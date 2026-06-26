package cmd

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/xiaoka6688/feishu-cli/internal/client"
	"github.com/xiaoka6688/feishu-cli/internal/config"
	"github.com/spf13/cobra"
)

// 合法 doc-type / file-extension
var driveExportAllowedDocTypes = []string{"doc", "docx", "sheet", "bitable"}
var driveExportAllowedExtensions = []string{"docx", "pdf", "xlsx", "csv", "markdown"}

var driveExportCmd = &cobra.Command{
	Use:   "export",
	Short: "导出云文档为本地文件（有界轮询 + markdown 快捷路径 + resume）",
	Long: `将 doc/docx/sheet/bitable 导出为本地文件。

- markdown 导出走 /docs/v1/content 快捷路径（仅 docx）
- 其他格式走 export_tasks 异步任务：创建 → 有界轮询（最多 10 次，每次 5s） → 下载
- 超时未完成时返回 next_command，可用 ` + "`drive task-result`" + ` 或 ` + "`drive export-download`" + ` 接力完成

必填:
  --token          源文档 token
  --doc-type       源文档类型: doc / docx / sheet / bitable
  --file-extension 导出格式: docx / pdf / xlsx / csv / markdown

可选:
  --sub-id         子表/工作表 ID（sheet/bitable → csv 时必填）
  --output-dir     输出目录（默认当前目录）
  --overwrite      已存在时覆盖
  --user-access-token  覆盖登录态

权限:
  - User Access Token
  - docs:document:export / drive:drive.metadata:readonly

示例:
  feishu-cli drive export --token docxxx --doc-type docx --file-extension markdown
  feishu-cli drive export --token sheetxxx --doc-type sheet --file-extension csv --sub-id 0 --output-dir ./out`,
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := config.Validate(); err != nil {
			return err
		}

		token, err := requireUserToken(cmd, "drive export")
		if err != nil {
			return err
		}

		docToken, _ := cmd.Flags().GetString("token")
		docType, _ := cmd.Flags().GetString("doc-type")
		fileExtension, _ := cmd.Flags().GetString("file-extension")
		subID, _ := cmd.Flags().GetString("sub-id")
		outputDir, _ := cmd.Flags().GetString("output-dir")
		overwrite, _ := cmd.Flags().GetBool("overwrite")
		output, _ := cmd.Flags().GetString("output")

		// 参数校验
		if docToken == "" {
			return fmt.Errorf("--token 必填")
		}
		if err := validateEnum(docType, "--doc-type", driveExportAllowedDocTypes); err != nil {
			return err
		}
		if err := validateEnum(fileExtension, "--file-extension", driveExportAllowedExtensions); err != nil {
			return err
		}
		if fileExtension == "markdown" && docType != "docx" {
			return fmt.Errorf("--file-extension markdown 仅支持 --doc-type docx")
		}
		if fileExtension == "csv" && (docType == "sheet" || docType == "bitable") && subID == "" {
			return fmt.Errorf("导出 sheet/bitable 为 csv 时 --sub-id 必填")
		}
		if subID != "" && (fileExtension != "csv" || (docType != "sheet" && docType != "bitable")) {
			return fmt.Errorf("--sub-id 仅在 sheet/bitable 导出 csv 时使用")
		}

		if outputDir == "" {
			outputDir = "."
		}
		if err := os.MkdirAll(outputDir, 0o755); err != nil {
			return fmt.Errorf("创建 --output-dir 失败: %w", err)
		}

		// Markdown 快捷路径：直接 /docs/v1/content
		if fileExtension == "markdown" {
			fmt.Fprintf(os.Stderr, "Markdown 快捷导出: %s\n", docToken)
			content, err := client.FetchDocxMarkdownContent(docToken, token)
			if err != nil {
				return err
			}

			// 尝试取文档标题
			title, _ := client.FetchDocMetaTitle(docToken, docType, token)
			fileName := sanitizeExportName(title, docToken) + ".md"
			savedPath := filepath.Join(outputDir, fileName)
			if _, err := os.Stat(savedPath); err == nil && !overwrite {
				return fmt.Errorf("文件已存在: %s（使用 --overwrite 覆盖）", savedPath)
			}
			if err := os.WriteFile(savedPath, []byte(content), 0o644); err != nil {
				return fmt.Errorf("写文件失败: %w", err)
			}

			result := map[string]any{
				"token":          docToken,
				"doc_type":       docType,
				"file_extension": fileExtension,
				"file_name":      fileName,
				"saved_path":     savedPath,
				"size_bytes":     len(content),
			}
			if output == "json" {
				return printJSON(result)
			}
			fmt.Printf("导出成功: %s (%d bytes)\n", savedPath, len(content))
			return nil
		}

		// 常规异步流程
		ticket, err := client.CreateExportTaskWithSubId(docToken, docType, fileExtension, subID, token)
		if err != nil {
			return err
		}
		fmt.Fprintf(os.Stderr, "创建导出任务: %s\n", ticket)

		status, timedOut, err := client.WaitDriveExportWithBound(ticket, docToken, token)
		if err != nil {
			return err
		}

		// 超时未完成 → 返回 resume 命令
		if timedOut {
			nextCmd := fmt.Sprintf("feishu-cli drive task-result --scenario export --ticket %s --file-token %s", ticket, docToken)
			result := map[string]any{
				"ticket":         ticket,
				"token":          docToken,
				"doc_type":       docType,
				"file_extension": fileExtension,
				"ready":          false,
				"timed_out":      true,
				"next_command":   nextCmd,
			}
			if status != nil {
				result["job_status"] = status.JobStatus
				result["job_status_label"] = status.StatusLabel()
			}
			if output == "json" {
				_ = printJSON(result)
			} else {
				fmt.Fprintf(os.Stderr, "导出任务仍在进行中，继续: %s\n", nextCmd)
			}
			return nil
		}

		// 任务就绪，下载
		fileName := sanitizeExportName(status.FileName, docToken) + "." + mapExtensionToSuffix(fileExtension)
		savedPath := filepath.Join(outputDir, fileName)
		if _, err := os.Stat(savedPath); err == nil && !overwrite {
			return fmt.Errorf("文件已存在: %s（使用 --overwrite 覆盖）", savedPath)
		}
		if err := client.DownloadExportFile(status.FileToken, savedPath, token); err != nil {
			nextCmd := fmt.Sprintf("feishu-cli drive export-download --file-token %s --output-dir %s", status.FileToken, outputDir)
			return fmt.Errorf("下载导出文件失败: %w\n可重试: %s", err, nextCmd)
		}

		stat, _ := os.Stat(savedPath)
		size := int64(0)
		if stat != nil {
			size = stat.Size()
		}
		result := map[string]any{
			"ticket":         ticket,
			"token":          docToken,
			"doc_type":       docType,
			"file_extension": fileExtension,
			"file_name":      fileName,
			"saved_path":     savedPath,
			"size_bytes":     size,
		}
		if output == "json" {
			return printJSON(result)
		}
		fmt.Printf("导出成功: %s (%d bytes)\n", savedPath, size)
		return nil
	},
}

// sanitizeExportName 把标题清洗为安全文件名（无扩展名）
func sanitizeExportName(title, fallback string) string {
	name := strings.TrimSpace(title)
	if name == "" {
		name = fallback
	}
	return safeOutputPath(name, "")
}

// mapExtensionToSuffix 把 --file-extension 值映射为本地文件后缀
func mapExtensionToSuffix(ext string) string {
	switch ext {
	case "markdown":
		return "md"
	case "docx", "pdf", "xlsx", "csv":
		return ext
	default:
		return ext
	}
}

var driveExportDownloadCmd = &cobra.Command{
	Use:   "export-download",
	Short: "下载已完成的导出任务文件（配合 drive export 超时后 resume）",
	Long: `通过 file_token 下载已经完成的导出任务产物。

必填:
  --file-token  导出任务生成的 file_token（由 drive export 或 drive task-result 返回）

可选:
  --file-name   保存文件名（默认由 file_token 自动构造）
  --output-dir  输出目录（默认当前目录）
  --overwrite   已存在时覆盖

示例:
  feishu-cli drive export-download --file-token boxxxx --output-dir ./exports`,
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := config.Validate(); err != nil {
			return err
		}

		token, err := requireUserToken(cmd, "drive export-download")
		if err != nil {
			return err
		}

		fileToken, _ := cmd.Flags().GetString("file-token")
		fileName, _ := cmd.Flags().GetString("file-name")
		outputDir, _ := cmd.Flags().GetString("output-dir")
		overwrite, _ := cmd.Flags().GetBool("overwrite")
		output, _ := cmd.Flags().GetString("output")

		if fileToken == "" {
			return fmt.Errorf("--file-token 必填")
		}
		if outputDir == "" {
			outputDir = "."
		}
		if err := os.MkdirAll(outputDir, 0o755); err != nil {
			return fmt.Errorf("创建 --output-dir 失败: %w", err)
		}

		if fileName == "" {
			fileName = safeOutputPath(fileToken, "")
		}
		savedPath := filepath.Join(outputDir, fileName)
		if _, err := os.Stat(savedPath); err == nil && !overwrite {
			return fmt.Errorf("文件已存在: %s（使用 --overwrite 覆盖）", savedPath)
		}

		if err := client.DownloadExportFile(fileToken, savedPath, token); err != nil {
			return err
		}

		stat, _ := os.Stat(savedPath)
		size := int64(0)
		if stat != nil {
			size = stat.Size()
		}
		result := map[string]any{
			"file_token": fileToken,
			"saved_path": savedPath,
			"size_bytes": size,
		}
		if output == "json" {
			return printJSON(result)
		}
		fmt.Printf("下载成功: %s (%d bytes)\n", savedPath, size)
		return nil
	},
}

func init() {
	driveCmd.AddCommand(driveExportCmd)
	driveExportCmd.Flags().String("token", "", "源文档 token（必填）")
	driveExportCmd.Flags().String("doc-type", "", "源文档类型: doc/docx/sheet/bitable（必填）")
	driveExportCmd.Flags().String("file-extension", "", "导出格式: docx/pdf/xlsx/csv/markdown（必填）")
	driveExportCmd.Flags().String("sub-id", "", "子表/工作表 ID（sheet/bitable 导出 csv 时必填）")
	driveExportCmd.Flags().String("output-dir", ".", "输出目录")
	driveExportCmd.Flags().Bool("overwrite", false, "已存在时覆盖")
	driveExportCmd.Flags().StringP("output", "o", "", "输出格式（json）")
	driveExportCmd.Flags().String("user-access-token", "", "User Access Token（覆盖登录态）")
	mustMarkFlagRequired(driveExportCmd, "token", "doc-type", "file-extension")

	driveCmd.AddCommand(driveExportDownloadCmd)
	driveExportDownloadCmd.Flags().String("file-token", "", "导出文件 token（必填）")
	driveExportDownloadCmd.Flags().String("file-name", "", "保存文件名")
	driveExportDownloadCmd.Flags().String("output-dir", ".", "输出目录")
	driveExportDownloadCmd.Flags().Bool("overwrite", false, "已存在时覆盖")
	driveExportDownloadCmd.Flags().StringP("output", "o", "", "输出格式（json）")
	driveExportDownloadCmd.Flags().String("user-access-token", "", "User Access Token（覆盖登录态）")
	mustMarkFlagRequired(driveExportDownloadCmd, "file-token")
}

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

// 格式特定的文件大小上限（参考飞书官方 drive +import 实现）
var driveImportSizeLimits = map[string]int64{
	"docx":    20 * 1024 * 1024,  // 20MB
	"sheet":   20 * 1024 * 1024,  // 20MB
	"bitable": 100 * 1024 * 1024, // 100MB
}

var driveImportAllowedTypes = []string{"docx", "sheet", "bitable"}

var driveImportCmd = &cobra.Command{
	Use:   "import",
	Short: "导入本地文件为云文档（分块上传 + 有界轮询 + resume）",
	Long: `导入本地文件为云文档（docx/sheet/bitable）。

流程:
  1. 上传本地文件到云盘（>20MB 自动走分块）
  2. 创建 import_tasks 任务
  3. 有界轮询（最多 30 次，每次 2s）
  4. 超时时返回 next_command 可用 drive task-result 继续

格式大小限制:
  - docx    : 20MB
  - sheet   : 20MB
  - bitable : 100MB

必填:
  --file        本地文件路径
  --type        目标文档类型: docx / sheet / bitable

可选:
  --folder-token  目标文件夹 token
  --name          导入后的文件名（默认本地文件名去扩展名）
  --user-access-token  覆盖登录态

权限:
  - User Access Token
  - docs:document:import / drive:file:upload

示例:
  feishu-cli drive import --file report.docx --type docx
  feishu-cli drive import --file data.xlsx --type sheet --folder-token fldxxx`,
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := config.Validate(); err != nil {
			return err
		}

		token, err := requireUserToken(cmd, "drive import")
		if err != nil {
			return err
		}

		filePath, _ := cmd.Flags().GetString("file")
		targetType, _ := cmd.Flags().GetString("type")
		folderToken, _ := cmd.Flags().GetString("folder-token")
		name, _ := cmd.Flags().GetString("name")
		output, _ := cmd.Flags().GetString("output")

		if filePath == "" {
			return fmt.Errorf("--file 必填")
		}
		if err := validateEnum(targetType, "--type", driveImportAllowedTypes); err != nil {
			return err
		}

		stat, err := os.Stat(filePath)
		if err != nil {
			return fmt.Errorf("读取文件失败: %w", err)
		}
		if stat.IsDir() {
			return fmt.Errorf("--file 必须指向文件")
		}

		// 格式大小校验
		if limit, ok := driveImportSizeLimits[targetType]; ok && stat.Size() > limit {
			return fmt.Errorf("文件大小 %d 超过 %s 限制 %d", stat.Size(), targetType, limit)
		}

		// 文件扩展名识别
		ext := strings.TrimPrefix(filepath.Ext(filePath), ".")
		if ext == "" {
			return fmt.Errorf("无法从文件名识别扩展名: %s", filePath)
		}

		// 导入名：默认去扩展名的本地文件名
		fileName := name
		if fileName == "" {
			base := filepath.Base(filePath)
			fileName = strings.TrimSuffix(base, filepath.Ext(base))
		}

		// Step 1: 上传临时媒体（不落到用户云盘）
		// 官方实现走 /medias/upload_all 端点 + parent_type=ccm_import_open + extra
		fmt.Fprintf(os.Stderr, "上传临时媒体: %s (%d bytes)\n", filepath.Base(filePath), stat.Size())
		uploadedName := filepath.Base(filePath)
		fileToken, err := client.UploadMediaForImport(filePath, uploadedName, targetType, ext, token)
		if err != nil {
			return fmt.Errorf("上传源文件失败: %w", err)
		}
		fmt.Fprintf(os.Stderr, "上传成功，file_token: %s\n", fileToken)

		// Step 2: 创建导入任务
		ticket, err := client.CreateImportTaskWithToken(fileToken, ext, fileName, targetType, folderToken, token)
		if err != nil {
			return err
		}
		fmt.Fprintf(os.Stderr, "创建导入任务: %s\n", ticket)

		// Step 3: 有界轮询
		status, timedOut, err := client.WaitDriveImportWithBound(ticket, token)
		if err != nil {
			return err
		}

		if timedOut {
			nextCmd := fmt.Sprintf("feishu-cli drive task-result --scenario import --ticket %s", ticket)
			result := map[string]any{
				"ticket":       ticket,
				"file_token":   fileToken,
				"type":         targetType,
				"ready":        false,
				"timed_out":    true,
				"next_command": nextCmd,
			}
			if status != nil {
				result["job_status"] = status.JobStatus
			}
			if output == "json" {
				_ = printJSON(result)
			} else {
				fmt.Fprintf(os.Stderr, "导入任务仍在进行中，继续: %s\n", nextCmd)
			}
			return nil
		}

		// 任务就绪
		result := map[string]any{
			"ticket":     ticket,
			"file_token": fileToken,
			"type":       targetType,
			"doc_token":  status.DocToken,
			"doc_url":    status.DocURL,
		}

		if output == "json" {
			return printJSON(result)
		}

		fmt.Printf("导入成功!\n")
		fmt.Printf("  类型:      %s\n", targetType)
		fmt.Printf("  doc_token: %s\n", status.DocToken)
		if status.DocURL != "" {
			fmt.Printf("  URL:       %s\n", status.DocURL)
		}
		return nil
	},
}

func init() {
	driveCmd.AddCommand(driveImportCmd)
	driveImportCmd.Flags().String("file", "", "本地文件路径（必填）")
	driveImportCmd.Flags().String("type", "", "目标文档类型: docx/sheet/bitable（必填）")
	driveImportCmd.Flags().String("folder-token", "", "目标文件夹 token")
	driveImportCmd.Flags().String("name", "", "导入后的文件名（默认本地文件名去扩展名）")
	driveImportCmd.Flags().StringP("output", "o", "", "输出格式（json）")
	driveImportCmd.Flags().String("user-access-token", "", "User Access Token（覆盖登录态）")
	mustMarkFlagRequired(driveImportCmd, "file", "type")
}

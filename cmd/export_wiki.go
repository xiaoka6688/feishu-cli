package cmd

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/riba2534/feishu-cli/internal/client"
	"github.com/riba2534/feishu-cli/internal/config"
	"github.com/riba2534/feishu-cli/internal/converter"
	"github.com/spf13/cobra"
)

var exportWikiCmd = &cobra.Command{
	Use:   "export <node_token|url>",
	Short: "导出知识库文档为 Markdown",
	Long: `导出知识库文档为 Markdown 文件。

支持的文档类型:
  docx      新版文档（完整支持）
  sheet     电子表格（读取数据转为 Markdown 表格）

工作流程:
  docx: 获取文档块 → 转换为 Markdown → 保存
  sheet: 获取工作表列表 → 读取单元格数据 → 转为 Markdown 表格 → 保存

参数:
  node_token        节点 Token
  url               知识库文档 URL
  --output, -o      输出文件路径
  --download-images 下载文档中的图片

示例:
  # 导出到默认路径
  feishu-cli wiki export Ad8Iw0oz3iSp4kkIi7QctVhin3e

  # 导出到指定路径
  feishu-cli wiki export Ad8Iw0oz3iSp4kkIi7QctVhin3e --output doc.md

  # 通过 URL 导出
  feishu-cli wiki export https://xxx.feishu.cn/wiki/Ad8Iw0oz3iSp4kkIi7QctVhin3e

  # 导出并下载图片
  feishu-cli wiki export Ad8Iw0oz3iSp4kkIi7QctVhin3e --download-images`,
	Args: cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := config.Validate(); err != nil {
			return err
		}

		// 解析 node_token
		nodeToken, err := extractWikiToken(args[0])
		if err != nil {
			return err
		}

		// 获取可选的 User Access Token（用于访问无 App 权限的文档）
		userAccessToken := resolveOptionalUserTokenWithFallback(cmd)

		// 1. 获取节点信息
		fmt.Printf("正在获取节点信息: %s\n", nodeToken)
		node, err := client.GetWikiNode(nodeToken, userAccessToken)
		if err != nil {
			return err
		}

		fmt.Printf("文档标题: %s\n", node.Title)
		fmt.Printf("文档类型: %s\n", node.ObjType)
		fmt.Printf("文档 Token: %s\n", node.ObjToken)

		var markdown string

		switch node.ObjType {
		case "docx":
			md, err := exportDocxToMarkdown(node.ObjToken, userAccessToken, cmd)
			if err != nil {
				return err
			}
			markdown = md
		case "sheet":
			md, err := exportSheetToMarkdown(node.ObjToken, node.Title, userAccessToken)
			if err != nil {
				return err
			}
			markdown = md
		default:
			return fmt.Errorf("暂不支持导出 %s 类型的文档，目前仅支持 docx、sheet", node.ObjType)
		}

		// 5. 保存文件
		outputPath, _ := cmd.Flags().GetString("output")
		if outputPath == "" {
			// 使用标题作为文件名
			safeTitle := node.Title
			if safeTitle == "" {
				safeTitle = nodeToken
			}
			outputPath = fmt.Sprintf("/tmp/%s.md", safeTitle)
		}

		// 路径安全检查
		if err := validateOutputPath(outputPath, ""); err != nil {
			return fmt.Errorf("输出路径不安全: %w", err)
		}

		// 确保目录存在（使用 0700 权限保护）
		dir := filepath.Dir(outputPath)
		if dir != "" && dir != "." {
			if err := os.MkdirAll(dir, 0700); err != nil {
				return fmt.Errorf("创建目录失败: %w", err)
			}
		}

		// 使用 0600 权限保护导出文件
		if err := os.WriteFile(outputPath, []byte(markdown), 0600); err != nil {
			return fmt.Errorf("写入文件失败: %w", err)
		}

		fmt.Printf("已导出到 %s\n", outputPath)
		return nil
	},
}

// exportDocxToMarkdown 导出 docx 类型文档为 Markdown
func exportDocxToMarkdown(docToken, userAccessToken string, cmd *cobra.Command) (string, error) {
	fmt.Println("正在获取文档内容...")
	blocks, err := client.GetAllBlocksWithToken(docToken, userAccessToken)
	if err != nil {
		return "", fmt.Errorf("获取块失败: %w", err)
	}

	downloadImages, _ := cmd.Flags().GetBool("download-images")
	assetsDir, _ := cmd.Flags().GetString("assets-dir")
	cfg := config.Get()

	conv := converter.NewBlockToMarkdown(blocks, converter.ConvertOptions{
		DocumentID:      docToken,
		DownloadImages:  downloadImages,
		AssetsDir:       assetsDir,
		UserAccessToken: userAccessToken,
		Debug:           cfg.Debug,
	})
	md, err := conv.Convert()
	if err != nil {
		return "", fmt.Errorf("转换为 Markdown 失败: %w", err)
	}
	return md, nil
}

// exportSheetToMarkdown 导出 sheet 类型文档为 Markdown
func exportSheetToMarkdown(spreadsheetToken, title, userAccessToken string) (string, error) {
	ctx := client.Context()

	// 1. 查询所有工作表
	fmt.Println("正在获取工作表列表...")
	sheets, err := client.QuerySheets(ctx, spreadsheetToken, userAccessToken)
	if err != nil {
		return "", fmt.Errorf("获取工作表列表失败: %w", err)
	}

	if len(sheets) == 0 {
		return "", fmt.Errorf("电子表格中没有工作表")
	}

	fmt.Printf("共 %d 个工作表，正在读取数据...\n", len(sheets))

	// 2. 逐个读取工作表数据
	var sheetDataList []*converter.SheetData
	for _, s := range sheets {
		if s.Hidden {
			continue
		}
		colLetter := colIndexToLetter(s.ColCount)
		rangeStr := fmt.Sprintf("%s!A1:%s%d", s.SheetID, colLetter, s.RowCount)

		cellRange, err := client.ReadCells(ctx, spreadsheetToken, rangeStr, "", "", userAccessToken)
		if err != nil {
			fmt.Printf("  ⚠ 读取工作表 %q 失败: %v，跳过\n", s.Title, err)
			continue
		}

		fmt.Printf("  ✓ %s（%d 行）\n", s.Title, len(cellRange.Values))
		sheetDataList = append(sheetDataList, &converter.SheetData{
			Title:  s.Title,
			Values: cellRange.Values,
		})
	}

	if len(sheetDataList) == 0 {
		return "", fmt.Errorf("没有可导出的工作表数据")
	}

	// 3. 转换为 Markdown
	var sb strings.Builder
	if title != "" {
		sb.WriteString("# ")
		sb.WriteString(title)
		sb.WriteString("\n\n")
	}
	sb.WriteString(converter.SheetToMarkdown(sheetDataList))

	return sb.String(), nil
}

// colIndexToLetter 将列数转为 Excel 列字母（1→A, 26→Z, 27→AA）
func colIndexToLetter(col int) string {
	var result string
	for col > 0 {
		col-- // 转为 0-based
		result = string(rune('A'+col%26)) + result
		col /= 26
	}
	return result
}

func init() {
	wikiCmd.AddCommand(exportWikiCmd)
	exportWikiCmd.Flags().StringP("output", "o", "", "输出文件路径")
	exportWikiCmd.Flags().Bool("download-images", false, "下载图片到本地目录")
	exportWikiCmd.Flags().String("assets-dir", "./assets", "下载资源的保存目录")
	exportWikiCmd.Flags().String("user-access-token", "", "User Access Token（可选，用于访问个人知识库）")
}

package cmd

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"

	"github.com/xiaoka6688/feishu-cli/internal/client"
	"github.com/spf13/cobra"
)

var sheetAppendCmd = &cobra.Command{
	Use:   "append <spreadsheet_token> <range>",
	Short: "追加数据到表格",
	Long: `在指定范围的最后一行之后追加数据。

数据格式（JSON 二维数组）:
  [["A值", "B值"], ["C值", "D值"]]

示例:
  feishu-cli sheet append shtcnxxxxxx "Sheet1!A:B" --data '[["新行1", "数据1"], ["新行2", "数据2"]]'`,
	Args: cobra.ExactArgs(2),
	RunE: func(cmd *cobra.Command, args []string) error {
		spreadsheetToken := args[0]
		rangeStr := args[1]
		sheetID, _ := cmd.Flags().GetString("sheet-id")
		dataStr, _ := cmd.Flags().GetString("data")
		dataFile, _ := cmd.Flags().GetString("data-file")
		insertOption, _ := cmd.Flags().GetString("insert-option")
		output, _ := cmd.Flags().GetString("output")

		// 处理 shell 转义
		rangeStr = unescapeSheetRange(rangeStr)

		if sheetID != "" && !strings.Contains(rangeStr, "!") {
			rangeStr = sheetID + "!" + rangeStr
		}

		var jsonData string
		if dataFile != "" {
			data, err := os.ReadFile(dataFile)
			if err != nil {
				return fmt.Errorf("读取数据文件失败: %w", err)
			}
			jsonData = string(data)
		} else if dataStr != "" {
			jsonData = dataStr
		} else {
			return fmt.Errorf("请通过 --data 或 --data-file 指定数据")
		}

		var values [][]any
		if err := json.Unmarshal([]byte(jsonData), &values); err != nil {
			return fmt.Errorf("解析数据失败: %w", err)
		}

		userAccessToken := resolveOptionalUserTokenWithFallback(cmd)

		result, err := client.AppendCells(client.Context(), spreadsheetToken, rangeStr, values, insertOption, userAccessToken)
		if err != nil {
			return err
		}

		if output == "json" {
			if err := printJSON(result); err != nil {
				return err
			}
		} else {
			fmt.Printf("追加成功！\n")
			fmt.Printf("  更新范围: %s\n", result.Range)
			fmt.Printf("  追加行数: %d\n", len(values))
		}

		return nil
	},
}

func init() {
	sheetCmd.AddCommand(sheetAppendCmd)

	sheetAppendCmd.Flags().String("sheet-id", "", "工作表 ID")
	sheetAppendCmd.Flags().StringP("data", "d", "", "要追加的数据（JSON 二维数组）")
	sheetAppendCmd.Flags().String("data-file", "", "数据文件路径")
	sheetAppendCmd.Flags().String("insert-option", "", "插入选项: OVERWRITE, INSERT_ROWS")
	sheetAppendCmd.Flags().StringP("output", "o", "text", "输出格式: text, json")
	sheetAppendCmd.Flags().String("user-access-token", "", "User Access Token（可选，用于访问无 App 权限的表格）")
}

package cmd

import (
	"fmt"

	"github.com/xiaoka6688/feishu-cli/internal/client"
	"github.com/xiaoka6688/feishu-cli/internal/config"
	"github.com/spf13/cobra"
)

var docTableInsertColumnCmd = &cobra.Command{
	Use:   "insert-column <document_id> <table_block_id>",
	Short: "在表格中插入列",
	Long: `在指定位置插入一列，使用 -1 表示插入到表格末尾。

参数:
  document_id     文档 ID
  table_block_id  表格块 ID（Block 类型 31）
  --index         插入位置索引（0 表示第一列，-1 表示末尾）

示例:
  # 在表格末尾插入一列
  feishu-cli doc table insert-column DOC_ID TABLE_BLOCK_ID --index -1

  # 在第一列位置插入
  feishu-cli doc table insert-column DOC_ID TABLE_BLOCK_ID --index 0`,
	Args: cobra.ExactArgs(2),
	RunE: runDocTableInsertColumn,
}

func init() {
	docTableCmd.AddCommand(docTableInsertColumnCmd)
	docTableInsertColumnCmd.Flags().Int("index", -1, "插入位置索引（-1 表示末尾）")
	docTableInsertColumnCmd.Flags().StringP("output", "o", "", "输出格式 (json)")
	docTableInsertColumnCmd.Flags().String("user-access-token", "", "User Access Token（可选）")
}

func runDocTableInsertColumn(cmd *cobra.Command, args []string) error {
	if err := config.Validate(); err != nil {
		return err
	}

	documentID := args[0]
	tableBlockID := args[1]
	index, _ := cmd.Flags().GetInt("index")
	output, _ := cmd.Flags().GetString("output")
	userAccessToken := resolveOptionalUserToken(cmd)

	// 飞书 API 仅接受 index == -1（末尾）或 index >= 0
	if index < -1 {
		return fmt.Errorf("索引必须 >= 0 或 -1（表示末尾）")
	}

	err := client.InsertTableColumn(documentID, tableBlockID, index, userAccessToken)
	if err != nil {
		return fmt.Errorf("插入列失败: %w", err)
	}

	if output == "json" {
		return printJSON(map[string]any{
			"document_id":    documentID,
			"table_block_id": tableBlockID,
			"operation":      "insert_column",
			"column_index":   index,
		})
	}

	posDesc := fmt.Sprintf("索引 %d", index)
	if index == -1 {
		posDesc = "表格末尾"
	}
	fmt.Printf("已在 %s 成功插入一列\n", posDesc)
	return nil
}

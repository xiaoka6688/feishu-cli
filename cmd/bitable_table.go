package cmd

import (
	"fmt"

	"github.com/riba2534/feishu-cli/internal/client"
	"github.com/spf13/cobra"
)

var bitableTablesCmd = &cobra.Command{
	Use:   "tables <app_token>",
	Short: "列出数据表",
	Long:  "列出多维表格中的所有数据表",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		appToken := args[0]
		output, _ := cmd.Flags().GetString("output")
		userToken := resolveOptionalUserToken(cmd)

		tables, err := client.ListBitableTables(appToken, userToken)
		if err != nil {
			return err
		}

		if output == "json" {
			return printJSON(tables)
		}

		if len(tables) == 0 {
			fmt.Println("暂无数据表")
			return nil
		}

		fmt.Printf("共 %d 个数据表：\n", len(tables))
		for i, t := range tables {
			fmt.Printf("  %d. %s (ID: %s)\n", i+1, t.Name, t.TableID)
		}
		return nil
	},
}

var bitableCreateTableCmd = &cobra.Command{
	Use:   "create-table <app_token>",
	Short: "创建数据表",
	Long:  "在多维表格中创建新的数据表",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		appToken := args[0]
		name, _ := cmd.Flags().GetString("name")
		output, _ := cmd.Flags().GetString("output")
		userToken := resolveOptionalUserToken(cmd)

		table, err := client.CreateBitableTable(appToken, name, userToken)
		if err != nil {
			return err
		}

		if output == "json" {
			return printJSON(table)
		}

		fmt.Printf("创建成功！\n")
		fmt.Printf("  Table ID: %s\n", table.TableID)
		fmt.Printf("  名称: %s\n", table.Name)
		return nil
	},
}

var bitableDeleteTableCmd = &cobra.Command{
	Use:   "delete-table <app_token> <table_id>",
	Short: "删除数据表",
	Long:  "删除多维表格中的数据表",
	Args:  cobra.ExactArgs(2),
	RunE: func(cmd *cobra.Command, args []string) error {
		appToken := args[0]
		tableID := args[1]
		userToken := resolveOptionalUserToken(cmd)

		if err := client.DeleteBitableTable(appToken, tableID, userToken); err != nil {
			return err
		}

		fmt.Println("删除成功")
		return nil
	},
}

var bitableRenameTableCmd = &cobra.Command{
	Use:   "rename-table <app_token> <table_id>",
	Short: "重命名数据表",
	Long:  "重命名多维表格中的数据表",
	Args:  cobra.ExactArgs(2),
	RunE: func(cmd *cobra.Command, args []string) error {
		appToken := args[0]
		tableID := args[1]
		name, _ := cmd.Flags().GetString("name")
		userToken := resolveOptionalUserToken(cmd)

		if err := client.RenameBitableTable(appToken, tableID, name, userToken); err != nil {
			return err
		}

		fmt.Printf("重命名成功: %s\n", name)
		return nil
	},
}

func init() {
	bitableCmd.AddCommand(bitableTablesCmd)
	bitableCmd.AddCommand(bitableCreateTableCmd)
	bitableCmd.AddCommand(bitableDeleteTableCmd)
	bitableCmd.AddCommand(bitableRenameTableCmd)

	// tables
	bitableTablesCmd.Flags().StringP("output", "o", "text", "输出格式: text, json")
	bitableTablesCmd.Flags().String("user-access-token", "", "User Access Token（可选）")

	// create-table
	bitableCreateTableCmd.Flags().StringP("name", "n", "", "数据表名称")
	bitableCreateTableCmd.Flags().StringP("output", "o", "text", "输出格式: text, json")
	bitableCreateTableCmd.Flags().String("user-access-token", "", "User Access Token（可选）")
	mustMarkFlagRequired(bitableCreateTableCmd, "name")

	// delete-table
	bitableDeleteTableCmd.Flags().String("user-access-token", "", "User Access Token（可选）")

	// rename-table
	bitableRenameTableCmd.Flags().StringP("name", "n", "", "新名称")
	bitableRenameTableCmd.Flags().String("user-access-token", "", "User Access Token（可选）")
	mustMarkFlagRequired(bitableRenameTableCmd, "name")
}

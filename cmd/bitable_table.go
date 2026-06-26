package cmd

import (
	"fmt"

	"github.com/xiaoka6688/feishu-cli/internal/client"
	"github.com/spf13/cobra"
)

var bitableTableCmd = &cobra.Command{
	Use:   "table",
	Short: "数据表管理（list/get/create/update/delete）",
}

func bitableTablePath(baseToken string, extra ...string) string {
	parts := []string{"bases", baseToken, "tables"}
	parts = append(parts, extra...)
	return client.BaseV3Path(parts...)
}

var bitableTableListCmd = &cobra.Command{
	Use:   "list",
	Short: "列出数据表",
	RunE: func(cmd *cobra.Command, args []string) error {
		offset, _ := cmd.Flags().GetInt("offset")
		limit, _ := cmd.Flags().GetInt("limit")
		params := map[string]any{}
		if offset > 0 {
			params["offset"] = offset
		}
		if limit > 0 {
			params["limit"] = limit
		}
		return runBaseV3Simple(cmd, "GET", func(bt string) string {
			return bitableTablePath(bt)
		}, params)
	},
}

var bitableTableGetCmd = &cobra.Command{
	Use:   "get",
	Short: "获取数据表信息",
	RunE: func(cmd *cobra.Command, args []string) error {
		tableID, _ := cmd.Flags().GetString("table-id")
		if tableID == "" {
			return fmt.Errorf("--table-id 必填")
		}
		return runBaseV3Simple(cmd, "GET", func(bt string) string {
			return bitableTablePath(bt, tableID)
		}, nil)
	},
}

var bitableTableCreateCmd = &cobra.Command{
	Use:   "create",
	Short: "创建数据表",
	Long:  `创建新数据表。--name 快捷指定名称，或 --config/--config-file 传入完整 table 配置`,
	RunE: func(cmd *cobra.Command, args []string) error {
		name, _ := cmd.Flags().GetString("name")
		configJSON, _ := cmd.Flags().GetString("config")
		configFile, _ := cmd.Flags().GetString("config-file")

		pathFn := func(bt string) string { return bitableTablePath(bt) }

		if configJSON != "" || configFile != "" {
			return runBaseV3WithJSON(cmd, "POST", pathFn)
		}
		if name == "" {
			return fmt.Errorf("需要 --name 或 --config/--config-file 至少一个")
		}
		// 官方 base/v3 body 顶层直接是字段，不包 "table" 一层
		body := map[string]any{"name": name}
		return runBaseV3WithBody(cmd, "POST", pathFn, body)
	},
}

var bitableTableUpdateCmd = &cobra.Command{
	Use:   "update",
	Short: "更新数据表",
	RunE: func(cmd *cobra.Command, args []string) error {
		tableID, _ := cmd.Flags().GetString("table-id")
		name, _ := cmd.Flags().GetString("name")
		configJSON, _ := cmd.Flags().GetString("config")
		configFile, _ := cmd.Flags().GetString("config-file")

		if tableID == "" {
			return fmt.Errorf("--table-id 必填")
		}

		pathFn := func(bt string) string { return bitableTablePath(bt, tableID) }

		if configJSON != "" || configFile != "" {
			return runBaseV3WithJSON(cmd, "PATCH", pathFn)
		}
		if name == "" {
			return fmt.Errorf("需要 --name 或 --config 至少一个")
		}
		body := map[string]any{"name": name}
		return runBaseV3WithBody(cmd, "PATCH", pathFn, body)
	},
}

var bitableTableDeleteCmd = &cobra.Command{
	Use:   "delete",
	Short: "删除数据表",
	RunE: func(cmd *cobra.Command, args []string) error {
		tableID, _ := cmd.Flags().GetString("table-id")
		if tableID == "" {
			return fmt.Errorf("--table-id 必填")
		}
		return runBaseV3Simple(cmd, "DELETE", func(bt string) string {
			return bitableTablePath(bt, tableID)
		}, nil)
	},
}

func init() {
	bitableCmd.AddCommand(bitableTableCmd)

	tableSubs := []*cobra.Command{
		bitableTableListCmd, bitableTableGetCmd, bitableTableCreateCmd,
		bitableTableUpdateCmd, bitableTableDeleteCmd,
	}
	for _, c := range tableSubs {
		bitableTableCmd.AddCommand(c)
		addBaseTokenFlag(c)
		c.Flags().String("user-access-token", "", "User Access Token")
	}

	bitableTableListCmd.Flags().Int("offset", 0, "分页 offset")
	bitableTableListCmd.Flags().Int("limit", 0, "分页 limit")

	bitableTableGetCmd.Flags().String("table-id", "", "table_id（必填）")
	mustMarkFlagRequired(bitableTableGetCmd, "table-id")

	bitableTableCreateCmd.Flags().String("name", "", "数据表名称")
	bitableTableCreateCmd.Flags().String("config", "", "JSON 配置（与 --config-file 互斥）")
	bitableTableCreateCmd.Flags().String("config-file", "", "JSON 配置文件路径")

	bitableTableUpdateCmd.Flags().String("table-id", "", "table_id（必填）")
	bitableTableUpdateCmd.Flags().String("name", "", "新名称")
	bitableTableUpdateCmd.Flags().String("config", "", "JSON 配置")
	bitableTableUpdateCmd.Flags().String("config-file", "", "JSON 配置文件")
	mustMarkFlagRequired(bitableTableUpdateCmd, "table-id")

	bitableTableDeleteCmd.Flags().String("table-id", "", "table_id（必填）")
	mustMarkFlagRequired(bitableTableDeleteCmd, "table-id")
}

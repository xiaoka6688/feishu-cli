package cmd

import (
	"fmt"
	"strings"

	"github.com/xiaoka6688/feishu-cli/internal/client"
	"github.com/xiaoka6688/feishu-cli/internal/config"
	"github.com/spf13/cobra"
)

var approvalGetCmd = &cobra.Command{
	Use:   "get <approval_code>",
	Short: "获取审批定义详情",
	Long: `获取指定审批定义的详细信息，包括名称、状态、表单结构和审批节点。

参数:
  approval_code   审批定义 Code（必填）
  --output, -o    输出格式，可选：json、raw-json

示例:
  # 获取审批定义详情
  feishu-cli approval get <approval_code>

  # 获取完整 JSON 输出
  feishu-cli approval get <approval_code> --output json

  # 获取原始 API 响应
  feishu-cli approval get <approval_code> --output raw-json

  # 指定语言
  feishu-cli approval get <approval_code> --locale zh-CN`,
	Args: cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := config.Validate(); err != nil {
			return err
		}

		approvalCode := args[0]
		if err := validateApprovalCode(approvalCode); err != nil {
			return err
		}

		locale, _ := cmd.Flags().GetString("locale")
		withAdminID, _ := cmd.Flags().GetBool("with-admin-id")
		withOption, _ := cmd.Flags().GetBool("with-option")
		output, _ := cmd.Flags().GetString("output")

		opts := client.GetApprovalOptions{
			Locale:      locale,
			WithAdminID: withAdminID,
			WithOption:  withOption,
		}

		if output == "raw-json" {
			raw, err := client.GetApprovalDefinitionRaw(approvalCode, opts)
			if err != nil {
				return err
			}
			fmt.Println(string(raw))
			return nil
		}

		approval, err := client.GetApprovalDefinition(approvalCode, opts)
		if err != nil {
			return err
		}

		if output == "json" {
			return printJSON(approval)
		}

		fmt.Printf("审批定义详情:\n")
		fmt.Printf("  Code: %s\n", approval.ApprovalCode)
		fmt.Printf("  名称: %s\n", approval.ApprovalName)
		fmt.Printf("  状态: %s\n", approval.Status)
		fmt.Printf("  节点数: %d\n", len(approval.NodeList))
		fmt.Printf("  可见人数量: %d\n", len(approval.Viewers))
		if len(approval.ApprovalAdminIDs) > 0 {
			fmt.Printf("  管理员 ID: %s\n", strings.Join(approval.ApprovalAdminIDs, ", "))
		}
		if len(approval.NodeList) > 0 {
			fmt.Printf("  节点列表:\n")
			for idx, node := range approval.NodeList {
				fmt.Printf("    %d. %s [%s]\n", idx+1, node.Name, node.NodeType)
			}
		}
		fmt.Printf("  使用 --output json 查看归一化结果，或 --output raw-json 查看飞书 API 原始响应\n")

		return nil
	},
}

func validateApprovalCode(approvalCode string) error {
	if !isValidToken(approvalCode) {
		return fmt.Errorf("无效的审批定义 code: %s", approvalCode)
	}
	return nil
}

func init() {
	approvalCmd.AddCommand(approvalGetCmd)

	approvalGetCmd.Flags().StringP("output", "o", "", "输出格式（json/raw-json）")
	approvalGetCmd.Flags().String("locale", "zh-CN", "返回结果语言，如 zh-CN、en-US")
	approvalGetCmd.Flags().Bool("with-admin-id", false, "返回有数据权限的审批流程管理员 ID")
	approvalGetCmd.Flags().Bool("with-option", false, "返回外部数据源和假勤控件选项")
}

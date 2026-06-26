package cmd

import (
	"github.com/xiaoka6688/feishu-cli/internal/client"
	"github.com/xiaoka6688/feishu-cli/internal/config"
	"github.com/spf13/cobra"
)

var getPublicPermissionCmd = &cobra.Command{
	Use:   "public-get <doc_token>",
	Short: "获取文档公共权限设置",
	Long: `获取文档的公共权限设置，包括外部访问、链接分享、评论权限等。

参数:
  doc_token       文档 Token
  --doc-type      文档类型（默认: docx）

返回字段说明:
  external_access   是否允许内容被分享到组织外
  security_entity   谁可以复制内容、创建副本、打印、下载
  comment_entity    谁可以评论
  share_entity      谁可以添加和管理协作者
  link_share_entity 链接分享设置
  invite_external   是否允许非管理权限的人分享到组织外
  lock_switch       节点加锁状态

示例:
  # 获取文档的公共权限设置
  feishu-cli perm public-get DOC_TOKEN

  # 获取电子表格的公共权限设置
  feishu-cli perm public-get DOC_TOKEN --doc-type sheet`,
	Args: cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := config.Validate(); err != nil {
			return err
		}

		docToken := args[0]
		docType, _ := cmd.Flags().GetString("doc-type")

		permPublic, err := client.GetPublicPermission(docToken, docType)
		if err != nil {
			return err
		}

		return printJSON(permPublic)
	},
}

func init() {
	permCmd.AddCommand(getPublicPermissionCmd)
	getPublicPermissionCmd.Flags().String("doc-type", "docx", "文档类型（docx/sheet/bitable 等）")
}

package cmd

import (
	"fmt"

	"github.com/xiaoka6688/feishu-cli/internal/client"
	"github.com/xiaoka6688/feishu-cli/internal/config"
	"github.com/spf13/cobra"
)

var chatCreateCmd = &cobra.Command{
	Use:   "create",
	Short: "创建群聊",
	Long: `创建一个新的群聊。

参数:
  --name           群名称（必填）
  --description    群描述
  --owner-id       群主 ID
  --user-ids       邀请的成员 ID 列表（逗号分隔）
  --chat-type      群类型（private/public，默认 private）

示例:
  # 创建私有群
  feishu-cli chat create --name "测试群"

  # 创建公开群并邀请成员
  feishu-cli chat create --name "公开群" --chat-type public --user-ids ou_xxx,ou_yyy

  # 指定群主创建群
  feishu-cli chat create --name "项目群" --owner-id ou_xxx --description "项目讨论群"`,
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := config.Validate(); err != nil {
			return err
		}

		name, _ := cmd.Flags().GetString("name")
		description, _ := cmd.Flags().GetString("description")
		ownerID, _ := cmd.Flags().GetString("owner-id")
		userIDsStr, _ := cmd.Flags().GetString("user-ids")
		chatType, _ := cmd.Flags().GetString("chat-type")

		var userIDs []string
		if userIDsStr != "" {
			userIDs = splitAndTrim(userIDsStr)
		}

		chatID, err := client.CreateChat(name, description, ownerID, userIDs, chatType)
		if err != nil {
			return err
		}

		fmt.Printf("群聊创建成功！\n")
		fmt.Printf("  群 ID: %s\n", chatID)

		return nil
	},
}

func init() {
	chatCmd.AddCommand(chatCreateCmd)
	chatCreateCmd.Flags().String("name", "", "群名称")
	chatCreateCmd.Flags().String("description", "", "群描述")
	chatCreateCmd.Flags().String("owner-id", "", "群主 ID")
	chatCreateCmd.Flags().String("user-ids", "", "邀请的成员 ID 列表（逗号分隔）")
	chatCreateCmd.Flags().String("chat-type", "private", "群类型（private/public）")
	mustMarkFlagRequired(chatCreateCmd, "name")
}

package cmd

import (
	"github.com/spf13/cobra"
)

var authCmd = &cobra.Command{
	Use:   "auth",
	Short: "用户授权管理",
	Long: `管理 OAuth 2.0 用户授权，用于获取 User Access Token。

搜索功能（search messages/docs/apps）需要 User Access Token。

示例:
  # 标准登录（Authorization Code Flow，需配置重定向 URL）
  feishu-cli auth login

  # Device Flow（无需配置重定向 URL 白名单）
  feishu-cli auth login --method device

  # 查看授权状态
  feishu-cli auth status

  # 退出登录
  feishu-cli auth logout`,
}

func init() {
	rootCmd.AddCommand(authCmd)
}

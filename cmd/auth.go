package cmd

import (
	"github.com/spf13/cobra"
)

var authCmd = &cobra.Command{
	Use:   "auth",
	Short: "用户授权管理",
	Long: `管理 OAuth 2.0 用户授权，用于获取 User Access Token。

子命令:
  login    登录授权（支持 Authorization Code Flow 和 Device Flow）
  status   查看当前授权状态
  logout   退出登录（清除本地 token）

搜索功能（search messages/docs/apps）需要 User Access Token。

示例:
  # 标准登录（Authorization Code Flow，需配置重定向 URL）
  feishu-cli auth login

  # Device Flow（无需重定向 URL，适合 CI/CD 和无头环境）
  feishu-cli auth login --device

  # 查看授权状态
  feishu-cli auth status

  # 退出登录
  feishu-cli auth logout`,
}

func init() {
	rootCmd.AddCommand(authCmd)
}

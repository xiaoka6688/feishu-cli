package cmd

import (
	"fmt"

	"github.com/xiaoka6688/feishu-cli/internal/client"
	"github.com/xiaoka6688/feishu-cli/internal/config"
	"github.com/spf13/cobra"
)

var userSearchCmd = &cobra.Command{
	Use:   "search",
	Short: "查询用户 ID（支持邮箱/手机号/关键词）",
	Long: `查询用户 ID。支持三种入口：
  --email / --mobile  走 contact/v3/users/batch_get_id（App Token 亦可），返回 user_id；
                      额外通过 search/v1/user（User Token 必需）补齐 open_id 和姓名。
  --query             直接走 search/v1/user，按姓名/邮箱/手机号模糊搜索，返回 open_id。

参数:
  --email     邮箱列表，逗号分隔
  --mobile    手机号列表，逗号分隔
  --query     任意关键词（姓名/邮箱/手机号）

示例:
  feishu-cli user search --email user@example.com
  feishu-cli user search --mobile +8613800138000
  feishu-cli user search --query "张三" -o json
  feishu-cli user search --email a@example.com,b@example.com -o json`,
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := config.Validate(); err != nil {
			return err
		}

		emailStr, _ := cmd.Flags().GetString("email")
		mobileStr, _ := cmd.Flags().GetString("mobile")
		query, _ := cmd.Flags().GetString("query")
		output, _ := cmd.Flags().GetString("output")

		if emailStr == "" && mobileStr == "" && query == "" {
			return fmt.Errorf("至少需要指定 --email、--mobile 或 --query 之一")
		}

		userToken := resolveOptionalUserTokenWithFallback(cmd)

		// --query 独立路径：直接走搜索 API，返回 open_id
		if query != "" {
			if userToken == "" {
				return fmt.Errorf("--query 需要 User Access Token，请先执行 auth login 或通过 --user-access-token 传入")
			}
			res, err := client.SearchUsers(query, 0, "", userToken)
			if err != nil {
				return err
			}
			if output == "json" {
				return printJSON(res)
			}
			if len(res.Users) == 0 {
				fmt.Println("未找到匹配的用户")
				return nil
			}
			fmt.Printf("查询结果（共 %d 条）:\n\n", len(res.Users))
			for i, u := range res.Users {
				fmt.Printf("[%d] %s\n", i+1, u.Name)
				if u.OpenID != "" {
					fmt.Printf("    open_id: %s\n", u.OpenID)
				}
				if u.UserID != "" {
					fmt.Printf("    user_id: %s\n", u.UserID)
				}
				fmt.Println()
			}
			return nil
		}

		// --email / --mobile 路径
		var emails, mobiles []string
		if emailStr != "" {
			emails = splitAndTrim(emailStr)
		}
		if mobileStr != "" {
			mobiles = splitAndTrim(mobileStr)
		}

		result, err := client.BatchGetUserID(emails, mobiles)
		if err != nil {
			return err
		}

		// 有 User Token 时为每条邮箱/手机号额外调 SearchUsers 补 open_id 和姓名。
		// 搜不到不是错误 — 保留 BatchGetUserID 原始结果，只是没 open_id。
		if userToken != "" {
			enrichWithSearch := func(infos []*client.UserContactIDInfo, getKey func(*client.UserContactIDInfo) string) {
				for _, info := range infos {
					k := getKey(info)
					if k == "" || info.OpenID != "" {
						continue
					}
					res, err := client.SearchUsers(k, 0, "", userToken)
					if err != nil || res == nil || len(res.Users) == 0 {
						continue
					}
					info.OpenID = res.Users[0].OpenID
					info.Name = res.Users[0].Name
				}
			}
			enrichWithSearch(result, func(i *client.UserContactIDInfo) string { return i.Email })
			enrichWithSearch(result, func(i *client.UserContactIDInfo) string { return i.Mobile })
		}

		if output == "json" {
			return printJSON(result)
		}

		if len(result) == 0 {
			fmt.Println("未找到匹配的用户")
			return nil
		}

		fmt.Printf("查询结果（共 %d 条）:\n\n", len(result))
		for i, item := range result {
			fmt.Printf("[%d]", i+1)
			if item.Name != "" {
				fmt.Printf(" %s", item.Name)
			}
			fmt.Println()
			if item.UserID != "" {
				fmt.Printf("    user_id: %s\n", item.UserID)
			}
			if item.OpenID != "" {
				fmt.Printf("    open_id: %s\n", item.OpenID)
			}
			if item.Email != "" {
				fmt.Printf("    邮箱: %s\n", item.Email)
			}
			if item.Mobile != "" {
				fmt.Printf("    手机号: %s\n", item.Mobile)
			}
			fmt.Println()
		}

		return nil
	},
}

func init() {
	userCmd.AddCommand(userSearchCmd)
	userSearchCmd.Flags().String("email", "", "邮箱列表，逗号分隔")
	userSearchCmd.Flags().String("mobile", "", "手机号列表，逗号分隔")
	userSearchCmd.Flags().String("query", "", "关键词搜索（姓名/邮箱/手机号），需 User Token")
	userSearchCmd.Flags().StringP("output", "o", "", "输出格式（json）")
	userSearchCmd.Flags().String("user-access-token", "", "User Access Token（用户授权令牌）")
}

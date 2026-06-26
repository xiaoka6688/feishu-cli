package cmd

import (
	"fmt"

	"github.com/xiaoka6688/feishu-cli/internal/client"
	"github.com/xiaoka6688/feishu-cli/internal/config"
	"github.com/spf13/cobra"
)

var myTasksCmd = &cobra.Command{
	Use:   "my",
	Short: "查看我的任务",
	Long: `查看分配给当前用户的任务列表。

此命令需要 User Access Token（用户授权），会通过完整优先级链自动解析：
  1. --user-access-token 参数
  2. FEISHU_USER_ACCESS_TOKEN 环境变量
  3. ~/.feishu-cli/token.json（支持自动刷新）
  4. config.yaml 中的 user_access_token

参数:
  --completed       只显示已完成的任务
  --uncompleted     只显示未完成的任务
  --page-size       每页数量（默认: 50）
  --page-token      分页标记
  --output, -o      输出格式（json）

示例:
  # 查看我的未完成任务
  feishu-cli task my

  # 查看我的已完成任务
  feishu-cli task my --completed

  # 分页查询
  feishu-cli task my --page-size 10

  # JSON 格式输出
  feishu-cli task my --output json`,
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := config.Validate(); err != nil {
			return err
		}

		token, err := resolveRequiredUserToken(cmd)
		if err != nil {
			return fmt.Errorf("查看我的任务需要 User Access Token: %w\n提示: 请先执行 feishu-cli auth login 进行授权", err)
		}

		pageSize, _ := cmd.Flags().GetInt("page-size")
		pageToken, _ := cmd.Flags().GetString("page-token")
		completedFlag, _ := cmd.Flags().GetBool("completed")
		uncompletedFlag, _ := cmd.Flags().GetBool("uncompleted")

		var completed *bool
		if completedFlag {
			t := true
			completed = &t
		} else if uncompletedFlag {
			f := false
			completed = &f
		}

		result, err := client.ListTasks(pageSize, pageToken, completed, token)
		if err != nil {
			return err
		}

		output, _ := cmd.Flags().GetString("output")
		if output == "json" {
			if err := printJSON(result); err != nil {
				return err
			}
		} else {
			if len(result.Tasks) == 0 {
				fmt.Println("没有找到任务")
				return nil
			}

			fmt.Printf("我的任务（共 %d 个）:\n\n", len(result.Tasks))
			for i, task := range result.Tasks {
				status := "[ ]"
				if task.CompletedAt != "" {
					status = "[x]"
				}
				fmt.Printf("[%d] %s %s\n", i+1, status, task.Summary)
				fmt.Printf("    ID: %s\n", task.Guid)
				if task.Description != "" {
					desc := task.Description
					if len(desc) > 50 {
						desc = desc[:50] + "..."
					}
					fmt.Printf("    描述: %s\n", desc)
				}
				if task.DueTime != "" {
					fmt.Printf("    截止: %s\n", task.DueTime)
				}
				if task.CompletedAt != "" {
					fmt.Printf("    完成: %s\n", task.CompletedAt)
				}
				fmt.Println()
			}

			if result.HasMore {
				fmt.Printf("还有更多任务，使用 --page-token %s 获取下一页\n", result.PageToken)
			}
		}

		return nil
	},
}

func init() {
	taskCmd.AddCommand(myTasksCmd)
	myTasksCmd.Flags().Int("page-size", 50, "每页数量")
	myTasksCmd.Flags().String("page-token", "", "分页标记")
	myTasksCmd.Flags().Bool("completed", false, "只显示已完成的任务")
	myTasksCmd.Flags().Bool("uncompleted", false, "只显示未完成的任务")
	myTasksCmd.Flags().StringP("output", "o", "", "输出格式（json）")
	myTasksCmd.Flags().String("user-access-token", "", "User Access Token（用户授权令牌）")
}

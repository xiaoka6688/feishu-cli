package cmd

import (
	"encoding/json"
	"fmt"

	"github.com/xiaoka6688/feishu-cli/internal/client"
	"github.com/xiaoka6688/feishu-cli/internal/config"
	"github.com/spf13/cobra"
)

// minutesCmd 妙记父命令
var minutesCmd = &cobra.Command{
	Use:   "minutes",
	Short: "妙记操作命令",
	Long: `妙记相关操作。

子命令:
  get       获取妙记基础信息（可选合并 AI 产物）
  download  下载妙记媒体文件（批量）

示例:
  feishu-cli minutes get obcnxxxx
  feishu-cli minutes get obcnxxxx --with-artifacts
  feishu-cli minutes download --minute-tokens obcnxxxx --output ./media`,
}

var minutesGetCmd = &cobra.Command{
	Use:   "get <minute_token>",
	Short: "获取妙记信息",
	Long: `通过妙记 Token 获取妙记基础信息，包括标题、链接、创建时间、时长等。

参数:
  minute_token  妙记 Token

可选:
  --with-artifacts  额外获取 AI 产物（summary / todos / chapters）
  -o, --output json 以 JSON 格式输出

权限:
  - User Access Token
  - minutes:minutes:readonly
  - --with-artifacts 额外需要 minutes:minutes.artifacts:read

示例:
  feishu-cli minutes get obcnxxxx
  feishu-cli minutes get obcnxxxx --with-artifacts -o json`,
	Args: cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := config.Validate(); err != nil {
			return err
		}

		token, err := requireUserToken(cmd, "minutes get")
		if err != nil {
			return err
		}

		minuteToken := args[0]
		if err := ensureMinuteToken(minuteToken); err != nil {
			return err
		}

		withArtifacts, _ := cmd.Flags().GetBool("with-artifacts")
		output, _ := cmd.Flags().GetString("output")

		minuteData, err := client.GetMinute(minuteToken, token)
		if err != nil {
			return err
		}

		var artifactsData json.RawMessage
		if withArtifacts {
			ad, artErr := client.GetMinuteArtifacts(minuteToken, token)
			if artErr != nil {
				if output == "json" {
					return printJSON(map[string]any{
						"minute":          json.RawMessage(minuteData),
						"artifacts_error": artErr.Error(),
					})
				}
				printMinuteText(minuteData, nil)
				fmt.Printf("\nAI 产物获取失败: %v\n", artErr)
				return nil
			}
			artifactsData = ad
		}

		if output == "json" {
			result := map[string]any{"minute": json.RawMessage(minuteData)}
			if artifactsData != nil {
				result["artifacts"] = json.RawMessage(artifactsData)
			}
			return printJSON(result)
		}

		printMinuteText(minuteData, artifactsData)
		return nil
	},
}

// printMinuteText 文本格式化输出妙记信息
func printMinuteText(minuteData, artifactsData json.RawMessage) {
	var parsed struct {
		Minute struct {
			Token      string `json:"token"`
			Title      string `json:"title"`
			URL        string `json:"url"`
			CreateTime string `json:"create_time"`
			OwnerID    string `json:"owner_id"`
			Duration   string `json:"duration"`
		} `json:"minute"`
	}
	if err := json.Unmarshal(minuteData, &parsed); err != nil {
		fmt.Println(string(minuteData))
		return
	}

	m := parsed.Minute
	title := m.Title
	if title == "" {
		title = "(无标题)"
	}

	fmt.Printf("妙记信息:\n\n")
	fmt.Printf("  标题:      %s\n", title)
	if m.Token != "" {
		fmt.Printf("  Token:     %s\n", m.Token)
	}
	if m.URL != "" {
		fmt.Printf("  链接:      %s\n", m.URL)
	}
	if m.CreateTime != "" {
		fmt.Printf("  创建时间:  %s\n", formatVCTime(m.CreateTime))
	}
	if m.OwnerID != "" {
		fmt.Printf("  创建者:    %s\n", m.OwnerID)
	}
	if m.Duration != "" {
		fmt.Printf("  时长:      %s\n", m.Duration)
	}

	if len(artifactsData) == 0 {
		return
	}

	var art struct {
		Summary        string `json:"summary"`
		MinuteTodos    any    `json:"minute_todos"`
		MinuteChapters any    `json:"minute_chapters"`
	}
	if err := json.Unmarshal(artifactsData, &art); err != nil {
		fmt.Printf("\nAI 产物（原始）: %s\n", string(artifactsData))
		return
	}

	if art.Summary != "" {
		summary := art.Summary
		if len(summary) > 400 {
			summary = summary[:400] + "…"
		}
		fmt.Printf("\nAI 摘要:\n  %s\n", summary)
	}
	if art.MinuteTodos != nil {
		if b, _ := json.MarshalIndent(art.MinuteTodos, "  ", "  "); len(b) > 0 {
			fmt.Printf("\nTodo 列表:\n  %s\n", string(b))
		}
	}
	if art.MinuteChapters != nil {
		if b, _ := json.MarshalIndent(art.MinuteChapters, "  ", "  "); len(b) > 0 {
			fmt.Printf("\n章节:\n  %s\n", string(b))
		}
	}
}

func init() {
	rootCmd.AddCommand(minutesCmd)
	minutesCmd.AddCommand(minutesGetCmd)
	minutesGetCmd.Flags().Bool("with-artifacts", false, "额外获取 AI 产物（summary/todos/chapters）")
	minutesGetCmd.Flags().StringP("output", "o", "", "输出格式（json）")
	minutesGetCmd.Flags().String("user-access-token", "", "User Access Token（覆盖登录态）")
}

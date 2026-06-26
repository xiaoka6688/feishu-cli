package cmd

import (
	"fmt"

	"github.com/xiaoka6688/feishu-cli/internal/client"
	"github.com/xiaoka6688/feishu-cli/internal/config"
	"github.com/spf13/cobra"
)

var mailDraftEditCmd = &cobra.Command{
	Use:   "draft-edit",
	Short: "编辑已有邮件草稿（全量覆盖）",
	Long: `编辑已有的邮件草稿。注意：这是全量覆盖（PUT 语义），需要提供完整的新内容。

必填:
  --draft-id    要编辑的草稿 ID
  --to          新收件人
  --subject     新主题
  --body        新正文

可选:
  --cc / --bcc / --from / --from-name / --html / --plain-text / --mailbox

示例:
  feishu-cli mail draft-edit --draft-id xxx --to user@example.com --subject "修改后的主题" --body "新内容"`,
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := config.Validate(); err != nil {
			return err
		}
		token, err := requireUserToken(cmd, "mail draft-edit")
		if err != nil {
			return err
		}

		mailbox, _ := cmd.Flags().GetString("mailbox")
		draftID, _ := cmd.Flags().GetString("draft-id")
		toRaw, _ := cmd.Flags().GetString("to")
		ccRaw, _ := cmd.Flags().GetString("cc")
		bccRaw, _ := cmd.Flags().GetString("bcc")
		subject, _ := cmd.Flags().GetString("subject")
		body, _ := cmd.Flags().GetString("body")
		from, _ := cmd.Flags().GetString("from")
		fromName, _ := cmd.Flags().GetString("from-name")
		forceHTML, _ := cmd.Flags().GetBool("html")
		plainText, _ := cmd.Flags().GetBool("plain-text")
		output, _ := cmd.Flags().GetString("output")

		if draftID == "" {
			return fmt.Errorf("--draft-id 必填")
		}

		to, err := parseEmailList(toRaw)
		if err != nil {
			return err
		}
		if len(to) == 0 {
			return fmt.Errorf("--to 至少一个收件人")
		}
		cc, err := parseEmailList(ccRaw)
		if err != nil {
			return err
		}
		bcc, err := parseEmailList(bccRaw)
		if err != nil {
			return err
		}

		if from == "" {
			if profile, perr := client.GetMailboxProfile(mailbox, token); perr == nil && profile != nil {
				from = profile.PrimaryEmailAddress
				if fromName == "" {
					fromName = profile.Name
				}
			}
		}

		isHTML := forceHTML
		if !forceHTML && !plainText {
			isHTML = detectHTMLBody(body)
		}

		input := mailMessageInput{
			From:     from,
			FromName: fromName,
			To:       to,
			CC:       cc,
			BCC:      bcc,
			Subject:  subject,
		}
		if isHTML {
			input.BodyHTML = body
		} else {
			input.BodyText = body
		}

		rawB64, err := buildEMLBase64URL(input)
		if err != nil {
			return err
		}

		if err := client.UpdateMailDraft(mailbox, draftID, rawB64, token); err != nil {
			return err
		}

		result := map[string]any{"draft_id": draftID, "updated": true}
		if output == "json" {
			return printJSON(result)
		}
		fmt.Printf("草稿更新成功: %s\n", draftID)
		return nil
	},
}

func init() {
	mailCmd.AddCommand(mailDraftEditCmd)
	mailDraftEditCmd.Flags().String("mailbox", "me", "邮箱 ID（默认 me）")
	mailDraftEditCmd.Flags().String("draft-id", "", "草稿 ID（必填）")
	mailDraftEditCmd.Flags().String("to", "", "收件人（必填）")
	mailDraftEditCmd.Flags().String("cc", "", "抄送")
	mailDraftEditCmd.Flags().String("bcc", "", "密送")
	mailDraftEditCmd.Flags().String("subject", "", "主题（必填）")
	mailDraftEditCmd.Flags().String("body", "", "正文（必填）")
	mailDraftEditCmd.Flags().String("from", "", "发件人地址")
	mailDraftEditCmd.Flags().String("from-name", "", "发件人显示名")
	mailDraftEditCmd.Flags().Bool("html", false, "强制视为 HTML body")
	mailDraftEditCmd.Flags().Bool("plain-text", false, "强制视为纯文本")
	mailDraftEditCmd.Flags().StringP("output", "o", "", "输出格式（json）")
	mailDraftEditCmd.Flags().String("user-access-token", "", "User Access Token（覆盖登录态）")
	mustMarkFlagRequired(mailDraftEditCmd, "draft-id", "to", "subject", "body")
}

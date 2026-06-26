package cmd

import (
	"encoding/json"
	"fmt"
	"strings"

	"github.com/xiaoka6688/feishu-cli/internal/client"
	"github.com/xiaoka6688/feishu-cli/internal/config"
	"github.com/spf13/cobra"
)

var mailReplyCmd = &cobra.Command{
	Use:   "reply",
	Short: "回复邮件（自动 Re: 前缀 + 引用块）",
	Long: `回复指定邮件。自动：
  1. 获取原邮件的 subject/from/body/smtp_message_id
  2. subject 加 "Re: " 前缀（已有则不重复）
  3. In-Reply-To / References header 继承原邮件
  4. body 自动带原文引用块

必填:
  --message-id   要回复的邮件 ID
  --body         回复正文

可选:
  --confirm-send 保存草稿后立即发送
  --mailbox      默认 me

示例:
  feishu-cli mail reply --message-id msg_xxx --body "收到，周三开会"
  feishu-cli mail reply --message-id msg_xxx --body "同意" --confirm-send`,
	RunE: func(cmd *cobra.Command, args []string) error {
		return runMailReply(cmd, false)
	},
}

var mailReplyAllCmd = &cobra.Command{
	Use:   "reply-all",
	Short: "全部回复（包含 To 和 CC 所有收件人）",
	Long: `全部回复指定邮件，自动包含原邮件的所有 To 和 CC 收件人。

参数同 mail reply。`,
	RunE: func(cmd *cobra.Command, args []string) error {
		return runMailReply(cmd, true)
	},
}

func runMailReply(cmd *cobra.Command, replyAll bool) error {
	if err := config.Validate(); err != nil {
		return err
	}
	token, err := requireUserToken(cmd, "mail reply")
	if err != nil {
		return err
	}

	mailbox, _ := cmd.Flags().GetString("mailbox")
	messageID, _ := cmd.Flags().GetString("message-id")
	body, _ := cmd.Flags().GetString("body")
	confirmSend, _ := cmd.Flags().GetBool("confirm-send")
	forceHTML, _ := cmd.Flags().GetBool("html")
	plainText, _ := cmd.Flags().GetBool("plain-text")
	output, _ := cmd.Flags().GetString("output")

	if messageID == "" {
		return fmt.Errorf("--message-id 必填")
	}

	// Step 1: 获取原邮件
	origData, err := client.GetMailMessage(mailbox, messageID, "full", token)
	if err != nil {
		return fmt.Errorf("获取原邮件失败: %w", err)
	}

	var orig struct {
		Message struct {
			Subject       string `json:"subject"`
			SMTPMessageID string `json:"smtp_message_id"`
			References    string `json:"references"`
			HeadFrom      struct {
				MailAddress string `json:"mail_address"`
				Name        string `json:"name"`
			} `json:"head_from"`
			To []struct {
				MailAddress string `json:"mail_address"`
				Name        string `json:"name"`
			} `json:"to"`
			Cc []struct {
				MailAddress string `json:"mail_address"`
				Name        string `json:"name"`
			} `json:"cc"`
			BodyPlainText string `json:"body_plain_text"`
		} `json:"message"`
	}
	// 响应有两种包装：{data: {message: {...}}} 或 {message: {...}} 或直接 {...}
	if err := json.Unmarshal(origData, &orig); err != nil {
		return fmt.Errorf("解析原邮件失败: %w", err)
	}
	// 如果 Message 为空，data 本身可能是 message
	if orig.Message.Subject == "" {
		if err := json.Unmarshal(origData, &orig.Message); err != nil {
			// 继续用空值
			_ = err
		}
	}

	origMsg := orig.Message

	// 单次获取 profile，提供 selfEmail（排除自己）+ from/fromName（发件人）
	var selfEmail, from, fromName string
	if profile, perr := client.GetMailboxProfile(mailbox, token); perr == nil && profile != nil {
		selfEmail = profile.PrimaryEmailAddress
		from = profile.PrimaryEmailAddress
		fromName = profile.Name
	}

	// Step 3: 构造收件人
	var to []string
	var cc []string

	// reply / reply-all 都把原发件人作为主收件人
	if origMsg.HeadFrom.MailAddress != "" && origMsg.HeadFrom.MailAddress != selfEmail {
		if origMsg.HeadFrom.Name != "" {
			to = append(to, fmt.Sprintf("%s <%s>", origMsg.HeadFrom.Name, origMsg.HeadFrom.MailAddress))
		} else {
			to = append(to, origMsg.HeadFrom.MailAddress)
		}
	}

	if replyAll {
		// To 列表（排除自己）
		for _, r := range origMsg.To {
			if r.MailAddress == "" || r.MailAddress == selfEmail {
				continue
			}
			if r.Name != "" {
				to = append(to, fmt.Sprintf("%s <%s>", r.Name, r.MailAddress))
			} else {
				to = append(to, r.MailAddress)
			}
		}
		// CC 列表（排除自己）
		for _, r := range origMsg.Cc {
			if r.MailAddress == "" || r.MailAddress == selfEmail {
				continue
			}
			if r.Name != "" {
				cc = append(cc, fmt.Sprintf("%s <%s>", r.Name, r.MailAddress))
			} else {
				cc = append(cc, r.MailAddress)
			}
		}
	}

	if len(to) == 0 {
		return fmt.Errorf("无法确定回复收件人（原邮件 from 缺失或仅是自己）")
	}

	// Step 4: 构造 subject
	subject := ensureReplySubject(origMsg.Subject)

	quotedBody := buildQuotedBody(origMsg.BodyPlainText, "> ")
	quoteHeader := fmt.Sprintf("\n\n%s 写道:\n", origMsg.HeadFrom.MailAddress)
	fullBody := body + quoteHeader + quotedBody

	// Step 6: References / In-Reply-To
	inReplyTo := origMsg.SMTPMessageID
	references := strings.TrimSpace(origMsg.References)
	if references != "" && origMsg.SMTPMessageID != "" {
		references += " " + origMsg.SMTPMessageID
	} else if origMsg.SMTPMessageID != "" {
		references = origMsg.SMTPMessageID
	}

	// 构造 EML（from/fromName 已在前面一次性从 profile 获取）
	isHTML := forceHTML
	if !forceHTML && !plainText {
		isHTML = detectHTMLBody(body)
	}
	input := mailMessageInput{
		From:       from,
		FromName:   fromName,
		To:         to,
		CC:         cc,
		Subject:    subject,
		InReplyTo:  inReplyTo,
		References: references,
	}
	if isHTML {
		input.BodyHTML = fullBody
	} else {
		input.BodyText = fullBody
	}

	rawB64, err := buildEMLBase64URL(input)
	if err != nil {
		return err
	}

	// Step 9: 保存草稿
	draftID, err := client.CreateMailDraft(mailbox, rawB64, token)
	if err != nil {
		return err
	}

	if !confirmSend {
		result := map[string]any{"draft_id": draftID, "confirmed": false}
		if output == "json" {
			return printJSON(result)
		}
		fmt.Printf("回复草稿已保存: %s\n", draftID)
		return nil
	}

	// 发送
	sendData, err := client.SendMailDraft(mailbox, draftID, token)
	if err != nil {
		return fmt.Errorf("发送失败（草稿 %s 已创建）: %w", draftID, err)
	}

	var sent struct {
		MessageID string `json:"message_id"`
		ThreadID  string `json:"thread_id"`
	}
	_ = json.Unmarshal(sendData, &sent)

	result := map[string]any{
		"draft_id":   draftID,
		"message_id": sent.MessageID,
		"thread_id":  sent.ThreadID,
		"confirmed":  true,
	}
	if output == "json" {
		return printJSON(result)
	}
	fmt.Printf("回复发送成功 (message_id=%s)\n", sent.MessageID)
	return nil
}

func init() {
	mailCmd.AddCommand(mailReplyCmd)
	mailReplyCmd.Flags().String("mailbox", "me", "邮箱 ID（默认 me）")
	mailReplyCmd.Flags().String("message-id", "", "要回复的邮件 ID（必填）")
	mailReplyCmd.Flags().String("body", "", "回复正文（必填）")
	mailReplyCmd.Flags().Bool("confirm-send", false, "保存草稿后立即发送")
	mailReplyCmd.Flags().Bool("html", false, "强制视为 HTML body")
	mailReplyCmd.Flags().Bool("plain-text", false, "强制视为纯文本")
	mailReplyCmd.Flags().StringP("output", "o", "", "输出格式（json）")
	mailReplyCmd.Flags().String("user-access-token", "", "User Access Token（覆盖登录态）")
	mustMarkFlagRequired(mailReplyCmd, "message-id", "body")

	mailCmd.AddCommand(mailReplyAllCmd)
	mailReplyAllCmd.Flags().String("mailbox", "me", "邮箱 ID（默认 me）")
	mailReplyAllCmd.Flags().String("message-id", "", "要回复的邮件 ID（必填）")
	mailReplyAllCmd.Flags().String("body", "", "回复正文（必填）")
	mailReplyAllCmd.Flags().Bool("confirm-send", false, "保存草稿后立即发送")
	mailReplyAllCmd.Flags().Bool("html", false, "强制视为 HTML body")
	mailReplyAllCmd.Flags().Bool("plain-text", false, "强制视为纯文本")
	mailReplyAllCmd.Flags().StringP("output", "o", "", "输出格式（json）")
	mailReplyAllCmd.Flags().String("user-access-token", "", "User Access Token（覆盖登录态）")
	mustMarkFlagRequired(mailReplyAllCmd, "message-id", "body")
}

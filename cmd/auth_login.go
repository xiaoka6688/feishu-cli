package cmd

import (
	"fmt"
	"os"
	"strings"

	"github.com/xiaoka6688/feishu-cli/internal/auth"
	"github.com/xiaoka6688/feishu-cli/internal/client"
	"github.com/xiaoka6688/feishu-cli/internal/config"
	"github.com/spf13/cobra"
)

var authLoginCmd = &cobra.Command{
	Use:   "login",
	Short: "登录授权（获取 User Access Token）",
	Long: `通过 OAuth 2.0 Device Flow（RFC 8628）完成用户授权。

无需在飞书开放平台配置任何重定向 URL 白名单。终端显示用户码和验证链接，
用户在任意浏览器打开链接输入用户码完成授权，命令自动轮询等待结果。

Token 保存位置: ~/.feishu-cli/token.json

示例:
  # 标准登录（交互终端下可按提示选择授权域）
  feishu-cli auth login

  # JSON 输出模式（AI Agent 推荐：run_in_background + 读 stdout 事件流）
  feishu-cli auth login --domain search --recommend --json

  # 按需申请明确的 scope
  feishu-cli auth login --scope "minutes:minutes.basic:read minutes:minutes:readonly minutes:minute:download minutes:minutes.transcript:export"

  # 按业务域申请推荐权限
  feishu-cli auth login --domain vc --domain minutes --recommend

  # 两步模式第一步：只请求 device_code 并输出，不启动轮询
  feishu-cli auth login --domain vc --domain minutes --recommend --no-wait --json

  # 两步模式第二步：用已有的 device_code 继续轮询
  feishu-cli auth login --device-code <device_code> --json`,
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := config.Validate(); err != nil {
			return err
		}

		cfg := config.Get()
		jsonOutput, _ := cmd.Flags().GetBool("json")
		noWait, _ := cmd.Flags().GetBool("no-wait")
		deviceCode, _ := cmd.Flags().GetString("device-code")
		scopeFlag, _ := cmd.Flags().GetString("scope")
		domainFlags, _ := cmd.Flags().GetStringSlice("domain")
		recommend, _ := cmd.Flags().GetBool("recommend")

		return runDeviceFlow(cfg, jsonOutput, deviceCode, noWait, scopeFlag, domainFlags, recommend)
	},
}

// runDeviceFlow 执行 Device Flow 授权（RFC 8628）。
//
// 根据 deviceCode / noWait 参数触发四种行为：默认阻塞轮询；--json 事件流；
// --no-wait 立即返回 device_code 不轮询；--device-code 复用已有 device_code 继续轮询。
func runDeviceFlow(cfg *config.Config, jsonOutput bool, deviceCode string, noWait bool, requestedScope string, domainFlags []string, recommend bool) error {
	appID := cfg.AppID
	appSecret := cfg.AppSecret
	baseURL := cfg.BaseURL

	var deviceResp *auth.DeviceAuthResponse

	if deviceCode != "" {
		if requestedScope != "" || len(domainFlags) > 0 || recommend || noWait {
			return fmt.Errorf("--device-code 模式下不能再同时传 --scope、--domain、--recommend 或 --no-wait")
		}
		cachedScope, err := loadLoginRequestedScope(deviceCode)
		if err != nil {
			return err
		}
		requestedScope = cachedScope
		deviceResp = &auth.DeviceAuthResponse{
			DeviceCode: deviceCode,
			Interval:   5,
			ExpiresIn:  180,
		}
	} else {
		resolvedScope, err := resolveRequestedScope(requestedScope, domainFlags, recommend, jsonOutput)
		if err != nil {
			return err
		}
		requestedScope = resolvedScope

		resp, err := auth.RequestDeviceAuthorization(appID, appSecret, baseURL, requestedScope)
		if err != nil {
			return err
		}
		deviceResp = resp

		if jsonOutput || noWait {
			event := map[string]any{
				"event":                     "device_authorization",
				"verification_uri":          deviceResp.VerificationURI,
				"verification_uri_complete": deviceResp.VerificationURIComplete,
				"user_code":                 deviceResp.UserCode,
				"device_code":               deviceResp.DeviceCode,
				"expires_in":                deviceResp.ExpiresIn,
				"interval":                  deviceResp.Interval,
				"requested_scope":           requestedScope,
				"requested_scopes":          auth.UniqueScopeList(requestedScope),
			}
			if err := printJSONLine(event); err != nil {
				return err
			}
		} else {
			printDeviceAuthHuman(deviceResp)
			_ = auth.TryOpenBrowser(bestVerificationURL(deviceResp))
		}

		if noWait {
			if err := saveLoginRequestedScope(deviceResp.DeviceCode, requestedScope); err != nil && cfg.Debug {
				fmt.Fprintf(os.Stderr, "[Debug] 保存 auth login requested_scope 失败: %v\n", err)
			}
			return nil
		}
	}

	// 步骤二：轮询 token 端点。
	onTick := func(elapsed, total int) {
		if jsonOutput {
			return
		}
		fmt.Fprintf(os.Stderr, "\r  轮询中... 已等待 %ds / %ds", elapsed, total)
	}
	token, err := auth.PollDeviceToken(
		appID, appSecret, baseURL,
		deviceResp.DeviceCode, deviceResp.Interval, deviceResp.ExpiresIn,
		onTick,
	)
	if !jsonOutput {
		fmt.Fprintln(os.Stderr)
	}
	if err != nil {
		if deviceCode != "" {
			_ = removeLoginRequestedScope(deviceCode)
		}
		return err
	}
	if deviceCode != "" {
		_ = removeLoginRequestedScope(deviceCode)
	}

	if err := auth.SaveToken(token); err != nil {
		return err
	}

	if err := refreshCurrentUserCache(token.AccessToken, cfg.Debug); err != nil && cfg.Debug {
		fmt.Fprintf(os.Stderr, "[Debug] 更新当前登录用户缓存失败: %v\n", err)
	}

	summary := buildLoginScopeSummary(requestedScope, token.Scope)
	if jsonOutput {
		return printJSONLine(buildAuthorizationCompleteEvent(token, summary))
	}

	printTokenSuccess(token, summary)
	return nil
}

// resolveRequestedScope 解析 auth login 要申请的 scope。
//
// 规则：
//   - --scope 与 --domain/--recommend 互斥
//   - 非交互模式下必须显式指定授权范围
//   - 交互终端下可通过简易提示选择 domain + recommended/all
//   - 始终自动追加最小核心 scope，确保后续可识别当前登录用户
func resolveRequestedScope(scope string, domainFlags []string, recommend bool, jsonOutput bool) (string, error) {
	scope = auth.NormalizeScopeList(scope)
	domains, err := auth.ParseScopeDomains(domainFlags)
	if err != nil {
		return "", err
	}
	if scope != "" && (len(domains) > 0 || recommend) {
		return "", fmt.Errorf("--scope 不能与 --domain 或 --recommend 同时使用")
	}

	if scope == "" && len(domains) == 0 && !recommend {
		if !jsonOutput && canPromptLoginScope() {
			selection, err := runInteractiveLoginScopePrompt()
			if err != nil {
				return "", err
			}
			domains = selection.Domains
			recommend = selection.Recommend
		} else {
			return "", fmt.Errorf("请通过 --scope 或 --domain/--recommend 指定授权范围，例如：feishu-cli auth login --domain search --recommend")
		}
	}

	var requested []string
	switch {
	case scope != "":
		requested = auth.UniqueScopeList(scope)
	case recommend && len(domains) == 0:
		requested, err = auth.CollectDomainScopes(auth.KnownScopeDomainNames(), true)
	case len(domains) > 0:
		requested, err = auth.CollectDomainScopes(domains, recommend)
	default:
		err = fmt.Errorf("未解析出任何授权范围，请显式指定 --scope 或 --domain")
	}
	if err != nil {
		return "", err
	}

	requested = auth.MergeScopeLists(auth.DefaultLoginScopeList(), requested)
	if len(requested) == 0 {
		return "", fmt.Errorf("未解析出任何 scope")
	}
	return strings.Join(requested, " "), nil
}

// bestVerificationURL 优先返回 VerificationURIComplete，否则回退到 VerificationURI。
func bestVerificationURL(resp *auth.DeviceAuthResponse) string {
	if resp.VerificationURIComplete != "" {
		return resp.VerificationURIComplete
	}
	return resp.VerificationURI
}

// printDeviceAuthHuman 把设备授权信息按人类友好格式打印到 stderr。
func printDeviceAuthHuman(resp *auth.DeviceAuthResponse) {
	fmt.Fprintln(os.Stderr, "\n请在浏览器中完成以下操作:")
	fmt.Fprintln(os.Stderr, "─────────────────────────────────────────────")
	fmt.Fprintf(os.Stderr, "  1. 打开链接: %s\n", resp.VerificationURI)
	fmt.Fprintf(os.Stderr, "  2. 输入用户码: %s\n", formatUserCode(resp.UserCode))
	fmt.Fprintln(os.Stderr, "─────────────────────────────────────────────")
	if resp.VerificationURIComplete != "" && resp.VerificationURIComplete != resp.VerificationURI {
		fmt.Fprintf(os.Stderr, "\n或直接访问完整链接（含用户码）:\n  %s\n", resp.VerificationURIComplete)
	}
	fmt.Fprintf(os.Stderr, "\n等待授权（%d 秒后过期）...\n", resp.ExpiresIn)
}

// formatUserCode 将 8 位无分隔符的用户码格式化为 ABCD-EFGH。
func formatUserCode(code string) string {
	if strings.ContainsAny(code, "-_ ") {
		return code
	}
	if len(code) == 8 {
		return code[:4] + "-" + code[4:]
	}
	return code
}

func refreshCurrentUserCache(userAccessToken string, debug bool) error {
	info, err := client.GetCurrentUserInfo(userAccessToken)
	if err != nil {
		return err
	}

	cache := &auth.CurrentUserCache{
		OpenID:           info.OpenID,
		UserID:           info.UserID,
		UnionID:          info.UnionID,
		Name:             info.Name,
		TokenFingerprint: auth.UserTokenFingerprint(userAccessToken),
	}
	if debug {
		fmt.Fprintf(os.Stderr, "[Debug] 当前登录用户: %s (%s)\n", info.Name, info.OpenID)
	}
	return auth.SaveCurrentUserCache(cache)
}

func init() {
	authCmd.AddCommand(authLoginCmd)

	authLoginCmd.Flags().Bool("json", false, "JSON 输出模式（AI Agent 友好，事件流写入 stdout）")
	authLoginCmd.Flags().Bool("no-wait", false, "只请求 device_code 并立即输出，不启动轮询（两步模式第一步）")
	authLoginCmd.Flags().String("device-code", "", "用已有的 device_code 继续轮询（两步模式第二步）")
	authLoginCmd.Flags().String("scope", "", "本次登录显式申请的 user scope（空格分隔）")
	authLoginCmd.Flags().StringSlice("domain", nil, fmt.Sprintf("按业务域申请授权（可重复或逗号分隔，可选: %s, all）", strings.Join(auth.KnownScopeDomainNames(), ", ")))
	authLoginCmd.Flags().Bool("recommend", false, "仅申请推荐 scope；可单独使用（对全部业务域）或与 --domain 搭配")
}

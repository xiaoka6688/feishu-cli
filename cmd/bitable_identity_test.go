package cmd

import (
	"strings"
	"testing"

	"github.com/spf13/cobra"
)

// newIdentityTestCmd 构造一个带 --as / --user-access-token 的命令，
// 模拟 bitable 子命令（--as 来自命令组 persistent flag，--user-access-token 来自子命令）。
func newIdentityTestCmd() *cobra.Command {
	c := &cobra.Command{Use: "x"}
	c.Flags().String("as", "auto", "")
	c.Flags().String("user-access-token", "", "")
	return c
}

// TestResolveIdentityTokenBot 验证 --as bot/tenant/app 都返回空 token（即走 Tenant/App Token），
// 且不依赖登录状态——这是修复 cron 无人值守抓 bitable 的核心路径。
func TestResolveIdentityTokenBot(t *testing.T) {
	for _, as := range []string{"bot", "tenant", "app", "BoT", " Bot "} {
		c := newIdentityTestCmd()
		if err := c.Flags().Set("as", as); err != nil {
			t.Fatalf("set --as=%q: %v", as, err)
		}
		token, err := resolveIdentityToken(c)
		if err != nil {
			t.Errorf("--as %q 不应报错: %v", as, err)
		}
		if token != "" {
			t.Errorf("--as %q 应返回空 token（走 Tenant Token），得到 %q", as, token)
		}
	}
}

// TestResolveIdentityTokenExplicitUser 验证显式传入 --user-access-token 时，
// auto 与 user 两种身份都原样返回该 token（不依赖 token.json / 网络）。
func TestResolveIdentityTokenExplicitUser(t *testing.T) {
	const fake = "u-fake-explicit-token"
	for _, as := range []string{"auto", "user", ""} {
		c := newIdentityTestCmd()
		if err := c.Flags().Set("as", as); err != nil {
			t.Fatalf("set --as=%q: %v", as, err)
		}
		if err := c.Flags().Set("user-access-token", fake); err != nil {
			t.Fatalf("set --user-access-token: %v", err)
		}
		token, err := resolveIdentityToken(c)
		if err != nil {
			t.Errorf("--as %q + 显式 token 不应报错: %v", as, err)
		}
		if token != fake {
			t.Errorf("--as %q 应原样返回显式 token %q，得到 %q", as, fake, token)
		}
	}
}

// TestResolveIdentityTokenInvalid 验证非法 --as 取值直接报错。
func TestResolveIdentityTokenInvalid(t *testing.T) {
	c := newIdentityTestCmd()
	if err := c.Flags().Set("as", "nobody"); err != nil {
		t.Fatalf("set --as: %v", err)
	}
	_, err := resolveIdentityToken(c)
	if err == nil {
		t.Fatal("非法 --as 应报错")
	}
	if !strings.Contains(err.Error(), "bot|user|auto") {
		t.Errorf("错误信息应提示合法取值，得到: %v", err)
	}
}

// TestBitableAsFlagRegistered 验证 bitable 命令组注册了 persistent --as flag、默认 auto，
// 且能被子命令继承（这是改造的入口，必须保证存在）。
func TestBitableAsFlagRegistered(t *testing.T) {
	f := bitableCmd.PersistentFlags().Lookup("as")
	if f == nil {
		t.Fatal("bitable 命令组缺少 persistent --as flag")
	}
	if f.DefValue != "auto" {
		t.Errorf("--as 默认值应为 auto，得到 %q", f.DefValue)
	}

	// 子命令应能通过 InheritedFlags 看到 --as。
	if len(bitableCmd.Commands()) == 0 {
		t.Skip("bitable 无子命令，跳过继承检查")
	}
	sub := bitableCmd.Commands()[0]
	if sub.InheritedFlags().Lookup("as") == nil {
		t.Errorf("子命令 %q 未继承 --as flag", sub.Name())
	}
}

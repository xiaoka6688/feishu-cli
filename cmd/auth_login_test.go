package cmd

import (
	"testing"
)

// TestFormatUserCode 测试 Device Flow 用户码格式化
func TestFormatUserCode(t *testing.T) {
	cases := []struct {
		input string
		want  string
	}{
		{"ABCD1234", "ABCD-1234"},
		{"ABCD-1234", "ABCD-1234"},
		{"ABC", "ABC"},
		{"ABCDEFGHIJ", "ABCDEFGHIJ"},
	}
	for _, c := range cases {
		got := formatUserCode(c.input)
		if got != c.want {
			t.Errorf("formatUserCode(%q) = %q, want %q", c.input, got, c.want)
		}
	}
}

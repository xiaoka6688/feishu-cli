package main

import (
	"github.com/xiaoka6688/feishu-cli/cmd"
)

// Version information, set by ldflags during build
var (
	Version   = "dev"
	BuildTime = "unknown"
)

func main() {
	cmd.SetVersionInfo(Version, BuildTime)
	cmd.Execute()
}

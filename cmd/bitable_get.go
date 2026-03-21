package cmd

import (
	"fmt"

	"github.com/riba2534/feishu-cli/internal/client"
	"github.com/spf13/cobra"
)

var bitableGetCmd = &cobra.Command{
	Use:   "get <app_token>",
	Short: "获取多维表格信息",
	Long:  "获取多维表格的元数据信息",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		appToken := args[0]
		output, _ := cmd.Flags().GetString("output")
		userToken := resolveOptionalUserToken(cmd)

		app, err := client.GetBitableApp(appToken, userToken)
		if err != nil {
			return err
		}

		if output == "json" {
			return printJSON(app)
		}

		fmt.Printf("App Token: %s\n", app.AppToken)
		fmt.Printf("名称: %s\n", app.Name)
		if app.URL != "" {
			fmt.Printf("URL: %s\n", app.URL)
		}
		fmt.Printf("版本: %d\n", app.Revision)
		return nil
	},
}

func init() {
	bitableCmd.AddCommand(bitableGetCmd)

	bitableGetCmd.Flags().StringP("output", "o", "text", "输出格式: text, json")
	bitableGetCmd.Flags().String("user-access-token", "", "User Access Token（可选）")
}

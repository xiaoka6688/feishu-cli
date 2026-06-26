package cmd

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/xiaoka6688/feishu-cli/internal/client"
	"github.com/xiaoka6688/feishu-cli/internal/config"
	"github.com/spf13/cobra"
)

var driveUploadCmd = &cobra.Command{
	Use:   "upload",
	Short: "上传本地文件到云盘（大文件自动分块）",
	Long: `上传本地文件到飞书云盘。文件 > 20MB 自动走分块上传（upload_prepare → upload_part × N → upload_finish），
每片最多重试 3 次。

必填:
  --file          本地文件路径

可选:
  --folder-token  目标文件夹 token（默认根目录）
  --name          上传后的文件名（默认本地文件名）
  --user-access-token  覆盖登录态

权限:
  - User Access Token
  - drive:file:upload

示例:
  feishu-cli drive upload --file /tmp/report.pdf
  feishu-cli drive upload --file /tmp/big.zip --folder-token fldxxx --name "大文件.zip"`,
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := config.Validate(); err != nil {
			return err
		}

		token, err := requireUserToken(cmd, "drive upload")
		if err != nil {
			return err
		}

		filePath, _ := cmd.Flags().GetString("file")
		folderToken, _ := cmd.Flags().GetString("folder-token")
		fileName, _ := cmd.Flags().GetString("name")
		output, _ := cmd.Flags().GetString("output")

		if filePath == "" {
			return fmt.Errorf("--file 必填")
		}

		stat, err := os.Stat(filePath)
		if err != nil {
			return fmt.Errorf("读取文件失败: %w", err)
		}
		if stat.IsDir() {
			return fmt.Errorf("--file 必须指向文件，不是目录")
		}

		displayName := fileName
		if displayName == "" {
			displayName = filepath.Base(filePath)
		}

		fmt.Fprintf(os.Stderr, "上传: %s (%d bytes)\n", displayName, stat.Size())

		fileToken, err := client.UploadFileWithToken(filePath, folderToken, fileName, token)
		if err != nil {
			return err
		}

		result := map[string]any{
			"file_token": fileToken,
			"file_name":  displayName,
			"size_bytes": stat.Size(),
		}

		if output == "json" {
			return printJSON(result)
		}

		fmt.Printf("文件上传成功!\n")
		fmt.Printf("  文件名:     %s\n", displayName)
		fmt.Printf("  文件 Token: %s\n", fileToken)
		fmt.Printf("  大小:       %d bytes\n", stat.Size())
		return nil
	},
}

func init() {
	driveCmd.AddCommand(driveUploadCmd)
	driveUploadCmd.Flags().String("file", "", "本地文件路径（必填）")
	driveUploadCmd.Flags().String("folder-token", "", "目标文件夹 token（默认根目录）")
	driveUploadCmd.Flags().String("name", "", "上传后的文件名（默认本地文件名）")
	driveUploadCmd.Flags().StringP("output", "o", "", "输出格式（json）")
	driveUploadCmd.Flags().String("user-access-token", "", "User Access Token（覆盖登录态）")
	mustMarkFlagRequired(driveUploadCmd, "file")
}

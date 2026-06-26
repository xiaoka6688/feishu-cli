package cmd

import (
	"fmt"
	"os"

	"github.com/xiaoka6688/feishu-cli/internal/client"
	"github.com/xiaoka6688/feishu-cli/internal/config"
	"github.com/spf13/cobra"
)

var driveMoveAllowedTypes = []string{"file", "docx", "doc", "sheet", "bitable", "mindnote", "folder", "slides"}

var driveMoveCmd = &cobra.Command{
	Use:   "move",
	Short: "移动文件/文件夹（folder 移动时轮询异步任务）",
	Long: `移动文件或文件夹到新位置。

- 文件移动：同步返回
- 文件夹移动：异步任务，自动轮询 task_check（最多 30×2s），超时返回 task_id 可用 drive task-result 继续

必填:
  --file-token     要移动的文件/文件夹 token
  --type           类型: file / docx / doc / sheet / bitable / mindnote / folder / slides

可选:
  --folder-token   目标文件夹 token（默认根目录）
  --user-access-token  覆盖登录态

权限:
  - User Access Token
  - drive:file:write

示例:
  feishu-cli drive move --file-token boxxxx --type docx --folder-token fldxxx
  feishu-cli drive move --file-token fldxxx --type folder --folder-token fldyyy`,
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := config.Validate(); err != nil {
			return err
		}

		token, err := requireUserToken(cmd, "drive move")
		if err != nil {
			return err
		}

		fileToken, _ := cmd.Flags().GetString("file-token")
		folderToken, _ := cmd.Flags().GetString("folder-token")
		fileType, _ := cmd.Flags().GetString("type")
		output, _ := cmd.Flags().GetString("output")

		if fileToken == "" {
			return fmt.Errorf("--file-token 必填")
		}
		if err := validateEnum(fileType, "--type", driveMoveAllowedTypes); err != nil {
			return err
		}

		taskID, err := client.MoveFileWithToken(fileToken, folderToken, fileType, token)
		if err != nil {
			return err
		}

		result := map[string]any{
			"file_token":   fileToken,
			"type":         fileType,
			"folder_token": folderToken,
		}

		// 文件类型无 task_id，同步完成
		if taskID == "" {
			result["ready"] = true
			if output == "json" {
				return printJSON(result)
			}
			fmt.Println("文件移动成功")
			return nil
		}

		// 文件夹类型：轮询 task_check
		result["task_id"] = taskID
		fmt.Fprintf(os.Stderr, "文件夹移动任务: %s，开始轮询...\n", taskID)

		status, timedOut, err := client.WaitDriveTaskCheckWithBound(taskID, token)
		if err != nil {
			return err
		}

		if timedOut {
			nextCmd := fmt.Sprintf("feishu-cli drive task-result --scenario task_check --task-id %s", taskID)
			result["ready"] = false
			result["timed_out"] = true
			result["next_command"] = nextCmd
			if status != nil {
				result["status"] = status.Status
			}
			if output == "json" {
				_ = printJSON(result)
			} else {
				fmt.Fprintf(os.Stderr, "移动仍在进行中，继续: %s\n", nextCmd)
			}
			return nil
		}

		result["ready"] = true
		result["status"] = status.Status
		if output == "json" {
			return printJSON(result)
		}
		fmt.Printf("文件夹移动成功 (task_id=%s, status=%s)\n", taskID, status.Status)
		return nil
	},
}

func init() {
	driveCmd.AddCommand(driveMoveCmd)
	driveMoveCmd.Flags().String("file-token", "", "要移动的文件/文件夹 token（必填）")
	driveMoveCmd.Flags().String("type", "", "类型: file/docx/doc/sheet/bitable/mindnote/folder/slides（必填）")
	driveMoveCmd.Flags().String("folder-token", "", "目标文件夹 token（默认根目录）")
	driveMoveCmd.Flags().StringP("output", "o", "", "输出格式（json）")
	driveMoveCmd.Flags().String("user-access-token", "", "User Access Token（覆盖登录态）")
	mustMarkFlagRequired(driveMoveCmd, "file-token", "type")
}

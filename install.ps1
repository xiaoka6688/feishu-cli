# install.ps1 - Windows 一键安装 feishu-cli + lark-cli
#
# 用法（PowerShell）:
#   iwr -useb https://raw.githubusercontent.com/.../install.ps1 | iex
#   或本地运行：
#   .\install.ps1
#
# 功能：
#   1. 检查 Go 和 Node.js 环境
#   2. 安装 feishu-cli（从 GitHub release）
#   3. 安装 lark-cli（从 npm）
#   4. 配置飞书应用凭证（手动输入或环境变量）
#   5. 跑 doctor 验证
#
# 作者：feishu-cli 部署实战
# 日期：2026-06-26

#Requires -Version 5.0

# 设置错误处理
$ErrorActionPreference = "Stop"

# 颜色输出
function Write-Step($msg) { Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $msg" -ForegroundColor Cyan }
function Write-OK($msg)    { Write-Host "  ✓ $msg" -ForegroundColor Green }
function Write-Warn($msg)  { Write-Host "  ⚠ $msg" -ForegroundColor Yellow }
function Write-Err($msg)   { Write-Host "  ✗ $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "========================================" -ForegroundColor Magenta
Write-Host "  飞书 CLI 一键安装脚本 (Windows)" -ForegroundColor Magenta
Write-Host "========================================" -ForegroundColor Magenta
Write-Host ""

# ============================================
# 1. 检查 Go
# ============================================
Write-Step "[1/5] 检查 Go 环境..."
$goCmd = Get-Command go -ErrorAction SilentlyContinue
if ($goCmd) {
    $goVersion = (& go version) -replace "go version ", "" -replace " .*", ""
    Write-OK "Go 已安装: $goVersion"
} else {
    Write-Err "Go 未安装"
    Write-Host "  请访问 https://go.dev/dl/ 下载安装 Go 1.21+"
    Write-Host "  安装后重新运行此脚本"
    exit 1
}

# ============================================
# 2. 安装 feishu-cli
# ============================================
Write-Step "[2/5] 安装 feishu-cli（开源第三方）..."

# 检测是否已装
$feishuPath = Get-Command feishu-cli -ErrorAction SilentlyContinue
if ($feishuPath) {
    $currentVersion = (& feishu-cli --version 2>$null)
    Write-OK "feishu-cli 已安装: $currentVersion"
    Write-OK "路径: $($feishuPath.Path)"
} else {
    Write-Host "  → 用 go install 安装最新版本..."
    try {
        & go install github.com/riba2534/feishu-cli@latest
        Write-OK "feishu-cli 安装成功"

        # 把 $GOPATH/bin 加入 PATH（当前会话）
        $goBin = (& go env GOPATH) + "\bin"
        $env:Path += ";$goBin"
        Write-OK "已临时加入 PATH: $goBin"

        # 提示永久加入
        $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
        if ($userPath -notlike "*$goBin*") {
            Write-Warn "建议把 $goBin 加入系统 PATH（永久生效）"
        }
    } catch {
        Write-Err "feishu-cli 安装失败: $_"
        exit 1
    }
}

# ============================================
# 3. 安装 lark-cli
# ============================================
Write-Step "[3/5] 安装 lark-cli（飞书官方）..."

$larkPath = Get-Command lark-cli -ErrorAction SilentlyContinue
if ($larkPath) {
    $currentVersion = (& lark-cli --version 2>$null)
    Write-OK "lark-cli 已安装: $currentVersion"
    Write-OK "路径: $($larkPath.Path)"
} else {
    $npmCmd = Get-Command npm -ErrorAction SilentlyContinue
    if (-not $npmCmd) {
        Write-Err "npm 未安装，无法装 lark-cli"
        Write-Host "  请先安装 Node.js: https://nodejs.org/"
        exit 1
    }

    Write-Host "  → 用 npm install -g 安装..."
    try {
        & npm install -g @larksuite/cli
        Write-OK "lark-cli 安装成功"
    } catch {
        Write-Err "lark-cli 安装失败: $_"
        exit 1
    }
}

# ============================================
# 4. 配置飞书凭证
# ============================================
Write-Step "[4/5] 配置飞书应用凭证..."

$envFile = "$HOME\.feishu-cli-env.ps1"
$env:FEISHU_APP_ID = $env:FEISHU_APP_ID
$env:FEISHU_APP_SECRET = $env:FEISHU_APP_SECRET

if ($env:FEISHU_APP_ID -and $env:FEISHU_APP_SECRET) {
    Write-OK "已检测到环境变量 FEISHU_APP_ID / FEISHU_APP_SECRET"
    Write-OK "App ID: $($env:FEISHU_APP_ID.Substring(0, [Math]::Min(10, $env:FEISHU_APP_ID.Length)))..."
} else {
    Write-Warn "未检测到环境变量 FEISHU_APP_ID / FEISHU_APP_SECRET"
    Write-Host ""
    Write-Host "  两种配置方式（选一）：" -ForegroundColor Yellow
    Write-Host "  A) 推荐：环境变量（不写文件）" -ForegroundColor Yellow
    Write-Host "     `$env:FEISHU_APP_ID = 'cli_xxx'" -ForegroundColor Gray
    Write-Host "     `$env:FEISHU_APP_SECRET = '你的secret'" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  B) 配置文件" -ForegroundColor Yellow
    Write-Host "     feishu-cli config init  # 手动填" -ForegroundColor Gray
    Write-Host ""

    $choice = Read-Host "  现在手动输入凭证？(y/N)"
    if ($choice -eq "y" -or $choice -eq "Y") {
        $appId = Read-Host "  App ID (cli_开头)"
        $appSecret = Read-Host "  App Secret" -AsSecureString
        $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($appSecret)
        $plainSecret = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)

        $env:FEISHU_APP_ID = $appId
        $env:FEISHU_APP_SECRET = $plainSecret

        # 写入用户级环境变量（永久）
        [Environment]::SetEnvironmentVariable("FEISHU_APP_ID", $appId, "User")
        [Environment]::SetEnvironmentVariable("FEISHU_APP_SECRET", $plainSecret, "User")
        Write-OK "凭证已写入用户环境变量（永久生效）"
    } else {
        Write-Warn "跳过凭证配置，feishu-cli 将无法调用飞书 API"
    }
}

# ============================================
# 5. 验证
# ============================================
Write-Step "[5/5] 验证安装..."

Write-Host ""
& feishu-cli --version
& feishu-cli doctor
Write-Host ""

# ============================================
# 完成
# ============================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  安装完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "📚 下一步：" -ForegroundColor Cyan
Write-Host "  1. 跑 feishu-cli doctor 验证健康"
Write-Host "  2. 创建/获取飞书 App: https://open.feishu.cn/app"
Write-Host "  3. 开通权限后跑: feishu-cli doc create --title '测试'"
Write-Host "  4. 阅读完整文档: 项目分析报告.md"
Write-Host ""
Write-Host "💡 推荐配合 Obsidian 使用：" -ForegroundColor Cyan
Write-Host "  - 下载飞书文档到本地: lark-cli docs +fetch --doc <token> --as user"
Write-Host "  - 转换为 Obsidian 格式: python feishu2obsidian.py xxx.md"
Write-Host ""

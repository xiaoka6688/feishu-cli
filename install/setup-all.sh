#!/bin/bash
# setup-all.sh - Linux/macOS 一键安装 feishu-cli + lark-cli
#
# 用法:
#   ./setup-all.sh
#   或: bash <(curl -fsSL https://raw.githubusercontent.com/.../setup-all.sh)
#
# 功能：
#   1. 检查 Go 和 Node.js 环境
#   2. 安装 feishu-cli（开源第三方，GitHub: riba2534/feishu-cli）
#   3. 安装 lark-cli（飞书官方，npm: @larksuite/cli）
#   4. 配置飞书应用凭证
#   5. 跑 doctor 验证
#
# 作者：feishu-cli 部署实战
# 日期：2026-06-26
# 配套文档：项目分析报告.md / 飞书+Obsidian 互通指南.md

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

step() { echo -e "${CYAN}[$(date +%H:%M:%S)] $1${NC}"; }
ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }
err()  { echo -e "  ${RED}✗${NC} $1"; }

echo ""
echo -e "${MAGENTA}========================================${NC}"
echo -e "${MAGENTA}  飞书双 CLI 一键安装脚本 (Linux/macOS)${NC}"
echo -e "${MAGENTA}========================================${NC}"
echo ""
echo "本脚本会安装："
echo "  1. feishu-cli (开源第三方)  - https://github.com/riba2534/feishu-cli"
echo "  2. lark-cli   (飞书官方)    - https://open.feishu.cn/document/.../feishu-cli-installation-guide"
echo ""

# ============================================
# 1. 检查 Go
# ============================================
step "[1/6] 检查 Go 环境..."
if command -v go &> /dev/null; then
    GO_VERSION=$(go version | awk '{print $3}' | sed 's/go//')
    ok "Go 已安装: $GO_VERSION"
else
    err "Go 未安装"
    echo ""
    echo "  请先安装 Go 1.21+："
    echo "    macOS:   brew install go"
    echo "    Ubuntu:  sudo apt install golang-go"
    echo "    其他:    https://go.dev/dl/"
    exit 1
fi

# ============================================
# 2. 安装 feishu-cli
# ============================================
step "[2/6] 安装 feishu-cli（开源第三方）..."

if command -v feishu-cli &> /dev/null; then
    CURRENT_VERSION=$(feishu-cli --version 2>/dev/null)
    ok "feishu-cli 已安装: $CURRENT_VERSION"
    ok "路径: $(which feishu-cli)"
else
    echo "  → 用 go install 安装最新版本..."
    go install github.com/riba2534/feishu-cli@latest
    ok "feishu-cli 安装成功"

    # 把 GOPATH/bin 加入 PATH
    GOPATH_BIN=$(go env GOPATH)/bin
    if [[ ":$PATH:" != *":$GOPATH_BIN:"* ]]; then
        warn "请把 $GOPATH_BIN 加入 PATH（永久生效）："
        echo "    echo 'export PATH=\$PATH:$GOPATH_BIN' >> ~/.bashrc"
        echo "    source ~/.bashrc"
    fi
fi

# ============================================
# 3. 安装 lark-cli
# ============================================
step "[3/6] 安装 lark-cli（飞书官方）..."

if command -v lark-cli &> /dev/null; then
    CURRENT_VERSION=$(lark-cli --version 2>/dev/null)
    ok "lark-cli 已安装: $CURRENT_VERSION"
    ok "路径: $(which lark-cli)"
else
    if ! command -v npm &> /dev/null; then
        err "npm 未安装，无法装 lark-cli"
        echo ""
        echo "  请先安装 Node.js："
        echo "    macOS:   brew install node"
        echo "    Ubuntu:  sudo apt install nodejs npm"
        echo "    其他:    https://nodejs.org/"
        exit 1
    fi

    echo "  → 用 npm install -g 安装..."
    npm install -g @larksuite/cli
    ok "lark-cli 安装成功"
fi

# ============================================
# 4. 安装 Obsidian 转换脚本
# ============================================
step "[4/6] 安装 feishu2obsidian.py（飞书→Obsidian 转换）..."

# 检测 Python
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PY_VERSION=$(python --version 2>&1 | awk '{print $2}')
    if [[ "$PY_VERSION" == 3.* ]]; then
        PYTHON_CMD="python"
    fi
fi

if [ -z "$PYTHON_CMD" ]; then
    warn "Python 3 未找到，跳过 feishu2obsidian.py 安装"
    warn "Obsidian 互通功能需要 Python 3.6+"
else
    ok "Python 3 已安装: $($PYTHON_CMD --version)"

    # 下载或复制 feishu2obsidian.py
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    if [ -f "$SCRIPT_DIR/feishu2obsidian.py" ]; then
        cp "$SCRIPT_DIR/feishu2obsidian.py" /usr/local/bin/feishu2obsidian
        chmod +x /usr/local/bin/feishu2obsidian
        ok "feishu2obsidian.py 已安装到 /usr/local/bin/"
    else
        warn "未找到 feishu2obsidian.py（请从项目目录复制）"
    fi
fi

# ============================================
# 5. 配置飞书凭证
# ============================================
step "[5/6] 配置飞书应用凭证..."

if [ -n "$FEISHU_APP_ID" ] && [ -n "$FEISHU_APP_SECRET" ]; then
    ok "已检测到环境变量 FEISHU_APP_ID / FEISHU_APP_SECRET"
    ok "App ID: ${FEISHU_APP_ID:0:10}..."
else
    warn "未检测到环境变量 FEISHU_APP_ID / FEISHU_APP_SECRET"
    echo ""
    echo -e "  ${YELLOW}两种配置方式（选一）：${NC}"
    echo -e "  ${YELLOW}A) 推荐：环境变量（不写文件）${NC}"
    echo "     export FEISHU_APP_ID='cli_xxx'"
    echo "     export FEISHU_APP_SECRET='你的secret'"
    echo ""
    echo -e "  ${YELLOW}B) 配置文件${NC}"
    echo "     feishu-cli config init  # 手动填"
    echo ""

    read -p "  现在手动输入凭证？(y/N) " choice
    if [[ "$choice" == "y" || "$choice" == "Y" ]]; then
        read -p "  App ID (cli_开头): " app_id
        read -s -p "  App Secret: " app_secret
        echo ""

        export FEISHU_APP_ID="$app_id"
        export FEISHU_APP_SECRET="$app_secret"

        # 写入 ~/.bashrc（永久）
        BASHRC="$HOME/.bashrc"
        if [ -f "$BASHRC" ]; then
            echo "" >> "$BASHRC"
            echo "# feishu-cli 凭证（自动添加 by setup-all.sh）" >> "$BASHRC"
            echo "export FEISHU_APP_ID=\"$app_id\"" >> "$BASHRC"
            echo "export FEISHU_APP_SECRET=\"$app_secret\"" >> "$BASHRC"
            ok "凭证已写入 $BASHRC（永久生效）"
        fi
    else
        warn "跳过凭证配置，feishu-cli 将无法调用飞书 API"
    fi
fi

# ============================================
# 6. 验证
# ============================================
step "[6/6] 验证安装..."

echo ""
echo "=== feishu-cli ==="
feishu-cli --version
echo ""
echo "=== lark-cli ==="
lark-cli --version
echo ""
echo "=== feishu-cli doctor ==="
feishu-cli doctor
echo ""

# ============================================
# 完成
# ============================================
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  安装完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${CYAN}📚 下一步：${NC}"
echo "  1. 创建/获取飞书 App: https://open.feishu.cn/app"
echo "  2. 开通权限（必开 docx + drive）"
echo "  3. 跑 feishu-cli doc create --title '测试' 验证"
echo "  4. 阅读完整文档: 项目分析报告.md"
echo ""
echo -e "${CYAN}💡 推荐配合 Obsidian 使用：${NC}"
echo "  - 下载飞书文档: lark-cli docs +fetch --doc <token> --as user"
echo "  - 转换 Obsidian: feishu2obsidian input.md -o output.md"
echo ""

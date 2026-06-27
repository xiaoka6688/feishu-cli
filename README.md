<p align="center">
  <img src="docs/logo.png" alt="feishu-cli Logo" width="120" />
</p>

<h1 align="center">feishu-cli（小卡的飞书工具链）</h1>

<p align="center">
  <strong>把飞书和 Obsidian 双向打通 · Markdown ↔ 飞书文档无损转换 · 双 CLI 共存</strong>
</p>

<p align="center">
  <a href="https://github.com/xiaoka6688/feishu-cli">GitHub</a> ·
  <a href="#-快速开始">快速开始</a> ·
  <a href="#-飞书--obsidian-双向同步">飞书 ↔ Obsidian</a> ·
  <a href="TROUBLESHOOTING.md">踩坑记录</a> ·
  <a href="#-命令参考">命令参考</a>
</p>

---

## ✨ 这是什么？

**feishu-cli（小卡版）** 是一个**飞书 OpenAPI 命令行工具链**，核心目标是：

> 🎯 **打通飞书云端和 Obsidian 本地知识库，实现双向同步**

### 核心特性

- 📥 **飞书 → Obsidian**：飞书知识库文档一键下载，图片自动打包，URL 解码成可点击
- 📤 **Obsidian → 飞书**：本地写的教程一键发到飞书云端，幂等增量同步
- 🔄 **双 CLI 共存**：`feishu-cli`（开源，强在 Markdown 转换）+ `lark-cli`（官方，强在稳定）
- 🎨 **40+ 飞书块类型**无损互转：标题/列表/表格/Mermaid/PlantUML/代码/引用/Callout/...
- 🤖 **AI Agent 友好**：27 个 Skill 文件 + 完整 OpenAPI 透传
- 🚀 **零运行时依赖**：Go 编译的单文件二进制 + Python 3.6+ 转换脚本

### 仓库构成

| 部分 | 来源 | 说明 |
|------|------|------|
| `cmd/`, `internal/`, `skills/` | fork 自 [riba2534/feishu-cli](https://github.com/riba2534/feishu-cli) v1.32.0 | 核心 Go 源码（GPL 友好的 MIT 协议） |
| `feishu2obsidian.py` | **本仓库原创** | 飞书 Markdown → Obsidian 格式转换 |
| `obsidian2feishu.py` | **本仓库原创** | Obsidian → 飞书增量同步 |
| `setup-all.sh` / `install.ps1` | **本仓库原创** | 一键装双 CLI |
| `飞书+Obsidian 互通指南.md` | **本仓库原创** | 小白上手教程 |
| `项目分析报告.md` | **本仓库原创** | 详细项目分析 |

---

## 🚀 快速开始（**一次跑通**）

> ⭐ **v1.32.x 新版**：实战中积累的踩坑都已修复（View 容器、首行 `---` 误判、sheet 图片、vault 相对路径等）。**强烈建议升级到最新版**。

### 一键安装（推荐）

```bash
# 1. 克隆
git clone https://github.com/xiaoka6688/feishu-cli.git
cd feishu-cli

# 2. 一步安装（自动检查环境 + 编译 + 装 lark-cli + 写凭证 + 一次性 OAuth）
python scripts/tools/install.py

# 期间会提示输入:
#   - App ID (cli_xxx 开头)
#   - App Secret
#   - 浏览器完成 OAuth 授权（35 个 scope 一次拿全，**不需要分多次授权**）
```

> macOS / Linux 用户：用 `bash setup-all.sh`，但 OAuth 部分需手动跑 `python scripts/tools/auth_all.py`。

### 一键同步飞书 Wiki 树到 Obsidian

```bash
# 同步整棵 Wiki 树到你的 Obsidian Vault
python scripts/core/sync_feishu_to_obsidian.py --wiki "WIKI_TOKEN" --vault "G:/飞书知识库"

# 同步单个文档
python scripts/core/sync_feishu_to_obsidian.py --doc "DOC_TOKEN" --vault "G:/飞书知识库"

# 从本地 MD 同步
python scripts/core/sync_feishu_to_obsidian.py --md "本地.md" --title "标题" --vault "G:/飞书知识库"
```

**完成**！Obsidian 里直接打开 Vault 就能看到所有文档、图片、视频、表格全部对齐飞书。

### 安装验证

```bash
feishu-cli --version    # feishu-cli version dev 或 v1.32.x
lark-cli --version      # lark-cli version 1.0.x
feishu-cli doctor       # 6 项健康检查（应输出 "全部通过 ✓"）
```

### OAuth 一次拿全

升级到最新版后，**只需要授权一次**（合并了原 wiki / drive / sheets 三次授权）：

```bash
# 一步发起 + 浏览器授权 + 轮询
python scripts/tools/auth_all.py

# 或手动两步
feishu-cli auth login --no-wait --json --scope "auth:user.id:read docs:... wiki:... drive:... sheets:... (完整 35 个 scope 见 TROUBLESHOOTING.md)"
# 浏览器打开链接授权
feishu-cli auth login --device-code <DEVICE_CODE>
```

> 💡 **Token 有效期内（含自动刷新）无需重新授权**。

### 常见问题

遇到问题先看 📖 **[TROUBLESHOOTING.md](./TROUBLESHOOTING.md)** —— 这里汇总了 7 大类踩坑和一次性解决。

---

## 🎯 飞书 ↔ Obsidian 双向同步

### 1. 飞书 → Obsidian（下载）

```bash
# 1. OAuth 授权（首次用 lark-cli 必做）
lark-cli auth login --domain docs --recommend --no-wait
# 浏览器打开输出的链接 → 授权

# 2. 下载飞书文档
lark-cli docs +fetch --doc "KZNxdO5mmobeb9xZvADcgXgcn0d" --as user 2>/dev/null | \
  python -c "import json,sys; d=json.load(sys.stdin); open('note.md','w').write(d['data']['markdown'])"

# 3. 转换格式（飞书 URL 编码 → 可点击，<image> → ![]()）
python scripts/core/feishu2obsidian.py note.md -o ~/ObsidianVault/note.md \
  --title "我的笔记" \
  --source-url "https://feishu.cn/docx/KZNxdO5mmobeb9xZvADcgXgcn0d"
```

`feishu2obsidian.py` 解决的问题：
- ✅ 飞书 URL 编码（`%2F`、`%3A`、`%29`）→ 标准 URL（可点击）
- ✅ 飞书私有 `<image token="xxx"/>` → Obsidian 友好的 `![](./assets/xxx.png)` 格式
- ✅ 自动添加 YAML frontmatter（标题/创建时间/来源/标签）

### 2. Obsidian → 飞书（上传）

在你的 Obsidian 笔记 frontmatter 加上 `source: obsidian` 标记：

```markdown
---
title: 我的教程
source: obsidian          ← 必加
tags: [tutorial, feishu]
---

# 正文
```

然后跑：

```bash
# 同步整个 vault
python scripts/core/obsidian2feishu.py ~/Documents/ObsidianVault/Notes/

# 单个文件
python scripts/core/obsidian2feishu.py my-note.md

# 预览
python scripts/core/obsidian2feishu.py vault/ --dry-run

# 强制重新同步
python scripts/core/obsidian2feishu.py vault/ --force
```

同步成功后，frontmatter 会自动加上：

```markdown
---
title: 我的教程
source: obsidian
feishu_doc_id: U7OPdcQuLomo9Txptz3cgA04nWh
feishu_url: https://feishu.cn/docx/U7OPdcQuLomo9Txptz3cgA04nWh
last_synced: 2026-06-26 22:45:47
---
```

**幂等性**：第二次跑会跳过已同步的文件，不会重复上传。

---

## 📚 完整文档

- 📖 [飞书+Obsidian 互通指南.md](./飞书+Obsidian 互通指南.md) —— 小白总览（推荐先读）
- 📖 [项目分析报告.md](./项目分析报告.md) —— 详细项目分析
- 📖 [README.md 详细版](https://github.com/riba2534/feishu-cli#readme) —— 上游 feishu-cli 完整文档（继承）

---

## 🛠 适用场景

| 你是 | 推荐使用 |
|------|---------|
| 飞书重度用户，想用命令行管理 | `feishu-cli` + `lark-cli` 双 CLI |
| Obsidian 用户，想把飞书文档备份到本地 | `feishu-cli` + `feishu2obsidian.py` |
| 在 Obsidian 写教程，想同步给同事 | `feishu-cli` + `obsidian2feishu.py` |
| AI Agent（Claude Code / Cursor） | `lark-cli` (官方 AI Skill) + 27 个上游 Skill |
| 想在多台电脑同步知识库 | `./setup-all.sh` 一键部署 |

---

## 🤝 致谢

- 上游项目：[riba2534/feishu-cli](https://github.com/riba2534/feishu-cli) —— 提供 Go 核心代码
- 飞书官方：[lark-cli](https://open.feishu.cn/document/no_class/mcp-archive/feishu-cli-installation-guide) —— 官方 CLI
- 飞书 OpenAPI：https://open.feishu.cn/document

---

## 📄 License

本仓库基于 [riba2534/feishu-cli](https://github.com/riba2534/feishu-cli) 的 MIT 协议二次开发。
新增的 Python 脚本和文档同样以 MIT 协议发布。

---

<p align="center">
  <sub>由小卡（xiaoka6688）维护 · 主要目的是打通飞书和 Obsidian 知识库</sub>
</p>

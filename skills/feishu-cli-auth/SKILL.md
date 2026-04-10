---
name: feishu-cli-auth
description: >-
  飞书 OAuth 认证和 User Access Token 管理（Device Flow，RFC 8628）。
  支持一键创建飞书应用（config create-app）、批量申请权限（config add-scopes）、
  auth check 预检 scope、auth login 登录、Token 自动刷新。无需配置任何重定向 URL 白名单。
  当用户请求"登录飞书"、"获取 Token"、"OAuth 授权"、"auth login"、"认证"、
  "搜索需要什么权限"、"Token 过期了"、"刷新 Token"、"创建应用"、"create-app"、
  "申请权限"、"开通权限"、"add-scopes"、"缺少权限"、"99991672"、"99991679"时使用。
  当其他飞书技能（toolkit/msg/read 等）遇到 User Access Token 相关问题时，也应参考此技能。
user-invocable: true
allowed-tools: Bash, Read
---

# 飞书 OAuth 认证与 Token 管理

feishu-cli 通过 **OAuth 2.0 Device Flow（RFC 8628）** 获取 User Access Token，用于搜索、消息互动、审批任务查询等需要用户身份的 API。**无需在飞书开放平台配置任何重定向 URL 白名单**。

> **feishu-cli**：如尚未安装，请前往 [riba2534/feishu-cli](https://github.com/riba2534/feishu-cli) 获取安装方式。
>
> **v1.18+ 变更**：Authorization Code Flow（`--print-url` / `auth callback` / `--manual` / `--no-manual` / `--port` / `--method` / `--scopes`）已全部删除，只保留 Device Flow。旧脚本请迁移至 `auth login --json` 或 `auth login --no-wait` + `--device-code` 两步模式。

---

## 首次使用：从零开始的三步配置

如果用户从未使用过 feishu-cli，按以下顺序完成初始化。整个过程不需要手动访问飞书开放平台后台：

```bash
# 第一步：一键创建飞书应用（CLI 自动完成，无需打开浏览器后台）
feishu-cli config create-app --save

# 第二步：为应用开通权限（生成链接，浏览器点击即可）
feishu-cli config add-scopes --domain all

# 第三步：验证配置是否成功
feishu-cli doc create --title "Hello Feishu"
```

第一步通过 Device Flow 协议自动注册「个人代理应用」，`--save` 会把凭证写入配置文件。如果还需要搜索、审批等用户身份功能，额外执行：

```bash
feishu-cli auth login
```

> 下文各章节有每一步的详细说明。已有应用凭证的用户可跳过第一步。

---

## 核心概念

**Token 存储位置**：所有 OAuth Token 保存在 `~/.feishu-cli/token.json`（明文 JSON，权限 0600），包括 Access Token、Refresh Token、过期时间和授权 scope。

**两种身份**：
- **App Access Token**（应用身份）：通过 app_id/app_secret 自动获取，大多数文档操作使用此身份
- **User Access Token**（用户身份）：需 OAuth 授权，搜索、消息互动、审批任务等 API **必须**使用此身份

**Token 生命周期**：
- Access Token：**2 小时**有效
- Refresh Token：**30 天**有效（Device Flow 会强制注入 `offline_access` scope）
- 过期后自动用 Refresh Token 刷新，用户无感

**Scope 由飞书应用配置决定，不由 CLI 请求**：
- CLI 在 `auth login` 时不传任何 scope 请求参数
- 飞书 token v2 端点**忽略**客户端声明的 scope，始终返回应用在开放平台已开通的**全部** scope
- 要增减 Token 权限范围，只需通过 `feishu-cli config add-scopes` 调整应用配置，然后重新 `auth login`

---

## 人类用户授权

**一条命令通吃所有环境**——本地桌面、SSH 远程、WSL、容器都一样：

```bash
feishu-cli auth login
```

CLI 会：
1. 向飞书请求一个 `device_code` 和 `user_code`
2. 在 stderr 打印验证链接 + 用户码
3. 在本地桌面尝试自动打开浏览器（有 GUI 时成功，SSH 远程时静默失败无副作用）
4. 每 5 秒轮询一次 token 端点，直到用户完成授权

用户只需在**任意有浏览器的设备**（电脑、手机）打开链接，输入用户码或扫码即可。完成后 CLI 自动拿到 Token 并保存。

**不再需要** `--manual` / `--no-manual` / `--port` / 重定向 URL 配置等一切针对 SSH 远程/桌面差异的 workaround。

---

## AI Agent 授权约定（核心）

AI Agent（Claude Code 等）授权飞书必须遵循下面的决策链和两种技术方案之一。

### 决策链：先 auth check 再 auth login

在执行任何需要 User Access Token 的命令前，先用 `auth check` 预检：

```
需要 User Token 的任务
    ↓
feishu-cli auth check --scope "REQ_SCOPES" -o json   (exit 0 = 全部满足)
    ↓
case ok=true:                         继续执行业务命令
case error=not_logged_in:             → 启动登录流程
case error=token_expired:             → 启动登录流程
case missing=[...]:                   → 启动登录流程（顺便提示可能需要 config add-scopes）
```

AI **永远不应该**：
- 传 `--scopes` flag（已删除）
- 调 `auth callback` 命令（已删除）
- 使用 `--print-url` flag（已删除）
- 维护硬编码的 scope 列表
- 自己生成或管理 device_code
- **要求用户从浏览器地址栏复制回调 URL 回传给 AI**——这是 v1.18 前 Authorization Code Flow 的流程，已彻底删除。Device Flow 下用户只需**点击链接完成授权**，无需复制任何东西。如果 AI 引导用户"把地址栏的 URL 粘贴给我"，那是在回忆错误的旧流程

### 方案 A：run_in_background 后台阻塞（推荐）

最简洁的做法——让 `auth login --json` 阻塞轮询，AI 通过 Claude Code 的 `run_in_background: true` 把它丢到后台：

```
# 步骤 1: 后台启动登录
task = Bash(command="feishu-cli auth login --json", run_in_background=true)

# 步骤 2: 读 stdout 第一行（首次 stdout 事件）
{
  "event": "device_authorization",
  "verification_uri": "https://accounts.feishu.cn/oauth/v1/device/verify?flow_id=...",
  "verification_uri_complete": "https://accounts.feishu.cn/oauth/v1/device/verify?flow_id=...&user_code=ABCD-EFGH",
  "user_code": "ABCD-EFGH",
  "device_code": "O-NUxxxx...",
  "expires_in": 240,
  "interval": 5
}

# 步骤 3: 把 verification_uri_complete 和 user_code 展示给用户
"请在浏览器打开以下链接完成授权（4 分钟内有效）:
  https://accounts.feishu.cn/oauth/v1/device/verify?flow_id=...&user_code=ABCD-EFGH
用户码: ABCD-EFGH
授权完成后告诉我继续。"

# 步骤 4: 等后台任务自动完成通知
# 步骤 5: 读 stdout 第二行（成功事件）
{
  "event": "authorization_success",
  "expires_at": "2026-04-18T04:05:36+08:00",
  "refresh_expires_at": "2026-04-25T02:05:36+08:00",
  "scope": "auth:user.id:read search:docs:read ... offline_access"
}

# 步骤 6: 再调一次 auth check 确认，继续业务
```

### 方案 B：--no-wait / --device-code 两步模式（高级）

如果 AI Agent 需要把"请求 device_code"和"轮询 token"拆到两个独立的 Bash 调用里（比如中间有其他任务要做），用对齐官方 lark-cli 的两步模式：

```bash
# 步骤 1: 只请求 device_code，立即退出（不轮询）
feishu-cli auth login --no-wait --json
# stdout 输出一行 JSON: {"event":"device_authorization", ..., "device_code":"O-NUxxxx..."}
# 进程立即退出 0

# 步骤 2: AI 把链接展示给用户，等待用户完成授权

# 步骤 3: 用上一步的 device_code 继续轮询
feishu-cli auth login --device-code "O-NUxxxx..." --json
# 阻塞直到用户授权完成或 device_code 过期（约 3 分钟）
# 成功后 stdout 输出: {"event":"authorization_success", ...}
```

两步模式的 device_code 是第一步服务器返回的原始值，AI 需要自己管理这个字符串（通常直接传给下一步命令参数）。

> **⚠️ 这个"两步模式"≠ v1.18 前的"两步式非交互登录"**。新模式是 Device Flow 的拆分：
> - 旧两步式（已删除）：用户必须**复制**浏览器地址栏里的 `127.0.0.1:9768/callback?code=...&state=...` 回调 URL 粘贴给 AI
> - 新两步模式：用户**只点击一次链接**完成授权，**不需要复制任何 URL**。AI 只需记住第一步服务端返回的 `device_code` 字符串并传给第二步命令即可。两次 Bash 调用中间 AI 向用户索要的是"是否已完成授权"的确认，**不是回调 URL**

### 三种登录模式对比

| 维度 | 人类直接跑 | AI 方案 A（后台阻塞） | AI 方案 B（两步拆分） |
|---|---|---|---|
| 命令 | `auth login` | `auth login --json` + `run_in_background=true` | `auth login --no-wait --json` → ... → `auth login --device-code <c> --json` |
| Bash 调用次数 | 1 次（前台/后台同进程） | 1 次（后台） | 2 次（独立进程） |
| 进程阻塞 | 阻塞到授权完成 | 后台阻塞 | 第一步立即退出，第二步阻塞轮询 |
| 用户操作 | 点击链接 / 输入用户码 | 点击链接 / 输入用户码 | 点击链接 / 输入用户码 |
| 用户需要复制东西给 AI | ❌ 不需要 | ❌ 不需要 | ❌ 不需要 |
| stdout 输出 | 无（仅 stderr 人类文本） | 2 行 JSONL 事件流 | 第一步 1 行 JSON，第二步 1 行 JSON |
| AI 需要保管什么 | 无 | 无（读 stdout 即可） | 第一步返回的 `device_code` 字符串 |
| 何时选 | 人类在交互终端 | AI 有 `run_in_background` 能力（绝大多数情况） | Agent 框架没有后台任务能力；或要在两次命令之间做其他事；或要把 `device_code` 持久化到状态文件 |

---

## auth check 命令

检查当前 Token 是否包含指定 scope，专为 AI Agent 预检而设计。

```bash
feishu-cli auth check --scope "search:docs:read"
feishu-cli auth check --scope "search:docs:read im:message:readonly"
```

**输出 JSON 到 stdout**，退出码 0 表示满足，非 0 表示不满足。

### 输出字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `ok` | bool | `true` = 所有 required scope 都已授权 |
| `granted` | []string | 已包含的 scope 列表 |
| `missing` | []string | 缺失的 scope 列表 |
| `error` | string | 失败原因（`not_logged_in` / `token_expired`），仅在未登录或过期时出现 |
| `suggestion` | string | 修复建议（仅在 `ok=false` 时出现） |

### 返回状态分支

```bash
# 全部满足
{"ok":true,"granted":["search:docs:read"],"missing":null}
# exit 0

# 未登录
{"ok":false,"error":"not_logged_in","missing":["search:docs:read"],"suggestion":"feishu-cli auth login"}
# exit 1

# Token 过期（access + refresh 都失效）
{"ok":false,"error":"token_expired","missing":["search:docs:read"],"suggestion":"feishu-cli auth login"}
# exit 1

# 部分缺失
{"ok":false,"granted":["search:docs:read"],"missing":["im:message:readonly"],"suggestion":"feishu-cli config add-scopes --scopes \"im:message:readonly\" && feishu-cli auth login"}
# exit 1
```

**设计意图**：AI 只需解析 `ok` 字段决定是否继续，解析 `error` / `missing` 字段决定提示用户做什么（重新登录 or 先补 scope 再登录）。

---

## Token 状态检查

```bash
# 人类可读格式
feishu-cli auth status

# JSON 格式（AI Agent 推荐）
feishu-cli auth status -o json
```

**已登录且 Token 有效：**

```json
{
  "logged_in": true,
  "access_token_valid": true,
  "access_token_expires_at": "2026-04-11T04:05:36+08:00",
  "refresh_token_valid": true,
  "refresh_token_expires_at": "2026-04-18T02:05:36+08:00",
  "scope": "auth:user.id:read search:docs:read ... offline_access"
}
```

**未登录：**

```json
{"logged_in": false}
```

> 一般情况下 AI Agent 应该优先用 `auth check` 而不是 `auth status`，因为 `check` 直接返回"是否满足需求"。`auth status` 更适合人类用户排查。

---

## Token 自动刷新机制

搜索、消息互动、审批任务等**必须**使用 User Access Token 的命令（`resolveRequiredUserToken`）通过 `ResolveUserAccessToken()` 按以下优先级链查找。其他可选命令（`resolveOptionalUserToken`）仅检查第 1、2 项，默认使用 App Token：

1. `--user-access-token` 命令行参数
2. `FEISHU_USER_ACCESS_TOKEN` 环境变量
3. `~/.feishu-cli/token.json`：
   - access_token 有效 → 直接使用
   - access_token 过期 + refresh_token 有效 → **自动刷新并保存新 Token**
   - 都过期 → 报错"已过期，请重新登录"
4. `config.yaml` 中的 `user_access_token` 静态配置

**刷新过程对用户透明**：stderr 输出 `[自动刷新] 刷新成功...`，命令正常执行。

---

## User Access Token 的使用场景

### 必须 User Access Token 的命令

| 命令 | 典型 scope |
|---|---|
| `search docs "关键词"` | `search:docs:read` |
| `search messages "关键词"` | `search:message` |
| `search apps "关键词"` | （应用审批） |
| `msg get / list / history` | `im:message:readonly` + `im:message.group_msg:get_as_user` |
| `msg pin / unpin / pins` | `im:message.pins` |
| `msg reaction add/remove/list` | `im:message.reactions` |
| `msg delete` | `im:message` |
| `msg search-chats` | `im:chat:read` |
| `chat get / update / delete` | `im:chat:read` / `im:chat` |
| `chat member list / add / remove` | `im:chat.members:read` / `im:chat.members` |
| `approval task query` | `approval:task` |

### 可选 User Access Token 的命令（默认用 App Token）

以下命令默认使用 App Token（租户身份），仅在通过 `--user-access-token` 参数或 `FEISHU_USER_ACCESS_TOKEN` 环境变量显式指定时才使用 User Token：

| 命令 |
|---|
| `wiki get/export/nodes` |
| `calendar list/get/event-search/freebusy` |
| `task create/complete/list`、`tasklist create/list/delete` |
| `user info/search` |

### 典型检查流程

```bash
# 1. 预检 scope（AI 推荐）
feishu-cli auth check --scope "search:docs:read offline_access"
# exit 0 → 继续

# 或者 2. 手动检查登录状态（人类用户）
feishu-cli auth status -o json

# 3. 如果缺少登录或 scope，执行登录
feishu-cli auth login

# 4. 登录后，搜索命令自动从 token.json 读取 Token
feishu-cli search docs "产品需求"
```

---

## 退出登录

```bash
feishu-cli auth logout
```

删除 `~/.feishu-cli/token.json`，不影响 App Access Token（app_id/app_secret）。

---

## 排错指南

| 问题 | 诊断 | 解决 |
|------|------|------|
| `"缺少 User Access Token"` | 从未登录 | `feishu-cli auth login` |
| `"User Access Token 已过期"` | token.json 中 access + refresh 都过期 | 重新 `auth login` |
| 搜索报 `99991679 Unauthorized` | Token scope 不满足 | `auth check --scope "..."` 定位缺失，`config add-scopes` 补权限后重新 `auth login` |
| 搜索报 `99991672 Access denied` | 应用未开通所需权限 | `feishu-cli config add-scopes --domain <域>` 申请 |
| Refresh Token 为空 | 罕见：服务端未返回 refresh_token | 重新 `auth login`（CLI 强制注入 `offline_access`） |
| `"授权码已过期"` | 设备码 240 秒内未完成授权 | 重新 `auth login`，尽快完成浏览器授权 |
| `"用户拒绝了授权"` | 用户在飞书授权页点了拒绝 | 重新 `auth login`，这次点「允许」 |
| 轮询长时间卡在 `authorization_pending` | 用户还未在浏览器完成授权 | 提醒用户打开链接并输入 user_code |
| `"未登录飞书，请先运行 feishu-cli auth login"` | 未登录或 token.json 损坏 | `auth logout && auth login` |

---

## 创建飞书应用（一键自动注册）

传统方式需要用户手动访问飞书开放平台后台（open.feishu.cn）创建应用、复制凭证。`config create-app` 命令通过飞书 Device Flow 协议，在终端内自动完成整个注册过程。

### 什么是 Device Flow

Device Flow（RFC 8628）是一种 OAuth 2.0 授权方式，专为没有浏览器的设备（如 CLI 工具、智能电视）设计。核心思路：

1. CLI 向飞书服务器申请一个「用户码」和「验证链接」
2. 用户在**任意设备**的浏览器中打开链接、输入用户码（或直接扫码）完成身份验证
3. CLI 在后台轮询服务器，用户确认后自动获取凭证

因此 CLI 本身不需要嵌入浏览器，也不需要配置回调 URL。`auth login` 和 `config create-app` 都使用 Device Flow。

### 命令与参数

```bash
feishu-cli config create-app [flags]
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--save` | `false` | 创建成功后自动将 App ID 和 App Secret 写入 `~/.feishu-cli/config.yaml` |
| `--brand` | `feishu` | 目标平台：`feishu`（飞书国内版）或 `lark`（Lark 国际版） |
| `-o json` | — | 以 JSON 格式输出结果（适合脚本和 AI Agent 解析） |

### 详细流程

#### 第一步：发起注册

```bash
feishu-cli config create-app --save
```

CLI 向 `accounts.feishu.cn/oauth/v1/app/registration` 发送请求，注册类型为 `PersonalAgent`（个人代理应用）。服务器返回 `device_code` / `user_code` / `verification_uri_complete` / `expires_in`。

终端输出：
```
正在发起应用注册...

请在浏览器中打开以下链接，扫码确认创建应用:

  https://open.feishu.cn/page/cli?user_code=ABCD-EFGH

用户码: ABCD-EFGH
有效期: 300 秒

等待扫码确认...
  等待中... 5/300 秒
```

#### 第二步：用户在浏览器确认

用户打开链接后，会看到飞书的授权页面。可以通过以下两种方式确认：

- **飞书 App 扫码**：手机飞书扫描页面上的二维码
- **手动输入用户码**：在页面输入终端显示的 `user_code`

确认后，飞书会自动创建一个「个人代理应用」，应用归属于扫码确认的用户。

#### 第三步：CLI 自动获取凭证

CLI 在后台以 `interval` 秒为间隔轮询服务器。用户确认后，服务器返回 `client_id`（即 App ID）和 `client_secret`（即 App Secret）。

终端输出：
```
应用创建成功！
  App ID:     cli_a7xxxxxx
  App Secret: 0hKj****************************dF3m

已保存到配置文件
```

### `--save` 标志详解

`--save` 控制凭证的持久化方式，是新用户最推荐的用法。

**不加 `--save`**：CLI 仅在终端打印凭证，并提示用户手动配置环境变量。

**加 `--save`**：CLI 自动将 App ID 和 App Secret 写入 `~/.feishu-cli/config.yaml`，后续所有命令直接可用。

| 场景 | 行为 |
|------|------|
| 配置文件**不存在** | 创建 `~/.feishu-cli/config.yaml`，写入默认配置项 |
| 配置文件**已存在** | 仅更新 `app_id` 和 `app_secret`，**保留**其他已有配置 |
| 目录不存在 | 自动创建 `~/.feishu-cli/` 目录 |
| 文件权限 | `0600`（仅所有者可读写） |

### AI Agent 使用方式

AI Agent 在 Bash 中执行时建议用 `-o json` 获取结构化输出：

```bash
feishu-cli config create-app --save -o json
```

JSON 输出（stdout）：
```json
{
  "app_id": "cli_a7xxxxxx",
  "app_secret": "0hKjxxxxxxxxdF3m",
  "brand": "feishu"
}
```

注意：进度信息输出到 stderr，JSON 输出到 stdout。命令需要等待用户扫码，AI Agent 应将授权链接展示给用户并等待确认，或使用 `run_in_background`。

### Lark 国际版

```bash
feishu-cli config create-app --save --brand lark
```

区别仅在 API 端点（`accounts.larksuite.com`）和默认 `base_url`（`https://open.larksuite.com`）。

### 错误处理

| 错误信息 | 原因 | 解决 |
|---------|------|------|
| `应用注册失败: 请求失败` | 无法访问 `accounts.feishu.cn`，网络不通或被代理拦截 | 检查网络，配置 `HTTPS_PROXY` |
| `注册码已过期，请重试` | 用户未在 300 秒内扫码确认 | 重新执行，尽快扫码 |
| `用户拒绝了应用注册` | 用户在飞书授权页面点了「拒绝」 | 重新执行，这次点「允许」 |
| `配置保存失败` | 磁盘权限问题 | 检查 `~/.feishu-cli/` 目录权限 |

### 创建成功后的下一步

```bash
# 1. 为应用开通权限
feishu-cli config add-scopes --domain all

# 2. 验证配置
feishu-cli doc create --title "Hello Feishu"

# 3. 可选：OAuth 用户授权
feishu-cli auth login
```

---

## 为应用申请开通权限

当命令返回 `99991672 Access denied` 或 `99991679 Unauthorized` 时，说明应用缺少对应权限。使用 `config add-scopes` 批量申请：

```bash
# 按域批量申请（推荐）
feishu-cli config add-scopes --domain calendar,task,vc

# 申请所有常用权限
feishu-cli config add-scopes --domain all

# 指定具体 scope
feishu-cli config add-scopes --scopes "vc:meeting:readonly minutes:minutes:readonly"

# 只输出链接（不打开浏览器）
feishu-cli config add-scopes --domain doc,im --print-only
```

> 注意：`config add-scopes --scopes` 是**配置应用权限**的 flag（给应用添加权限到开放平台的权限列表），和已删除的 `auth login --scopes`（登录时请求 scope）**完全不同**——前者仍然保留。

### 可用的域名

| 域名 | 包含的权限 |
|------|-----------|
| `calendar` | 日历读写 |
| `task` | 任务读写 |
| `vc` | 视频会议 |
| `minutes` | 妙记 |
| `doc` | 文档/知识库/云空间 |
| `im` | 消息/群聊 |
| `bitable` | 多维表格 |
| `sheet` | 电子表格 |
| `contact` | 通讯录 |
| `search` | 搜索 |
| `export` | 导出 |
| `all` | 以上全部 |

申请完成后，需要重新 `auth login` 才能让新 scope 出现在 Token 中。

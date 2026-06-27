# 项目实战经验与踩坑记录

> 本文汇总了 feishu-cli（xiaoka6688 仓库）在"飞书 → Obsidian 知识库"同步实战中遇到的所有问题、根因、解决方案。
> 目的是让任何新用户（包括其他电脑上的你）能**一次跑通**，避免重复踩坑。

## 📑 目录

- [一、一次跑通所需的全部 OAuth scope](#一一次跑通所需的全部-oauth-scope)
- [二、7 大类问题与解决](#二七大类问题与解决)
- [三、最佳实践（推荐流程）](#三最佳实践推荐流程)
- [四、命令速查](#四命令速查)

---

## 一、一次跑通所需的全部 OAuth scope

经验：**3 次授权合并为 1 次**。原始流程要分别授权 wiki / drive / sheets 3 次，现在一次性申请以下 35 个 scope 就够所有场景用：

```bash
feishu-cli auth login --no-wait --json \
  --scope "auth:user.id:read
docs:document.comment:create
docs:document.comment:delete
docs:document.comment:read
docs:document.comment:update
docs:document.comment:write_only
docs:document.content:read
docs:document.media:download
docs:document.media:upload
docs:document:copy
docs:document:export
docs:document:import
docs:event:subscribe
docs:permission.member:auth
docs:permission.member:create
docs:permission.member:transfer
docx:document:readonly
drive:drive
drive:drive.metadata:readonly
drive:file:download
drive:file:upload
drive:file:view_record:readonly
sheets:spreadsheet
sheets:spreadsheet:readonly
space:document:delete
space:document:move
space:folder:create
wiki:member:create
wiki:member:retrieve
wiki:member:update
wiki:node:copy
wiki:node:create
wiki:node:move
wiki:node:read
wiki:node:retrieve
wiki:node:update
wiki:space:read
wiki:space:retrieve"
```

**为什么需要这些 scope**：

| 场景 | 必须 scope | 不开的话 |
|---|---|---|
| 读飞书文档 | `wiki:node:read`、`docs:document.content:read` | export-tree 直接 403 |
| 下载图片 | `docs:document.media:download`、`drive:file:download` | media-download 401/403 |
| 下载视频 | `docs:document.media:download` | 视频 401 |
| 读 sheet 表格 | `sheets:spreadsheet`、`sheets:spreadsheet:readonly` | sheet export 99991679 |
| 写文件 | `docs:document.media:upload`、`drive:file:upload` | 不能反向同步 |
| 评论/权限 | docs:document.comment:*、docs:permission.member:* | 评论、转移失败 |

> 💡 **首次安装后只授权这一次即可**。Token 有效期内（含自动刷新）无需重新授权。

---

## 二、7 大类问题与解决

### 问题 1：OAuth 反复授权 3 次

**现象**：

第一次授权只拿基础 scope，跑同步时发现 401/99991679，又跳一次授权。重复 3 次。

**根本原因**：

`feishu-cli auth login --domain X` 的 `--domain` 只预设该域最小必需 scope，跨域 scope 要重新发起授权。

**解决**：

✅ 一次申请所有 scope（见上面命令），后续 7 天内不需要再授权（Token 自动刷新）。

---

### 问题 2：飞书导出文件首行 `---` 误判 frontmatter

**现象**：

转换脚本以为首行的 `---` 已经是 YAML frontmatter，跳过添加，结果 MD 头部缺 `title`/`source` 等元信息。

**根本原因**：

`feishu2obsidian.py` 旧逻辑：```if text.startswith("---"): return text # 已有 frontmatter```

但飞书导出的 Markdown 实际**首行就是 `---`（飞书的引用块分割线）**，不是 YAML。

**解决**（`feishu2obsidian.py` 内置修复）：

```python
# 旧逻辑（错误）
if text.startswith("---"):
    return text  # 已有 frontmatter

# 新逻辑（正确）
# 飞书导出文件首行 '---' 不是 frontmatter，是分割线
# 看后续有没有配对的 '---'，有就当 metadata 剥离
lines = text.split('\n')
i = 0
while i < len(lines) and lines[i].strip() == "":
    i += 1
if i < len(lines) and lines[i].strip() == "---":
    j = i + 1
    while j < len(lines) and lines[j].strip() != "---":
        j += 1
    if j < len(lines):
        k = j + 1
        while k < len(lines) and lines[k].strip() == "":
            k += 1
        body = "\n".join(lines[k:])
    else:
        body = "\n".join(lines[i+1:])
else:
    body = text
```

---

### 问题 3：View/Grid/Callout 容器内容被丢弃

**现象**：

飞书的"对比展示"（左图右文/左视频右视频）等 View 容器整块被跳过，原飞书"23 个 View 块"在导出 MD 里变成 23 个 `<!-- 不支持的块类型: View (type=33) -->` 占位符。

**根本原因**：

`feishu-cli wiki export-tree` 的 Markdown 转换器**不递归 View 块里的 children**。

**解决**（`rebuild_md_from_blocks.py`）：

✅ 用底层 OpenAPI 拿原始块结构，**递归所有块**：

```python
def render_children(child_ids, block_map, depth, asset_dir_rel):
    out = []
    for cid in child_ids or []:
        b = block_map.get(cid)
        if not b:
            continue
        rendered = render_block(b, block_map, depth, asset_dir_rel)
        if rendered:
            out.append(rendered)
    return "\n\n".join(out)
```

支持的 block_type 完整映射：

| type | 含义 | 渲染 |
|---|---|---|
| 1 | page（根） | 递归 children |
| 2 | paragraph | text elements |
| 3/4/5 | h1/h2/h3 | `#`/`##`/`###` |
| 6-11 | heading4-9 | `####`-`#########` |
| 12 | bullet | `-` |
| 13 | ordered | `1.` |
| 14 | code | ` ``` lang` |
| 15 | quote | `> ` |
| 19 | callout | `> 💡` |
| 22 | divider | `---` |
| 23 | video | `<video src="./assets/feishu_xxx.mp4" controls>` |
| 24 | grid | 递归 children |
| 25 | grid_column | 递归 children |
| 27 | image | `![](./assets/feishu_xxx.png)` |
| 31 | table | Markdown 表格 |
| 32 | table_row | 表格行 |
| 33 | view（容器） | 递归 children |
| 34 | 旧 callout | `> 💡` |

---

### 问题 4：heading 字段名错误

**现象**：

标题渲染为 `# ` 空标题（H1 文本完全丢失）。

**根本原因**：

飞书 docx v1 API 字段是 `heading1.elements`（嵌套结构），不是 list 形式：

```json
// 错误假设
{"heading1": {"text": [{"text": "标题"}]}}

// 实际 API
{"heading1": {"elements": [{"text_run": {"content": "标题", "text_element_style": {...}}}]}}
```

**解决**（`rebuild_md_from_blocks.py`）：

```python
# 兼容新旧两种格式
def render_text_elements(text_elements):
    if isinstance(text_elements, dict):
        elements = text_elements.get("elements", [])
        # ... 处理 text_run / equation / mention_user / mention_doc
    else:
        # 旧版 list of dict
        ...
```

---

### 问题 5：资源路径硬编码为 `./assets/`，子目录 MD 100% 失败

**现象**（**最致命**）：

Obsidian 打开后显示"找不到 `./assets/数字人短视频系统实操手册(小程序)/feishu_xxx.png`"。**14 个子目录 MD 全部 100% 解析失败，300 个引用失效**。

**根本原因**：

`rebuild_md_from_blocks.py` 写路径时硬编码 `./assets/...`，**没有根据 MD 实际所在目录调整 `../` 层级**。Obsidian 严格按 MD 所在目录解析相对路径：

| MD 位置 | 写 `./assets/foo.png` 后 Obsidian 解析为 | 实际文件在 | 结果 |
|---|---|---|---|
| 根 `AI数字人 使用手册.md` | `assets/foo.png` | `assets/foo.png` | ✅ OK |
| `数字人短视频系统实操手册(小程序)/数字人短视频系统操作手册（PC端）.md` | `数字人短视频系统实操手册(小程序)/数字人短视频系统操作手册（PC端）/assets/数字人短视频系统实操手册(小程序)/foo.png` | `assets/数字人短视频系统实操手册(小程序)/foo.png` | ❌ 找不到 |

**解决**（`fix_md_asset_paths.py` + `rebuild_md_from_blocks.py` 内置）：

```python
# 自动按 MD 相对 vault 根的深度加 ../
md_rel = str(md_path.relative_to(vault_root)).replace("\\", "/")
depth = len(Path(md_rel).parent.parts) if str(Path(md_rel).parent) != "." else 0
prefix = "../" * depth
asset_ref = prefix + "assets/..."
```

或用一次性修复脚本（已存在的 MD 也能修）：

```bash
python fix_md_asset_paths.py "G:/飞书知识库/AI数字人 使用手册"
```

---

### 问题 6：数字人模型 sheet 280+ 张图丢失

**现象**：

`feishu-cli wiki export-tree` 对 sheet 类型节点不导出 cell 里的图片。导出后 MD 是空表格 200×36，**280+ 张数字人形象图全丢**。

**根本原因**：

飞书 sheet 的 cell image 用 `embed-image id`（数字 ID）存储，不是 `file_token`。`feishu-cli sheet export markdown` 只导出文字不导出图片。

**解决**（`extract_sheet_images.py` + `build_sheet_token_map.py` + `rebuild_sheet_doc_v3.py`）：

✅ 关键洞察：**`read-rich` 输出的 file_token 顺序 == V2 API 返回的 embed_id 顺序**（按 cell 遍历顺序），可以一一对应。

```python
# Step 1: 拿 embed_id 列表（V2 API，cell 位置）
positions = read_v2_embed_ids(ss_token, sheet_id, n_rows, n_cols, env)
# 返回 [(row, col, embed_id), ...]

# Step 2: 拿 file_token 列表（read-rich，按 cell 顺序）
tokens = read_rich_tokens(ss_token, sheet_id, n_rows, n_cols, env)
# 返回 [file_token, ...]

# Step 3: 按位置一一对应
for i, (r, c, eid) in enumerate(positions):
    if i < len(tokens):
        ftok = tokens[i]
        # 用 ftok 下载图片，重建 MD
```

---

### 问题 7：2 个 mp4 下载时放错位置

**现象**：

`形象克隆进阶篇.md` 引用 2 个 mp4（`JVNLb...`、`DrQqb...`），但实际文件在 `assets/` 根，子目录找不到。

**根本原因**：

这 2 个视频是飞书原文档里的"跨节点共享资源"，被飞书放到了 vault 根。下载脚本按"按 doc 分目录"策略放，结果在子目录找不到。

**解决**：

✅ 兜底脚本：在子目录里再放一份：

```python
# 任何 MD 引用了 X.mp4 但实际在 assets/ 根 → 复制一份到 MD 对应子目录
import shutil
src = root / "assets" / f"feishu_{token}.mp4"
dst = root / "assets" / md_parent_dir / f"feishu_{token}.mp4"
if not dst.exists():
    shutil.copy(src, dst)
```

---

## 三、最佳实践（推荐流程）

### 一次性环境准备

```bash
# 1. 安装 Go (winget) + Node.js + Python 3
winget install --id GoLang.Go
winget install --id OpenJS.NodeJS.LTS
# Python 3.6+ 通常系统已有

# 2. 克隆本项目
git clone https://github.com/xiaoka6688/feishu-cli.git
cd feishu-cli

# 3. 编译 feishu-cli + 安装 lark-cli
go install .
npm install -g @larksuite/cli

# 4. 配置 App 凭证（编辑 ~/.feishu-cli/config.yaml）
feishu-cli config init
# 编辑 config.yaml，填入 cli_xxx 开头的 App ID 和 Secret

# 5. 一次性申请所有 scope
feishu-cli auth login --no-wait --json --scope "..."
# 浏览器打开链接完成授权
feishu-cli auth login --device-code <device_code>
```

### 同步整棵 Wiki 树（一条命令搞定）

```bash
# 把整棵 Wiki 树同步到 Obsidian Vault
python sync_feishu_to_obsidian.py --wiki "WIKI_TOKEN" --vault "G:/飞书知识库"
```

这个脚本**已集成**：

1. ✅ 递归所有节点拿 doc_token 映射
2. ✅ 拿原始 docx blocks 重建 MD（不丢 View 块）
3. ✅ 自动 sheet 节点特殊处理（cell 图片重建）
4. ✅ 按 MD 实际位置智能决定资源放哪里
5. ✅ 自动算 vault 根相对路径
6. ✅ 修首行 `---` 误判 frontmatter
7. ✅ 修 heading 字段路径

### 单独同步一个文档

```bash
python sync_feishu_to_obsidian.py --wiki "DOC_WIKI_TOKEN"
```

### 增量同步（跳过已存在）

默认行为：已存在的图片/视频文件**自动跳过**（按 token 去重）。重新跑只下新资源。

---

## 四、命令速查

### 安装
```bash
git clone https://github.com/xiaoka6688/feishu-cli.git
cd feishu-cli
go build -o bin/feishu-cli.exe .
cp bin/feishu-cli.exe "$(go env GOPATH)/bin/"
npm install -g @larksuite/cli
```

### 凭证
```bash
feishu-cli config init
# 编辑 ~/.feishu-cli/config.yaml
```

### 一次性 OAuth
```bash
# 见 "一、一次跑通所需的全部 OAuth scope"
feishu-cli auth login --no-wait --json --scope "auth:user.id:read ..."
# 浏览器完成授权后：
feishu-cli auth login --device-code <DEVICE_CODE>
```

### 同步
```bash
# 同步整棵 Wiki 树
python sync_feishu_to_obsidian.py --wiki "WIKI_TOKEN" --vault "G:/飞书知识库"

# 同步单个文档
python sync_feishu_to_obsidian.py --doc "DOC_TOKEN" --vault "G:/飞书知识库"

# 从本地 MD 文件同步
python sync_feishu_to_obsidian.py --md "本地.md" --title "标题" --vault "G:/飞书知识库"
```

### 验证
```bash
# 健康检查
feishu-cli doctor

# 授权状态
feishu-cli auth status

# 资源完整性检查（自己写脚本：MD 引用 vs 实际文件）
python -c "
import re
from pathlib import Path
root = Path('G:/飞书知识库/<你的知识库名>')
missing = []
for p in root.rglob('*.md'):
    text = p.read_text(encoding='utf-8')
    for m in re.finditer(r'(?:\.\./)*\./?assets/[^\"\)\s\']+feishu_[A-Za-z0-9]+\\.(?:png|mp4)', text):
        ref = m.group(0)
        abs_p = (p.parent / ref).resolve() if ref.startswith('.') else (root / ref)
        if not abs_p.exists():
            missing.append((p.name, ref))
print(f'缺失: {len(missing)}')"
```

---

## 📝 关键文件清单

| 文件 | 作用 |
|---|---|
| `sync_feishu_to_obsidian.py` | **主入口** — 一条命令完成 wiki 树同步 |
| `feishu2obsidian.py` | 飞书 MD → Obsidian 格式转换（带 fix frontmatter） |
| `rebuild_md_from_blocks.py` | 从 docx blocks 重建 MD（带 vault 路径计算） |
| `extract_blocks_all.py` | 拿原始 docx 块数据 |
| `build_doc_token_map.py` | 递归 wiki 树拿 doc_token 映射 |
| `download_wiki_images.py` | 批量下载图片/视频（带 doc_token） |
| `extract_sheet_images.py` | sheet 节点专用，提取 cell image |
| `rebuild_sheet_doc_v3.py` | 重建 sheet MD（带 vault 路径） |
| `fix_md_asset_paths.py` | 修复已有 MD 的资源路径 |
| `install.ps1` | Windows 一键安装 |
| `setup-all.sh` | Linux/macOS 一键安装 |
| `TROUBLESHOOTING.md` | 本文档 |

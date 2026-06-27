# Git 提交指引

> 本次 v1.33.0 升级包含 6 个修改 + 17 个新文件

## 📋 推荐提交（拆分 2 个 commit）

### Commit 1: 修复 3 个核心脚本
- `feishu2obsidian.py` (modified) - 修首行 `---` 误判 frontmatter
- `CHANGELOG.md` (modified) - 新增 v1.33.0 版本记录
- `README.md` (modified) - 重写"快速开始"反映所有优化

### Commit 2: 新增工具脚本和文档
- `TROUBLESHOOTING.md` (new) - 完整踩坑记录
- `auth_all.py` (new) - 一次性申请 35 个 scope
- `install.py` (new) - 一步安装脚本
- `sync_feishu_to_obsidian.py` (new) - 一键同步主入口
- `rebuild_md_from_blocks.py` (new) - 从 docx blocks 重建 MD
- `rebuild_sheet_doc_v3.py` (new) - 重建 sheet MD
- `build_sheet_token_map.py` (new) - sheet cell 映射
- `extract_sheet_layout.py` (new) - sheet 全布局
- `download_wiki_images.py` (new) - 批量下载
- `download_videos.py` (new) - 下载视频
- `download_all_videos.py` (new) - 批量下载视频
- `fix_md_asset_paths.py` (new) - 修复已有 MD 资源路径
- `extract_blocks_all.py` (new) - 拿原始 docx 块数据
- `build_doc_token_map.py` (new) - 递归 wiki 树
- `extract_sheet_images.py` (new) - 提取 sheet 图片
- `extract_sheet_images_v2.py` (new) - 提取 sheet 图片 v2
- `deep_extract_tokens.py` (new) - 深扫 token
- `batch_download_wiki_images.py` (new) - 批量下载（早期版）
- `transform_wiki_tree.py` (new) - 转换整棵 wiki 树

## 🚀 推荐命令

```bash
cd "D:\AI\feisu cli\feishu-cli"

# 添加 .gitignore 排除调试文件
cat >> .gitignore << 'EOF'

# 调试/临时文件
__pycache__/
*.pyc
json
项目分析报告-小白指南.md
EOF

# 1. 第一个 commit: 修复
git add CHANGELOG.md README.md feishu2obsidian.py
git commit -m "fix: 修首行 --- 误判 frontmatter + README 重写

1. feishu2obsidian.py: 严格按 YAML 格式判定 frontmatter
   - 飞书导出文件首行 '---' 是引用块分割线，不是 YAML
   - 旧逻辑直接跳过添加元信息，导致 MD 缺 title/source
   - 新逻辑：检查 'key: value' 形式才视为真 frontmatter
2. README.md: 重写快速开始，体现所有 v1.33 优化
3. CHANGELOG.md: 新增 v1.33.0 实战增强版记录

Ref: TROUBLESHOOTING.md#问题-2"

# 2. 第二个 commit: 新增
git add TROUBLESHOOTING.md install.py auth_all.py \
        sync_feishu_to_obsidian.py \
        rebuild_md_from_blocks.py rebuild_sheet_doc_v3.py \
        build_sheet_token_map.py extract_sheet_layout.py \
        download_wiki_images.py download_videos.py download_all_videos.py \
        fix_md_asset_paths.py extract_blocks_all.py build_doc_token_map.py \
        extract_sheet_images.py extract_sheet_images_v2.py \
        deep_extract_tokens.py batch_download_wiki_images.py \
        transform_wiki_tree.py

git commit -m "feat: 飞书→Obsidian 一键同步工具集 (v1.33.0)

实战飞书 Wiki 树（21 文档 + 318 图 + 33 视频）同步的全部经验沉淀：

新增:
- install.py        一步安装（环境检查+编译+OAuth+doctor）
- auth_all.py       一次性 35 个 scope OAuth（合并原 3 次授权）
- sync_feishu_to_obsidian.py  主入口（--wiki/--doc/--md）
- TROUBLESHOOTING.md  7 大类问题+35 scope 完整文档

修复:
- View/Grid/Callout 容器内容不再丢（用底层 docx blocks API 递归）
- heading 字段路径错误（兼容新旧两种 v1 API 格式）
- sheet 280+ 张 cell 图片不再丢（embed_id ↔ file_token 顺序映射）
- vault 子目录 MD 资源路径硬编码为 ./assets/ 导致 14 个 MD 100% 解析失败
  - 根因：Obsidian 严格按 MD 位置解析相对路径
  - 修复：自动按深度加 ../ 前缀
- 2 个 mp4 孤儿资源（飞书跨节点共享资源被放错位置）
  - 修复：fix_orphan_assets 事后兜底，自动复制到子目录
- OAuth 反复授权 3 次 → 1 次拿全

验证: 21 文档 + 354 资源，100% 可达"

# 3. 推送
git push origin main
```

## ⚠️ 注意事项

1. **`项目分析报告-小白指南.md`** 是上次的报告（用户私人），不要 commit
2. **`json` 目录**是中间缓存（blocks_cache.json 等），也不要 commit
3. **`__pycache__`** 加上 .gitignore
4. **`sync_feishu_to_obsidian.py` 里硬编码了你的 App ID/Secret** —— 如果要发到 GitHub，**改成读取环境变量或 config**！

---

## 🌐 多电脑协作工作流（功能分支模式）

> 2026-06-27 补充：作者（小卡）在多台电脑之间协作时使用的工作流。

### 为什么需要分支？

只有 `main` 一个分支时，**两台电脑同时改就会出现冲突**。功能分支模式：

- **`main`** = 永远稳定的"主分支"
- **`feat/xxx` / `fix/xxx` / `docs/xxx`** = 临时分支，开发完 merge 回 main

### 5 类分支命名规范

| 分支前缀 | 用途 | 例子 |
|----------|------|------|
| `feat/` | 新功能 | `feat/sync-feishu-obsidian` |
| `fix/` | 修 bug | `fix/feishu2obsidian-frontmatter` |
| `refactor/` | 重构（不改功能） | `refactor/go-mod-xiaoka` |
| `docs/` | 文档 | `docs/update-troubleshooting` |
| `chore/` | 杂项（依赖、CI） | `chore/upgrade-go-1.22` |

### 日常开发流程

```bash
# === 1. 开始工作前 ===
cd /d/AI/feishu-cli
git checkout main
git pull                            # 拉取最新

# === 2. 创建分支 ===
git checkout -b feat/my-new-feature

# === 3. 改代码 ===
# ... 编辑文件 ...
python feishu2obsidian.py --help    # 自测
go build -o /tmp/test .             # 编译测试

# === 4. 提交 ===
git add -A
git commit -m "feat: 新功能描述"

# === 5. 推到远程 ===
git push -u origin feat/my-new-feature

# === 6. 合并到 main（两种方式） ===
# 方式 A：本地 merge（推荐，单人用）
git checkout main
git pull
git merge feat/my-new-feature       # 快进合并
git push
git branch -d feat/my-new-feature   # 删除本地分支

# 方式 B：GitHub PR（多人协作时）
# 在网页上点 "Compare & pull request"
# Review 后 merge
```

### 跨设备切换

```bash
# === 电脑 A 完成后，电脑 B 开始 ===
# 电脑 B
cd /d/AI/feishu-cli
git fetch origin                    # 拿所有远程分支
git checkout feat/my-new-feature    # 切到 A 正在用的分支
# ... 继续改 ...
git push                            # 推回同一分支（可能冲突，需 rebase）
```

### 冲突处理

```bash
# 如果 push 时报 "non-fast-forward"
git pull --rebase origin main       # 把你的 commit 重放到 main 之后
# 手动解决冲突文件
git add <conflict-files>
git rebase --continue
git push
```

### 5 条铁律

1. **不要同时改同一个文件**——A 改 `feishu2obsidian.py` 时，B 别动
2. **新功能用分支**——大改动开 `feat/xxx`
3. **每天开工前先拉**——`git pull --rebase`
4. **commit 前先自测**——`go build` + 几个 `--help`
5. **push 前先看 diff**——`git diff origin/main`

### 一键同步脚本（`sync.sh`）

保命用，在每台电脑的 `feishu-cli/` 目录保存一份：

```bash
#!/bin/bash
set -e
cd "$(dirname "$0")"

# 检查未提交改动
if [[ -n $(git status --porcelain) ]]; then
    echo "⚠️  有未提交改动"
    git status --short
    read -p "stash 暂存？(y/N) " c
    [[ "$c" == "y" ]] && git stash push -m "auto-$(date +%H%M%S)" || exit 1
fi

# 拉取
git pull --rebase

# 校验
go build -o /tmp/test-build . && echo "✓ Go build"
python feishu2obsidian.py --help > /dev/null && echo "✓ feishu2obsidian"
python obsidian2feishu.py --help > /dev/null && echo "✓ obsidian2feishu"

# 恢复 stash
git stash list | grep -q "auto-" && git stash pop
echo "🎉 同步完成"
```

### 紧急回退

```bash
# 撤销最后一次 commit（保留改动）
git reset --soft HEAD~1

# 撤销到指定 commit
git reset --soft <hash>

# 彻底放弃改动
git reset --hard HEAD

# 从远程覆盖本地
git fetch origin && git reset --hard origin/main
```

### 当前分支情况

- `main` = 稳定主分支
- 本地无其他分支
- 远程也无其他分支（只有 `main`）

如需新功能或大改动，开 `feat/xxx` 分支即可。

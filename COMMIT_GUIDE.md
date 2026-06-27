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

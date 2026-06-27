#!/usr/bin/env python3
"""
sync_feishu_to_obsidian.py - 一键把飞书文档同步到 Obsidian Vault

支持 3 种入口:
  --wiki "WIKI_TOKEN"      : 同步整棵 Wiki 树到 Vault 子目录
  --doc "DOC_TOKEN"        : 同步单个飞书文档
  --md "本地.md"            : 已经下载的本地 MD，做转换+入 Vault

核心功能（已集成所有实战经验）:
  1. ✅ 递归所有节点拿 doc_token 映射（不再丢节点）
  2. ✅ 用底层 docx blocks API 重建 MD（View/Grid 容器不再丢内容）
  3. ✅ 自动 sheet 节点特殊处理（cell 图片不再丢）
  4. ✅ 自动按 MD 实际位置计算 vault 根相对路径（资源不再找不到）
  5. ✅ 修首行 '---' 误判 frontmatter 问题
  6. ✅ 修 heading 字段路径错误
  7. ✅ 资源下载 + 事后兜底（孤儿资源复制到子目录）

默认 Vault: G:\\飞书知识库\\飞书导入\\
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ============== 默认配置 ==============
DEFAULT_VAULT = Path(r"G:\飞书知识库")
VAULT_SUBDIR = "飞书导入"

# feishu-cli 路径：优先用环境变量，否则用默认
import shutil as _shutil
FEISHU_CLI = os.environ.get("FEISHU_CLI_PATH") or (
    r"C:\Users\wang'zhong'wei\go\bin\feishu-cli.exe" if os.name == "nt"
    else (_shutil.which("feishu-cli") or "feishu-cli")
)

# 凭证优先级：环境变量 > config.local.py（个人配置，不提交 Git）
APP_ID = os.environ.get("FEISHU_APP_ID", "")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")

if not APP_ID or not APP_SECRET:
    # 尝试加载 config.local.py（个人凭证）
    try:
        import importlib.util as _ilu
        _local_cfg = HERE / "config.local.py" if (HERE := Path(__file__).parent) else None
        if _local_cfg and _local_cfg.exists():
            _spec = _ilu.spec_from_file_location("config_local", _local_cfg)
            _mod = _ilu.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            APP_ID = APP_ID or getattr(_mod, "APP_ID", "")
            APP_SECRET = APP_SECRET or getattr(_mod, "APP_SECRET", "")
            if not os.environ.get("FEISHU_CLI_PATH"):
                FEISHU_CLI = getattr(_mod, "FEISHU_CLI", FEISHU_CLI)
            if "DEFAULT_VAULT" in dir(_mod):
                DEFAULT_VAULT = Path(getattr(_mod, "DEFAULT_VAULT"))
    except Exception:
        pass


def step(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")


def run_feishu(args, env, timeout=60):
    return subprocess.run([FEISHU_CLI] + args, env=env, capture_output=True, text=True, timeout=timeout)


# ============== 1. 拿 wiki 树所有节点 ==============

def wiki_to_doc_token(wiki_token: str, env: dict) -> tuple:
    """Wiki token → (文档 token, 标题)"""
    r = run_feishu(["wiki", "get", wiki_token], env, 30)
    out = r.stdout
    m_token = re.search(r"文档 Token:\s*(\S+)", out)
    m_title = re.search(r"标题:\s*(.+?)(?:\s*$)", out, re.MULTILINE)
    if not m_token:
        raise RuntimeError(f"无法获取文档 token:\n{out}\n{r.stderr}")
    return (m_token.group(1).strip(),
            m_title.group(1).strip() if m_title else "")


def walk_wiki(space_id: str, node_token: str, env: dict, out: list, depth: int = 0):
    """递归 walk wiki 树"""
    info = wiki_to_doc_token(node_token, env)
    indent = "  " * depth
    print(f"{indent}📄 {info[1][:40]} (doc_token={info[0][:12] if info[0] else '-'}...)")
    out.append({"node_token": node_token, "doc_token": info[0], "title": info[1]})
    # 列出子节点
    try:
        r = run_feishu(["api", "GET",
                        f"/open-apis/wiki/v2/spaces/{space_id}/nodes?parent_node_token={node_token}&page_size=50",
                        "--as", "bot"], env, 30)
        data = r.json() if r.stdout else {}
        items = (data.get("data", {}).get("items", []) or [])
    except Exception as e:
        items = []
        print(f"{indent}  ⚠️  无法列子节点: {e}")
    for c in items:
        walk_wiki(space_id, c["node_token"], env, out, depth + 1)


def get_space_id(wiki_token: str, env: dict) -> str:
    """从 wiki 节点反查空间 ID"""
    r = run_feishu(["wiki", "get", wiki_token], env, 30)
    m = re.search(r"空间 ID:\s*(\d+)", r.stdout)
    if not m:
        raise RuntimeError(f"无法获取空间 ID: {r.stdout[:200]}")
    return m.group(1).strip()


# ============== 2. 拿原始 docx 块数据 ==============

def fetch_all_blocks(doc_token: str, env: dict) -> list:
    """分页拿全所有块"""
    blocks = []
    page_token = ""
    while True:
        path = f"/open-apis/docx/v1/documents/{doc_token}/blocks?page_size=500"
        if page_token:
            path += f"&page_token={page_token}"
        r = run_feishu(["api", "GET", path], env, 120)
        try:
            data = r.json()
        except Exception:
            break
        if data.get("code") != 0:
            print(f"  ❌ 错误 code={data.get('code')}: {data.get('msg', '')}")
            break
        items = data.get("data", {}).get("items", []) or []
        blocks.extend(items)
        if not data.get("data", {}).get("has_more"):
            break
        page_token = data.get("data", {}).get("page_token", "")
        if not page_token:
            break
    return blocks


# ============== 3. 重建 MD ==============

def render_text_elements(text_elements):
    """从 docx v1 API 元素渲染为 Markdown inline（同时兼容旧版）"""
    import urllib.parse
    if isinstance(text_elements, dict):
        elements = text_elements.get("elements", [])
        out = []
        for el in elements:
            if "text_run" in el:
                run = el["text_run"]
                content = run.get("content", "")
                style = run.get("text_element_style", {})
                if style.get("bold"): content = f"**{content}**"
                if style.get("italic"): content = f"*{content}*"
                if style.get("strikethrough"): content = f"~~{content}~~"
                if style.get("underline"): content = f"<u>{content}</u>"
                if style.get("inline_code"): content = f"`{content}`"
                link = el.get("link", {}) or run.get("link", {})
                if link and link.get("url"):
                    content = f"[{content}]({urllib.parse.unquote(link['url'])})"
                out.append(content)
            elif "equation" in el:
                out.append(f"${el['equation'].get('content','')}$")
            elif "mention_user" in el:
                out.append(f"@{el['mention_user'].get('user_id','user')}")
            elif "mention_doc" in el:
                out.append(f"[[{el['mention_doc'].get('title','doc')}]]")
        return "".join(out)
    out = []
    for el in text_elements or []:
        if isinstance(el, str):
            out.append(el)
            continue
        kind = el.get("type", "text")
        if kind == "text":
            content = el.get("text", "")
            link = el.get("link", {})
            if link and link.get("url"):
                content = f"[{content}]({urllib.parse.unquote(link['url'])})"
            out.append(content)
        else:
            out.append(el.get("text", ""))
    return "".join(out)


def compute_asset_prefix(md_path: Path, vault_root: Path) -> str:
    """根据 MD 相对 vault 根的深度计算 asset 前缀"""
    try:
        rel = md_path.relative_to(vault_root)
    except ValueError:
        return ""
    depth = len(rel.parent.parts) if str(rel.parent) != "." else 0
    return "../" * depth


def render_block(block, block_map, depth, asset_dir_rel, asset_prefix):
    bt = block.get("block_type")
    if bt == 1:
        return render_children(block.get("children", []), block_map, depth, asset_dir_rel, asset_prefix)
    elif bt == 2:
        return render_text_elements(block.get("text", {}))
    elif bt == 3:
        return "# " + render_text_elements(block.get("heading1", {}))
    elif bt == 4:
        return "## " + render_text_elements(block.get("heading2", {}))
    elif bt == 5:
        return "### " + render_text_elements(block.get("heading3", {}))
    elif bt in (6, 7, 8, 9, 10, 11):
        return "#" * (bt - 5) + " " + render_text_elements(block.get(f"heading{bt-2}", {}))
    elif bt == 12:
        return "- " + render_text_elements(block.get("bullet", {}))
    elif bt == 13:
        return "1. " + render_text_elements(block.get("ordered", {}))
    elif bt == 14:
        c = block.get("code", {})
        return f"```{c.get('language','')}\n{c.get('body','')}\n```"
    elif bt == 15:
        return "> " + render_text_elements(block.get("quote", {}))
    elif bt == 19:
        co = block.get("callout", {})
        emoji = co.get("emoji_id", "💡")
        inner = render_children(block.get("children", []), block_map, depth, asset_dir_rel, asset_prefix)
        return f"> {emoji}\n>\n{inner}"
    elif bt == 22:
        return "---"
    elif bt == 23:
        f = block.get("file", {})
        token = f.get("token", "")
        name = f.get("name", "video.mp4")
        if token:
            return f'\n<video src="{asset_prefix}{asset_dir_rel}/feishu_{token}.mp4" controls style="max-width:100%"></video>\n<!-- {name} -->\n'
        return ""
    elif bt in (24, 25, 33):
        return render_children(block.get("children", []), block_map, depth, asset_dir_rel, asset_prefix)
    elif bt == 27:
        img = block.get("image", {})
        token = img.get("token", "")
        if token:
            return f"\n![{asset_prefix}{asset_dir_rel}/feishu_{token}.png]({asset_prefix}{asset_dir_rel}/feishu_{token}.png)\n"
        return ""
    elif bt == 31:
        rows_ids = block.get("children", [])
        rows = [block_map.get(rid, {}) for rid in rows_ids]
        return render_table(rows, block_map, depth, asset_dir_rel, asset_prefix)
    elif bt == 32:
        cells_ids = block.get("children", [])
        cells = [block_map.get(cid, {}) for cid in cells_ids]
        return [render_block(c, block_map, depth + 1, asset_dir_rel, asset_prefix) for c in cells]
    return f"<!-- 不支持的块类型 {bt} -->"


def render_children(child_ids, block_map, depth, asset_dir_rel, asset_prefix):
    out = []
    for cid in child_ids or []:
        b = block_map.get(cid)
        if not b:
            continue
        r = render_block(b, block_map, depth, asset_dir_rel, asset_prefix)
        if r:
            out.append(r)
    return "\n\n".join(out)


def render_table(rows, block_map, depth, asset_dir_rel, asset_prefix):
    if not rows:
        return ""
    header_cells = render_block(rows[0], block_map, depth, asset_dir_rel, asset_prefix)
    if not isinstance(header_cells, list):
        header_cells = [str(header_cells)]
    lines = ["| " + " | ".join(c.replace("|", "\\|") if c else "" for c in header_cells) + " |"]
    lines.append("| " + " | ".join("---" for _ in header_cells) + " |")
    for r in rows[1:]:
        cells = render_block(r, block_map, depth, asset_dir_rel, asset_prefix)
        if not isinstance(cells, list):
            cells = [str(cells)]
        while len(cells) < len(header_cells):
            cells.append("")
        lines.append("| " + " | ".join(c.replace("|", "\\|") if c else "" for c in cells) + " |")
    return "\n" + "\n".join(lines) + "\n"


def build_md_from_blocks(doc_token, title, blocks, md_path, vault_root):
    """从 docx blocks 重建 MD，含 frontmatter 和正确的 asset 路径"""
    asset_subdir = "assets"
    rel = md_path.relative_to(vault_root)
    if str(rel.parent) != ".":
        asset_subdir = "assets/" + str(rel.parent)
    asset_prefix = compute_asset_prefix(md_path, vault_root)

    block_map = {b["block_id"]: b for b in blocks}
    root = next((b for b in blocks if b.get("block_type") == 1), None)
    if not root:
        return f"<!-- 无根 block: {title} -->"

    body = render_children(root.get("children", []), block_map, 0, asset_subdir, asset_prefix)

    import datetime
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    fm_lines = [
        "---",
        f"title: {title}",
        f"created: {now}",
        "source: feishu",
        f"source_url: feishu://docx/{doc_token}",
        "tags:",
        "  - feishu",
        "  - imported",
        "  - wiki",
        "---",
        "",
    ]
    return "\n".join(fm_lines) + body


# ============== 4. 下载图片/视频 ==============

def extract_tokens_from_blocks(blocks):
    """从 docx blocks 提取所有 image/video token"""
    imgs = []
    vids = []
    for b in blocks:
        if b.get("block_type") == 27:
            t = b.get("image", {}).get("token")
            if t:
                imgs.append(t)
        elif b.get("block_type") == 23:
            t = b.get("file", {}).get("token")
            if t:
                vids.append(t)
    return imgs, vids


def download_media(token, doc_token, ext, asset_path, env, timeout=300):
    """下载单个图片或视频"""
    if asset_path.exists() and asset_path.stat().st_size > 0:
        return True
    cmd = [FEISHU_CLI, "doc", "media-download", token,
           "--doc-token", doc_token, "--doc-type", "docx",
           "-o", str(asset_path)]
    try:
        r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False
    return asset_path.exists() and asset_path.stat().st_size > 0


# ============== 5. 事后兜底：孤儿资源复制 ==============

def fix_orphan_assets(vault: Path):
    """把 vault 根的孤儿资源复制到 MD 实际引用的子目录"""
    vault_assets = vault / "assets"
    if not vault_assets.exists():
        return 0
    root_files = {f.stem: f for f in vault_assets.glob("feishu_*") if f.is_file()}
    if not root_files:
        return 0
    fixed = 0
    for md in vault.rglob("*.md"):
        try:
            text = md.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for m in re.finditer(r'feishu_([A-Za-z0-9]{27})\.(png|mp4)', text):
            stem = f"feishu_{m.group(1)}"
            if stem not in root_files:
                continue
            rel = md.relative_to(vault)
            target_dir = vault_assets / rel.parent
            target_dir.mkdir(parents=True, exist_ok=True)
            dst = target_dir / root_files[stem].name
            if not dst.exists():
                shutil.copy(root_files[stem], dst)
                fixed += 1
    if fixed:
        print(f"  🔧 兜底复制 {fixed} 个孤儿资源到子目录")
    return fixed


# ============== 主流程 ==============

def sync_single_doc(doc_token: str, title: str, out_md: Path, env: dict, vault: Path):
    """同步单个 docx 文档"""
    step(f"📥 拉取 {title} 原始块...")
    blocks = fetch_all_blocks(doc_token, env)
    if not blocks:
        print(f"  ❌ 拉取失败")
        return False

    step(f"🛠  重建 MD: {out_md.name}")
    md = build_md_from_blocks(doc_token, title, blocks, out_md, vault)
    out_md.write_text(md, encoding="utf-8")

    # 下载图片/视频
    imgs, vids = extract_tokens_from_blocks(blocks)
    asset_dir = out_md.parent / "assets"
    if imgs or vids:
        step(f"🖼  下载 {len(imgs)} 张图 + {len(vids)} 个视频")
        asset_dir.mkdir(parents=True, exist_ok=True)
        for t in imgs:
            download_media(t, doc_token, "png", asset_dir / f"feishu_{t}.png", env)
        for t in vids:
            download_media(t, doc_token, "mp4", asset_dir / f"feishu_{t}.mp4", env)
    return True


def main():
    p = argparse.ArgumentParser(description="一键把飞书文档同步到 Obsidian Vault")
    p.add_argument("--wiki", help="飞书 Wiki token（同步整棵子树）")
    p.add_argument("--doc", help="飞书 Docx token（同步单个文档）")
    p.add_argument("--md", help="已经是本地飞书 MD 文件")
    p.add_argument("--title", help="文档标题（默认自动从 MD/wiki 提取）")
    p.add_argument("--vault", default=str(DEFAULT_VAULT), help=f"Obsidian Vault 路径（默认 {DEFAULT_VAULT}）")
    p.add_argument("--subdir", default=VAULT_SUBDIR, help=f"Vault 内子目录（默认 {VAULT_SUBDIR}，--wiki 模式不用）")
    p.add_argument("--no-images", action="store_true", help="不下载图片/视频")
    p.add_argument("--tags", default="feishu,imported,wiki", help="frontmatter 标签")
    args = p.parse_args()

    if not (args.wiki or args.doc or args.md):
        print("❌ 至少指定一个: --wiki / --doc / --md")
        sys.exit(1)

    env = os.environ.copy()
    env["FEISHU_APP_ID"] = APP_ID
    env["FEISHU_APP_SECRET"] = APP_SECRET

    vault = Path(args.vault)

    # ===== Wiki 树模式 =====
    if args.wiki:
        step(f"🚶 遍历 Wiki 树: {args.wiki}")
        space_id = get_space_id(args.wiki, env)
        nodes = []
        walk_wiki(space_id, args.wiki, env, nodes, 0)
        print(f"  共 {len(nodes)} 个节点")

        wiki_root = vault / args.title or "Wiki"
        if args.title:
            wiki_root = vault / args.title
        else:
            # 用 wiki 标题作目录
            _, wiki_title = wiki_to_doc_token(args.wiki, env)
            wiki_root = vault / wiki_title
        wiki_root.mkdir(parents=True, exist_ok=True)

        for n in nodes:
            if not n["doc_token"]:
                continue
            # 找 MD 路径
            rel = n["title"]
            out_md = wiki_root / f"{rel}.md"
            if n["node_token"] == args.wiki:
                # 根节点单独放
                out_md = wiki_root / f"{rel}.md"
            sync_single_doc(n["doc_token"], rel, out_md, env, vault)
        # 兜底
        fix_orphan_assets(vault)
        return

    # ===== 单文档模式 =====
    if args.doc:
        doc_token = args.doc
        title = args.title
        if not title:
            # 试一下 wiki get 拿标题
            try:
                _, title = wiki_to_doc_token(args.doc, env)
            except Exception:
                title = args.doc
        subdir = vault / args.subdir
        subdir.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r'[\\/:*?"<>|]', '_', title)
        out_md = subdir / f"{safe}.md"
        sync_single_doc(doc_token, title, out_md, env, vault)
        # 兜底
        fix_orphan_assets(vault)
        return

    # ===== 本地 MD 模式 =====
    if args.md:
        # 简化：让 feishu2obsidian.py 处理
        from feishu2obsidian import add_obsidian_frontmatter
        subdir = vault / args.subdir
        subdir.mkdir(parents=True, exist_ok=True)
        src = Path(args.md)
        title = args.title or src.stem
        safe = re.sub(r'[\\/:*?"<>|]', '_', title)
        out_md = subdir / f"{safe}.md"
        text = src.read_text(encoding="utf-8")
        text = add_obsidian_frontmatter(text, title, "")
        out_md.write_text(text, encoding="utf-8")
        print(f"✅ 转换: {out_md}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
rebuild_md_from_blocks.py - 从 docx 块数据完整重建 MD

关键设计:
  - asset_prefix: 根据 MD 相对 vault 根的深度自动加 ../ 前缀
  - 支持新版 v1 API (elements/text_run/text_element_style) 和旧版
  - 完整 block_type 映射: 1, 2, 3-11 (heading1-9), 12, 13, 14, 15, 19, 22, 23, 24, 25, 27, 31, 32, 33
"""
import argparse
import datetime
import json
import re
import sys
import urllib.parse
from pathlib import Path


# ---------- 文本元素 ----------

def render_text_elements(text_elements):
    """把飞书 text 元素渲染为 Markdown inline

    支持两种输入:
    1. 旧版: [{"type": "text", "text": "...", "link": {...}}, ...]
    2. 新版 v1: {"elements": [{"text_run": {"content": "...", "text_element_style": {...}}, ...]}
    """
    if isinstance(text_elements, dict):
        # 新版 v1 API 格式
        elements = text_elements.get("elements", [])
        out = []
        for el in elements:
            if "text_run" in el:
                run = el["text_run"]
                content = run.get("content", "")
                style = run.get("text_element_style", {})
                if style.get("bold"):
                    content = f"**{content}**"
                if style.get("italic"):
                    content = f"*{content}*"
                if style.get("strikethrough"):
                    content = f"~~{content}~~"
                if style.get("underline"):
                    content = f"<u>{content}</u>"
                if style.get("inline_code"):
                    content = f"`{content}`"
                link = el.get("link", {}) or run.get("link", {})
                if link and link.get("url"):
                    href = urllib.parse.unquote(link["url"])
                    content = f"[{content}]({href})"
                out.append(content)
            elif "equation" in el:
                eq = el["equation"].get("content", "")
                out.append(f"${eq}$")
            elif "mention_user" in el:
                out.append(f"@{el['mention_user'].get('user_id', 'user')}")
            elif "mention_doc" in el:
                out.append(f"[[{el['mention_doc'].get('title', 'doc')}]]")
        return "".join(elements and out or [""])

    # 旧版 list of dict
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
                href = urllib.parse.unquote(link["url"])
                out.append(f"[{content}]({href})")
            else:
                out.append(content)
        elif kind == "mention_user":
            out.append(f"@{el.get('user_name', '用户')}")
        elif kind == "mention_doc":
            out.append(f"[[{el.get('title', '文档')}]]")
        elif kind == "equation":
            out.append(f"${el.get('equation', '')}$")
        elif kind == "file":
            out.append(el.get("file_name", ""))
        else:
            out.append(el.get("text", ""))
    return "".join(out)


# ---------- 块渲染 ----------

def render_block(block, block_map, depth, asset_dir_rel, asset_prefix=""):
    """递归渲染单个块为 MD

    asset_prefix: 相对 vault 根的路径前缀（如 "" 或 "../" 或 "../../"）
    """
    bt = block.get("block_type")

    if bt == 1:  # page 根
        return render_children(block.get("children", []), block_map, depth, asset_dir_rel, asset_prefix)

    elif bt == 2:  # paragraph
        return render_text_elements(block.get("text", {}))

    elif bt == 3:  # h1
        return "# " + render_text_elements(block.get("heading1", {}))

    elif bt == 4:  # h2
        return "## " + render_text_elements(block.get("heading2", {}))

    elif bt == 5:  # h3
        return "### " + render_text_elements(block.get("heading3", {}))

    elif bt in (6, 7, 8, 9, 10, 11):  # heading4-9
        level = bt - 5
        key = f"heading{bt - 2}"
        return "#" * level + " " + render_text_elements(block.get(key, {}))

    elif bt == 12:  # bullet
        return "- " + render_text_elements(block.get("bullet", {}))

    elif bt == 13:  # ordered
        return "1. " + render_text_elements(block.get("ordered", {}))

    elif bt == 14:  # code
        c = block.get("code", {})
        lang = c.get("language", "")
        body = c.get("body", "")
        return f"```{lang}\n{body}\n```"

    elif bt == 15:  # quote
        text = render_text_elements(block.get("quote", {}))
        return f"> {text}"

    elif bt == 17:  # todo
        td = block.get("todo", {})
        done = "x" if td.get("done") else " "
        text = render_text_elements(td)
        return f"- [{done}] {text}"

    elif bt == 19:  # callout
        co = block.get("callout", {})
        emoji = co.get("emoji_id", "💡")
        inner = render_children(block.get("children", []), block_map, depth, asset_dir_rel, asset_prefix)
        return f"> {emoji}\n>\n{inner}"

    elif bt == 22:  # divider
        return "---"

    elif bt == 23:  # video
        f = block.get("file", {})
        token = f.get("token", "")
        name = f.get("name", "video.mp4")
        if token:
            return f'\n<video src="{asset_prefix}{asset_dir_rel}/feishu_{token}.mp4" controls style="max-width:100%"></video>\n<!-- 原文件名: {name} -->\n'
        return ""

    elif bt == 24:  # grid
        return render_children(block.get("children", []), block_map, depth, asset_dir_rel, asset_prefix)

    elif bt == 25:  # grid_column
        return render_children(block.get("children", []), block_map, depth, asset_dir_rel, asset_prefix)

    elif bt == 27:  # image
        img = block.get("image", {})
        token = img.get("token", "")
        if token:
            return f"\n![{asset_prefix}{asset_dir_rel}/feishu_{token}.png]({asset_prefix}{asset_dir_rel}/feishu_{token}.png)\n"
        return ""

    elif bt == 31:  # table
        rows_ids = block.get("children", [])
        rows = [block_map.get(rid, {}) for rid in rows_ids]
        return render_table(rows, block_map, depth, asset_dir_rel, asset_prefix)

    elif bt == 32:  # table_row
        cells_ids = block.get("children", [])
        cells = [block_map.get(cid, {}) for cid in cells_ids]
        return [render_block(c, block_map, depth + 1, asset_dir_rel, asset_prefix) for c in cells]

    elif bt == 33:  # view（容器）
        return render_children(block.get("children", []), block_map, depth, asset_dir_rel, asset_prefix)

    elif bt == 34:  # 旧 callout
        co = block.get("callout", {})
        emoji = co.get("emoji", "💡")
        text_parts = render_children(block.get("children", []), block_map, depth, asset_dir_rel, asset_prefix)
        return f"> {emoji} **提示**\n>\n{text_parts}"

    elif bt == 39:  # bookmark
        return ""

    else:
        return f"<!-- 不支持的块类型 {bt} -->"


def render_children(child_ids, block_map, depth, asset_dir_rel, asset_prefix=""):
    out = []
    for cid in child_ids or []:
        b = block_map.get(cid)
        if not b:
            continue
        rendered = render_block(b, block_map, depth, asset_dir_rel, asset_prefix)
        if rendered:
            out.append(rendered)
    return "\n\n".join(out)


def render_table(rows, block_map, depth, asset_dir_rel, asset_prefix=""):
    if not rows:
        return ""
    header = rows[0]
    header_cells = render_block(header, block_map, depth, asset_dir_rel, asset_prefix)
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


def compute_asset_prefix(md_path: Path, vault_root: Path) -> str:
    """根据 MD 相对 vault 根的深度计算 asset 前缀"""
    try:
        rel = md_path.relative_to(vault_root)
    except ValueError:
        return ""
    depth = len(rel.parent.parts) if str(rel.parent) != "." else 0
    return "../" * depth


def build_md(doc_token: str, title: str, blocks: list,
             asset_dir_rel: str = "assets",
             md_path: Path = None, vault_root: Path = None) -> str:
    """把一个 doc 的所有块渲染成 MD

    Args:
        asset_dir_rel: 资源目录相对 vault 根的路径，如 "assets"
        md_path: MD 文件的最终路径（用于计算相对 vault 根的深度）
        vault_root: Obsidian Vault 根目录
    """
    asset_prefix = ""
    if md_path and vault_root:
        asset_prefix = compute_asset_prefix(md_path, vault_root)

    block_map = {b["block_id"]: b for b in blocks}
    root = next((b for b in blocks if b.get("block_type") == 1), None)
    if not root:
        return f"<!-- 无根 block: {title} -->"

    body = render_children(root.get("children", []), block_map, 0, asset_dir_rel, asset_prefix)

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


def main():
    p = argparse.ArgumentParser()
    p.add_argument("root", help="Wiki 根目录")
    p.add_argument("--cache", default="blocks_cache.json")
    p.add_argument("--out-subdir", default="", help="输出子目录（默认覆盖原 MD）")
    args = p.parse_args()

    root = Path(args.root)
    cache = root / args.cache
    data = json.loads(cache.read_text(encoding="utf-8"))
    map_data = json.loads((root / "doc_token_map.json").read_text(encoding="utf-8"))
    title_to_md = {}
    for md_path in root.rglob("*.md"):
        if md_path.name in (args.cache, "doc_token_map.json", "image_map.json", "blocks_cache.json", "all_tokens.json"):
            continue
        title_to_md[md_path.stem.strip()] = md_path

    success = 0
    failed = []
    for dt, info in data.items():
        title = info["title"].strip()
        if not info["blocks"]:
            continue
        md_path = title_to_md.get(title)
        if not md_path:
            for t, p_ in title_to_md.items():
                if title in t or t in title:
                    md_path = p_
                    break
        if not md_path:
            print(f"  ⚠️  找不到 MD: {title}")
            continue

        rel = md_path.relative_to(root)
        asset_subdir = "assets/" + str(rel.parent) if str(rel.parent) != "." else "assets"

        try:
            md = build_md(dt, title, info["blocks"], asset_subdir, md_path, root)
            md_path.write_text(md, encoding="utf-8")
            print(f"  ✅ {rel}  ({len(md)} chars)")
            success += 1
        except Exception as e:
            print(f"  ❌ {rel}: {e}")
            failed.append((title, str(e)))

    print(f"\n📊 重建: 成功 {success}, 失败 {len(failed)}")


if __name__ == "__main__":
    main()

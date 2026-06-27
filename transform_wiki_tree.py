#!/usr/bin/env python3
"""
transform_wiki_tree.py - 把整个 Wiki 树 MD 全部转 Obsidian 格式并补 frontmatter

流程:
  1. 扫描 root/**/*.md
  2. 对每个 MD 跑 feishu2obsidian.py 转换（输出到 .obsidian.tmp 临时文件）
  3. 给结果补 Obsidian 风格 frontmatter（从目录结构/文件路径推断元信息）
  4. 替换原文件
  5. 收集所有 feishu_<27位token> 引用 + 对应 doc_token，写到 image_map.json
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# 引用 feishu2obsidian.py 的转换逻辑
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from feishu2obsidian import (  # noqa: E402
    url_decode_text, transform_images, transform_lark_table,
)


TOKEN_RE = re.compile(r'<image\s+token="([A-Za-z0-9]+)"')


def transform(md_path: Path) -> str:
    """跑 feishu2obsidian 的转换链"""
    text = md_path.read_text(encoding="utf-8", errors="ignore")
    text = url_decode_text(text)
    text = transform_images(text)
    text = transform_lark_table(text)
    return text


def fix_frontmatter(text: str, title: str, source_url: str, tags: list) -> str:
    """和 sync_feishu_to_obsidian.py 一样的 frontmatter 修复"""
    import datetime
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
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

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    tags_yaml = "\n".join(f"  - {t}" for t in tags)
    fm = f"""---
title: {title}
created: {now}
source: feishu
source_url: {source_url}
tags:
{tags_yaml}
---

"""
    return fm + body


def main():
    p = argparse.ArgumentParser(description="把 Wiki 树全部 MD 转 Obsidian 格式")
    p.add_argument("root", help="Wiki 根目录")
    p.add_argument("--wiki-url", help="飞书 Wiki URL（用于 root frontmatter）")
    p.add_argument("--tags", default="feishu,imported,wiki", help="frontmatter 标签")
    p.add_argument("--map-out", default="image_map.json", help="输出图片映射文件")
    args = p.parse_args()

    root = Path(args.root)
    if not root.exists():
        print(f"❌ 路径不存在: {root}")
        sys.exit(1)

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    md_files = sorted(root.rglob("*.md"))
    print(f"📂 扫描: {root} (找到 {len(md_files)} 个 MD)")

    image_map: dict = {}  # token -> {"md": relative_path, "doc_token": "..."}

    for i, md in enumerate(md_files, 1):
        rel = md.relative_to(root)
        # 标题：用文件名（去 .md 后缀）
        title = md.stem
        # 来源 URL：用文件路径拼一个相对 URL（外部链接）
        source_url = f"feishu://wiki-tree/{rel.as_posix()}"

        # 转换
        transformed = transform(md)
        # 提取 token（在转换前还是转换后？我们对原始 MD 提取更可靠）
        raw_text = md.read_text(encoding="utf-8", errors="ignore")
        tokens = set(TOKEN_RE.findall(raw_text))
        for t in tokens:
            if t not in image_map:
                image_map[t] = {"md": str(rel), "doc_token": ""}

        # 加 frontmatter
        out_text = fix_frontmatter(transformed, title, source_url, tags)
        md.write_text(out_text, encoding="utf-8")
        print(f"  [{i:2d}/{len(md_files)}] ✓ {rel}  (图片 {len(tokens)} 张)")

    # 写映射
    map_path = root / args.map_out
    map_path.write_text(json.dumps(image_map, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print(f"🗺  映射文件: {map_path}  ({len(image_map)} 个唯一 token)")


if __name__ == "__main__":
    main()

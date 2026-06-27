#!/usr/bin/env python3
"""
rebuild_sheet_doc_v3.py - 用 sheet_token_map.json 重建数字人模型.md
"""
import argparse
import datetime
import json
import sys
from pathlib import Path

ASSET_REL = "assets/常见数字人形象"
SHEETS_ORDER = [
    "76ec0d", "6FZq6E", "k2Vhow", "s4NXm2", "iFeNfn", "SEMqvr", "1xbmFi", "m5ZanZ",
]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("root", help="Wiki 根目录")
    args = p.parse_args()

    root = Path(args.root)
    token_map = json.loads((root / "sheet_token_map.json").read_text(encoding="utf-8"))

    # 校验本地图存在
    asset_dir = root / ASSET_REL
    local_files = {f.stem.replace("feishu_", ""): f for f in asset_dir.glob("feishu_*.png")}

    out_md = []
    out_md.append("---")
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    out_md.append("title: 数字人模型")
    out_md.append(f"created: {now}")
    out_md.append("source: feishu")
    out_md.append("source_url: feishu://sheet/LyppsrqKbhUvzmtfmmIcmcThnpc")
    out_md.append("tags:")
    out_md.append("  - feishu")
    out_md.append("  - imported")
    out_md.append("  - wiki")
    out_md.append("---")
    out_md.append("")
    out_md.append("# 数字人模型")
    out_md.append("")

    total_imgs = 0
    for sheet_id in SHEETS_ORDER:
        if sheet_id not in token_map:
            continue
        info = token_map[sheet_id]
        name = info["name"]
        positions = info["positions"]  # [(row, col, embed_id), ...]
        tokens = info["tokens"]        # [file_token, ...]（按 cell 顺序）

        out_md.append(f"## {name}")
        out_md.append("")

        if not positions:
            out_md.append("（无图）")
            out_md.append("")
            continue

        # 按 row, col 分组：每个 row 一行
        from collections import defaultdict
        row_groups = defaultdict(list)
        for i, (r, c, eid) in enumerate(positions):
            if i < len(tokens):
                ftok = tokens[i]
                row_groups[r].append((c, ftok))

        # 渲染：每行一组
        for r in sorted(row_groups.keys()):
            cells = row_groups[r]
            # 按 col 排序
            cells.sort(key=lambda x: x[0])
            cell_md = []
            for c, ftok in cells:
                if ftok in local_files:
                    cell_md.append(f"![](./{ASSET_REL}/feishu_{ftok}.png)")
                    total_imgs += 1
                else:
                    cell_md.append(f"<!-- 图 {ftok[:8]} 缺失 -->")
            out_md.append(f"**第 {r} 行：** " + " | ".join(cell_md))
            out_md.append("")

        out_md.append("---")
        out_md.append("")

    out_path = root / "常见数字人形象" / "数字人模型.md"
    out_path.write_text("\n".join(out_md), encoding="utf-8")
    print(f"✅ {out_path}")
    print(f"📊 嵌入 {total_imgs} 张图，共 {sum(len(t['positions']) for t in token_map.values())} 个 cell")
    if total_imgs < sum(len(t['positions']) for t in token_map.values()):
        print("⚠️  部分图本地未找到")


if __name__ == "__main__":
    main()

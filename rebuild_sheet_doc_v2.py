#!/usr/bin/env python3
"""
rebuild_sheet_doc_v2.py - 重建数字人模型.md，按 sheet 嵌入所有图

策略:
  1. 从 sheet_layout.json 拿 (sheet_id, row, col, embed_id) 位置
  2. 从 extract_sheet_images 当时的 token 列表按 sheet 顺序匹配
     （因为 read-rich 输出顺序 == V2 API embed_id 顺序 == 飞书内部 cell 顺序）
  3. 按 sheet/row/col 渲染为表格，cell 含 image
"""
import argparse
import datetime
import json
import re
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
    layout = json.loads((root / "sheet_layout.json").read_text(encoding="utf-8"))
    embed_to_token = layout.get("embed_to_token", {})

    # 收集本地图，按文件 token 排序
    asset_dir = root / ASSET_REL
    local_files = {f.stem.replace("feishu_", ""): f for f in asset_dir.glob("feishu_*.png")}
    print(f"  本地图: {len(local_files)} 张")

    # 按 sheet 顺序重建
    out_md = []
    out_md.append("---")
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    out_md.append(f"title: 数字人模型")
    out_md.append(f"created: {now}")
    out_md.append(f"source: feishu")
    out_md.append("source_url: feishu://sheet/LyppsrqKbhUvzmtfmmIcmcThnpc")
    out_md.append("tags:")
    out_md.append("  - feishu")
    out_md.append("  - imported")
    out_md.append("  - wiki")
    out_md.append(f"---")
    out_md.append("")
    out_md.append("# 数字人模型")
    out_md.append("")
    # 统计总图数
    total_sheet_imgs = 0
    for sid in SHEETS_ORDER:
        if sid in layout["layout"]:
            for row in layout["layout"][sid].get("rows", {}).values():
                for toks in row.values():
                    total_sheet_imgs += len(toks)
    out_md.append("> 飞书 Wiki 数字人形象库（" + str(total_sheet_imgs) + " 个图片 cell）")
    out_md.append("")

    total_imgs = 0
    unmapped = []

    for sheet_id in SHEETS_ORDER:
        if sheet_id not in layout["layout"]:
            continue
        info = layout["layout"][sheet_id]
        name = info["name"]
        rows = info["rows"]
        out_md.append(f"## {name}")
        out_md.append("")

        if not rows:
            out_md.append("（无图）")
            out_md.append("")
            continue

        # 收集本 sheet 的 (row, col) 排序
        cell_list = []
        for r in sorted(rows.keys(), key=int):
            for c in sorted(rows[r].keys(), key=int):
                for eid in rows[r][c]:
                    cell_list.append((int(r), int(c), eid))

        # 对每个 embed_id，找 file_token
        # 备选映射：embed_to_token 直接映射（70 个能映射上）
        # 兜底：先看 embed_to_token；否则跳过
        # 输出: 每个 cell 独占一行（cell 大）
        for r, c, eid in cell_list:
            ftok = embed_to_token.get(str(eid)) or embed_to_token.get(eid)
            if ftok and ftok in local_files:
                rel = f"./{ASSET_REL}/feishu_{ftok}.png"
                out_md.append(f"### 行 {r} 列 {c}")
                out_md.append("")
                out_md.append(f"![数字人形象 {ftok[:12]}]({rel})")
                out_md.append("")
                total_imgs += 1
            else:
                # 没映射上，跳过
                unmapped.append((sheet_id, r, c, eid))

        out_md.append("---")
        out_md.append("")

    print(f"\n📊 嵌入: {total_imgs} 张图")
    if unmapped:
        print(f"⚠️  未映射: {len(unmapped)} 个 cell")
        for s, r, c, e in unmapped[:5]:
            print(f"   {s} 行{r}列{c} embed_id={e}")

    out_path = root / "常见数字人形象" / "数字人模型.md"
    out_path.write_text("\n".join(out_md), encoding="utf-8")
    print(f"  ✅ {out_path}  ({sum(len(l) for l in out_md):,} 字符)")


if __name__ == "__main__":
    main()

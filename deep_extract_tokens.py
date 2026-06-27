#!/usr/bin/env python3
"""
deep_extract_tokens.py - 从 blocks_cache.json 提取所有 image/video token（含 View 容器内的）

输出：
  - all_tokens.json: {"<token>": {"type": "image|video", "doc_token": "..."}}
"""
import argparse
import json
import sys
from pathlib import Path


def walk_blocks(blocks, visit):
    """DFS 遍历所有 block，调 visit(block)"""
    for b in blocks:
        visit(b)
        # 递归子块
        children = b.get("children", []) or []
        for cid in children:
            # 实际嵌套在 blocks 里的子 block 在数据里已经平铺或在父级 children
            # 这里只需要 visit 父，子级由 fetch 时一次性返回
            pass


def extract(blocks):
    """从块数据里提取所有 image/video token"""
    out = {}  # token -> {"type": ..., "doc_token": ...}
    for b in blocks:
        bt = b.get("block_type")
        # type 27 = image, 33 = view, 24/25 = grid columns
        if bt == 27:  # image
            img = b.get("image", {})
            token = img.get("token") or img.get("file_token")
            if token:
                out[token] = {"type": "image", "block_id": b["block_id"]}
        elif bt == 23:  # video
            v = b.get("video", {})
            token = v.get("token") or v.get("file_token")
            if token:
                out[token] = {"type": "video", "block_id": b["block_id"]}
        # table cell 里的图片也走 type 27，会被 block 自身包括
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("root", help="Wiki 根目录")
    p.add_argument("--cache", default="blocks_cache.json")
    p.add_argument("--out", default="all_tokens.json")
    args = p.parse_args()

    root = Path(args.root)
    cache = root / args.cache
    data = json.loads(cache.read_text(encoding="utf-8"))

    # 每个 doc_token 配对
    map_data = json.loads((root / "doc_token_map.json").read_text(encoding="utf-8"))
    title_to_doc = {n["title"].strip(): n["doc_token"] for n in map_data}

    all_tokens = {}
    for doc_token, info in data.items():
        title = info["title"]
        blocks = info["blocks"]
        toks = extract(blocks)
        for t, meta in toks.items():
            if t not in all_tokens:
                all_tokens[t] = {"type": meta["type"], "doc_token": doc_token, "title": title}
        img = sum(1 for m in toks.values() if m["type"] == "image")
        vid = sum(1 for m in toks.values() if m["type"] == "video")
        print(f"  {title[:30]:30s}  图片 {img:3d}  视频 {vid:3d}")

    out_path = root / args.out
    out_path.write_text(json.dumps(all_tokens, ensure_ascii=False, indent=2), encoding="utf-8")
    img_n = sum(1 for v in all_tokens.values() if v["type"] == "image")
    vid_n = sum(1 for v in all_tokens.values() if v["type"] == "video")
    print(f"\n📊 总计: {len(all_tokens)} tokens ({img_n} 图片 + {vid_n} 视频)")
    print(f"📄 写入: {out_path}")


if __name__ == "__main__":
    main()

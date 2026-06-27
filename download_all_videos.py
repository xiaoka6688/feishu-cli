#!/usr/bin/env python3
"""从 blocks_cache.json 提取所有 video token 并批量下载"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

FEISHU_CLI = r"C:\Users\wang'zhong'wei\go\bin\feishu-cli.exe"
APP_ID = os.environ.get("FEISHU_APP_ID", "")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")

# Fallback: 从 ~/.feishu-cli/config.yaml 读
if not APP_ID or not APP_SECRET:
    try:
        import yaml
        cfg = Path.home() / ".feishu-cli" / "config.yaml"
        if cfg.exists():
            d = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
            APP_ID = APP_ID or d.get("app_id", "")
            APP_SECRET = APP_SECRET or d.get("app_secret", "")
    except ImportError:
        # 没装 yaml 时请配环境变量 FEISHU_APP_ID/FEISHU_APP_SECRET
        # 或跑: pip install pyyaml
        pass


def main():
    p = argparse.ArgumentParser()
    p.add_argument("root", help="Wiki 根目录")
    p.add_argument("--cache", default="blocks_cache.json")
    args = p.parse_args()

    root = Path(args.root)
    cache = root / args.cache
    data = json.loads(cache.read_text(encoding="utf-8"))
    map_data = json.loads((root / "doc_token_map.json").read_text(encoding="utf-8"))
    title_to_doc = {n["title"].strip(): n["doc_token"] for n in map_data}

    env = os.environ.copy()
    env["FEISHU_APP_ID"] = APP_ID
    env["FEISHU_APP_SECRET"] = APP_SECRET

    # 收集所有视频 token
    videos = []  # (token, name, doc_token, title)
    for dt, info in data.items():
        for b in info["blocks"]:
            if b.get("block_type") == 23:
                f = b.get("file", {})
                tok = f.get("token")
                if tok:
                    videos.append((tok, f.get("name", "video.mp4"), dt, info["title"]))

    print(f"🎬 视频总数: {len(videos)}")
    success = 0
    failed = []
    for i, (tok, name, dt, title) in enumerate(videos, 1):
        # 找对应 MD 路径，决定资产子目录
        md_rel = None
        for n in map_data:
            if n["doc_token"] == dt:
                md_rel = n.get("md_rel") or f"{n['title'].strip()}.md"
                break
        if not md_rel:
            # 简化：放在根 assets
            asset_dir = root / "assets"
        else:
            asset_dir = root / "assets" / Path(md_rel).parent

        asset_dir.mkdir(parents=True, exist_ok=True)
        out_file = asset_dir / f"feishu_{tok}.mp4"

        if out_file.exists() and out_file.stat().st_size > 1024:
            print(f"  [{i:2d}/{len(videos)}] ⏭  {tok[:12]} ({out_file.stat().st_size:,} B)")
            success += 1
            continue

        cmd = [FEISHU_CLI, "doc", "media-download", tok,
               "--doc-token", dt, "--doc-type", "docx",
               "-o", str(out_file)]
        try:
            r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)
        except subprocess.TimeoutExpired:
            r = None

        if out_file.exists() and out_file.stat().st_size > 1024:
            print(f"  [{i:2d}/{len(videos)}] ✅ {tok[:12]} ({out_file.stat().st_size:,} B) - {name[:30]}")
            success += 1
        else:
            err = (r.stderr.strip() or r.stdout.strip() or "unknown")[:80] if r else "timeout"
            print(f"  [{i:2d}/{len(videos)}] ❌ {tok[:12]} - {err}")
            failed.append(tok)

    print(f"\n📊 视频: 成功 {success}/{len(videos)}, 失败 {len(failed)}")
    if failed:
        print(f"   失败: {failed[:5]}")


if __name__ == "__main__":
    main()

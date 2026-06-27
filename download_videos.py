#!/usr/bin/env python3
"""批量下载 Wiki 树里 feishu://media 视频文件"""
import os
import re
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

# 视频 token → 对应 MD 路径（用于匹配 doc_token）
VIDEOS = [
    {"token": "Wb5QbtztMoPFCtxU6zYcDLQXn4c", "md": "短视频系统介绍.md", "name": "无限克隆数字人使用教程_11"},
    {"token": "QWCcbnBCeocCsSxlLhScDrHpn2f", "md": "短视频系统介绍.md", "name": "换脸数字人"},
    {"token": "LOFubV7HUoOqRVxOhLDc3eDunqD", "md": "短视频系统介绍.md", "name": "换脸数字人2"},
    {"token": "PABKbvARCoU8P5xL5B3c2NGNnYg", "md": "数字人短视频系统操作手册（PC端）.md", "name": "数字人教程"},
    {"token": "SWbabtkehoprWGxM5GJc61rfnie", "md": "形象克隆进阶篇.md", "name": "出镜01"},
]


def main():
    if len(sys.argv) < 2:
        print("用法: python download_videos.py <root>")
        sys.exit(1)
    root = Path(sys.argv[1])

    # 加载 doc_token_map
    map_path = root / "doc_token_map.json"
    if not map_path.exists():
        print(f"❌ 缺少 {map_path}")
        sys.exit(1)
    import json
    title_to_doc = {}
    for item in json.loads(map_path.read_text(encoding="utf-8")):
        title_to_doc[item["title"].strip()] = item["doc_token"]

    env = os.environ.copy()
    env["FEISHU_APP_ID"] = APP_ID
    env["FEISHU_APP_SECRET"] = APP_SECRET

    success = 0
    for i, v in enumerate(VIDEOS, 1):
        # 找 doc_token
        doc_token = title_to_doc.get(Path(v["md"]).stem.strip(), "")
        if not doc_token:
            # 模糊匹配
            for t, dt in title_to_doc.items():
                if v["md"].replace(".md", "") in t or t in v["md"].replace(".md", ""):
                    doc_token = dt
                    break
        if not doc_token:
            print(f"  [{i}/{len(VIDEOS)}] ⚠️  找不到 doc_token: {v['md']}")
            continue

        # 输出路径：assets/<子目录>/feishu_<video_token>.<ext>
        md_path = root / v["md"]
        if not md_path.exists():
            # 尝试子目录
            for p in root.rglob(v["md"]):
                md_path = p
                break
        rel = md_path.relative_to(root)
        asset_subdir = root / "assets" / rel.parent

        # 视频用 mp4 扩展
        out_file = asset_subdir / f"feishu_{v['token']}.mp4"
        asset_subdir.mkdir(parents=True, exist_ok=True)

        if out_file.exists() and out_file.stat().st_size > 0:
            print(f"  [{i}/{len(VIDEOS)}] ⏭  跳过: {out_file.name}")
            success += 1
            continue

        cmd = [FEISHU_CLI, "doc", "media-download", v["token"],
               "--doc-token", doc_token,
               "--doc-type", "docx",
               "-o", str(out_file)]
        r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)
        if out_file.exists() and out_file.stat().st_size > 0:
            size = out_file.stat().st_size
            print(f"  [{i}/{len(VIDEOS)}] ✅ {out_file.name} ({size:,} B)")
            success += 1
        else:
            err = (r.stderr.strip() or r.stdout.strip())[:100]
            print(f"  [{i}/{len(VIDEOS)}] ❌ {v['token'][:12]}... {err}")

    print(f"\n📊 视频: 成功 {success}/{len(VIDEOS)}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
download_wiki_images.py - 拿到 doc_token_map.json 后批量下载 Wiki 树图片

逻辑:
  1. 读 doc_token_map.json: [{title, doc_token, node_token}, ...]
  2. 扫描 root/**/*.md，提取每张图片的 token
  3. 对每个 MD 文件名匹配 title → 拿到 doc_token
  4. 用 feishu-cli doc media-download 下载到 assets/<子目录>/feishu_<token>.png
"""
import argparse
import json
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
TOKEN_RE = re.compile(r'feishu_([A-Za-z0-9]{27})')


def main():
    p = argparse.ArgumentParser()
    p.add_argument("root", help="Wiki 根目录")
    p.add_argument("--map", default="doc_token_map.json", help="doc_token 映射文件")
    args = p.parse_args()

    root = Path(args.root)
    map_path = root / args.map
    if not map_path.exists():
        print(f"❌ 映射文件不存在: {map_path}")
        sys.exit(1)

    # 读映射：title (去除尾随空格) -> doc_token
    raw = json.loads(map_path.read_text(encoding="utf-8"))
    title_to_doc = {}
    for item in raw:
        title = item["title"].strip()
        title_to_doc[title] = item["doc_token"]
    print(f"📄 加载映射: {len(title_to_doc)} 个 title")

    env = os.environ.copy()
    env["FEISHU_APP_ID"] = APP_ID
    env["FEISHU_APP_SECRET"] = APP_SECRET

    # 扫描所有 MD
    md_files = sorted(root.rglob("*.md"))
    # 过滤掉映射文件
    md_files = [m for m in md_files if m.name != args.map and m.name != "image_map.json"]

    success = 0
    failed = []
    total = 0

    for md in md_files:
        # 找 doc_token
        doc_token = title_to_doc.get(md.stem.strip(), "")
        if not doc_token:
            print(f"  ⚠️  找不到 doc_token: {md.name}")

        # 提取 token
        text = md.read_text(encoding="utf-8", errors="ignore")
        tokens = sorted(set(TOKEN_RE.findall(text)))
        if not tokens:
            continue
        total += len(tokens)

        # 资产子目录
        rel = md.relative_to(root)
        asset_subdir = root / "assets" / rel.parent
        asset_subdir.mkdir(parents=True, exist_ok=True)

        for j, token in enumerate(tokens, 1):
            out_file = asset_subdir / f"feishu_{token}.png"
            if out_file.exists() and out_file.stat().st_size > 0:
                success += 1
                continue

            cmd = [FEISHU_CLI, "doc", "media-download", token,
                   "--doc-type", "docx",
                   "-o", str(out_file)]
            if doc_token:
                cmd = [FEISHU_CLI, "doc", "media-download", token,
                       "--doc-token", doc_token,
                       "--doc-type", "docx",
                       "-o", str(out_file)]

            try:
                r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60)
            except subprocess.TimeoutExpired:
                r = None

            if out_file.exists() and out_file.stat().st_size > 0:
                success += 1
            else:
                failed.append((md.name, token, (r.stderr.strip()[:60] if r else "timeout")))

    print()
    print(f"📊 总计: {total} 个 token, 成功 {success}, 失败 {len(failed)}")
    if failed:
        print("失败样本（前 5）:")
        for n, t, e in failed[:5]:
            print(f"  - {n} | {t[:12]}... | {e}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
extract_blocks_titles.py - 取所有 docx 块数据中提取标题、image/video token 等
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


def fetch_all_blocks(doc_token: str, env: dict) -> list:
    """分页拿全所有块"""
    blocks = []
    page_token = ""
    while True:
        path = f"/open-apis/docx/v1/documents/{doc_token}/blocks?page_size=500"
        if page_token:
            path += f"&page_token={page_token}"
        cmd = [FEISHU_CLI, "api", "GET", path]
        r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=120)
        try:
            data = json.loads(r.stdout)
        except json.JSONDecodeError:
            print(f"  ⚠️ 解析失败: {r.stdout[:200]}")
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


def main():
    p = argparse.ArgumentParser()
    p.add_argument("root", help="Wiki 根目录")
    p.add_argument("--out", default="blocks_cache.json")
    args = p.parse_args()

    root = Path(args.root)
    map_path = root / "doc_token_map.json"
    if not map_path.exists():
        print(f"❌ 缺少 {map_path}")
        sys.exit(1)
    nodes = json.loads(map_path.read_text(encoding="utf-8"))

    env = os.environ.copy()
    env["FEISHU_APP_ID"] = APP_ID
    env["FEISHU_APP_SECRET"] = APP_SECRET

    out = {}
    for i, node in enumerate(nodes, 1):
        title = node["title"].strip()
        doc_token = node["doc_token"]
        # 跳过 sheet
        if not doc_token:
            print(f"  [{i:2d}/{len(nodes)}] ⏭  {title} (无 doc_token)")
            continue
        # 只处理 docx 节点
        if not re.match(r'^[A-Za-z0-9]{27}$', doc_token):
            print(f"  [{i:2d}/{len(nodes)}] ⏭  {title} (非标准 token: {doc_token[:12]})")
            continue

        print(f"  [{i:2d}/{len(nodes)}] 📥 {title} ...", end="", flush=True)
        try:
            blocks = fetch_all_blocks(doc_token, env)
            out[doc_token] = {"title": title, "blocks": blocks, "node_token": node["node_token"]}
            print(f" {len(blocks)} blocks")
        except Exception as e:
            print(f" ❌ {e}")

    out_path = root / args.out
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n📦 缓存: {out_path}  ({len(out)} 个文档)")


if __name__ == "__main__":
    main()

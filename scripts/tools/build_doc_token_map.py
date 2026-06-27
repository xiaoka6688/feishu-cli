#!/usr/bin/env python3
"""
build_doc_token_map.py - 递归列 Wiki 树里每个节点的 doc_token

用法:
  python build_doc_token_map.py <space_id>
  # → 写到 ./doc_token_map.json
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


def wiki_get(node_token: str, env: dict) -> dict:
    cmd = [FEISHU_CLI, "wiki", "get", node_token]
    r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)
    out = r.stdout
    m_token = re.search(r"文档 Token:\s*(\S+)", out)
    m_title = re.search(r"标题:\s*(.+?)(?:\s*$)", out, re.MULTILINE)
    m_has_child = re.search(r"有子节点:\s*(\S+)", out)
    return {
        "node_token": node_token,
        "doc_token": m_token.group(1).strip() if m_token else "",
        "title": m_title.group(1).strip() if m_title else "",
        "has_child": m_has_child.group(1).strip().lower() == "true" if m_has_child else False,
    }


def list_children(space_id: str, parent_token: str, env: dict) -> list:
    """通过 api 透传列子节点（GET 带 query）"""
    path = f"/open-apis/wiki/v2/spaces/{space_id}/nodes?parent_node_token={parent_token}&page_size=50"
    cmd = [FEISHU_CLI, "api", "GET", path, "--as", "bot"]
    r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        print(f"  ⚠️ 解析失败: {r.stdout[:200]}")
        return []
    items = data.get("data", {}).get("items", []) or []
    return [{"node_token": it.get("node_token", ""),
             "title": it.get("title", ""),
             "obj_type": it.get("obj_type", ""),
             "obj_token": it.get("obj_token", ""),
             "has_child": it.get("has_child", False)} for it in items]


def walk(space_id: str, node_token: str, env: dict, out: list, depth: int = 0):
    info = wiki_get(node_token, env)
    out.append(info)
    indent = "  " * depth
    print(f"{indent}📄 {info['title'][:40]} (doc_token={info['doc_token'][:12] if info['doc_token'] else '-'}...)")
    if info["has_child"]:
        children = list_children(space_id, node_token, env)
        for c in children:
            walk(space_id, c["node_token"], env, out, depth + 1)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root-token", required=True, help="Wiki 根节点 token")
    p.add_argument("--space-id", required=True, help="空间 ID")
    p.add_argument("--out", default="doc_token_map.json")
    args = p.parse_args()

    env = os.environ.copy()
    env["FEISHU_APP_ID"] = APP_ID
    env["FEISHU_APP_SECRET"] = APP_SECRET

    out: list = []
    print(f"🚶 遍历 Wiki 树: {args.root_token} (space={args.space_id})")
    walk(args.space_id, args.root_token, env, out)
    print(f"   共 {len(out)} 个节点")

    # 写文件
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"📄 映射文件: {args.out}")


if __name__ == "__main__":
    main()

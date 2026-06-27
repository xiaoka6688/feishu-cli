#!/usr/bin/env python3
"""
build_sheet_token_map.py - 跑 read-rich 拿 (row, col, embed_id) 顺序，
并跑 doc media-download 按同样顺序拿 file_token 列表，建立 embed_id → file_token 映射
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
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
SS_TOKEN = "LyppsrqKbhUvzmtfmmIcmcThnpc"

SHEETS = [
    ("76ec0d", "中年老妇女", 200, 36),
    ("6FZq6E", "中年老妇女（副本2）", 200, 36),
    ("k2Vhow", "中年老妇女（副本）", 200, 36),
    ("s4NXm2", "中国形象", 200, 36),
    ("iFeNfn", "中年男士", 200, 36),
    ("SEMqvr", "思维认知（男）", 200, 36),
    ("1xbmFi", "思维认知（女）", 213, 36),
    ("m5ZanZ", "年轻美女", 213, 36),
]


def read_v2_embed_ids(ss_token, sheet_id, n_rows, n_cols, env):
    """用 V2 API 按 (row, col) 顺序拿 embed_id 列表"""
    range_str = f"{sheet_id}!A1:AJ{n_rows}"
    r = subprocess.run([FEISHU_CLI, "api", "GET",
                        f"/open-apis/sheets/v2/spreadsheets/{ss_token}/values/{range_str}?valueRenderOption=ToString"],
                       env=env, capture_output=True, text=True, timeout=300)
    try:
        d = json.loads(r.stdout)
    except json.JSONDecodeError:
        return []
    values = d.get("data", {}).get("valueRange", {}).get("values", [])
    out = []
    for ri, row in enumerate(values, 1):
        for ci, v in enumerate(row, 1):
            if isinstance(v, list) and v and isinstance(v[0], dict) and v[0].get("type") == "embed-image":
                out.append((ri, ci, v[0]["id"]))
    return out


def read_rich_tokens(ss_token, sheet_id, n_rows, n_cols, env):
    """用 read-rich 拿 file_token 列表（按 cell 顺序）"""
    IMAGE_RE = re.compile(r"\[image:\s*([A-Za-z0-9]+)\]")
    range_str = f"{sheet_id}!A1:AJ{n_rows}"
    r = subprocess.run([FEISHU_CLI, "sheet", "read-rich", ss_token, sheet_id, range_str],
                       env=env, capture_output=True, text=True, timeout=600)
    tokens = IMAGE_RE.findall(r.stdout)
    return tokens


def main():
    p = argparse.ArgumentParser()
    p.add_argument("root", help="Wiki 根目录")
    args = p.parse_args()

    root = Path(args.root)
    env = os.environ.copy()
    env["FEISHU_APP_ID"] = APP_ID
    env["FEISHU_APP_SECRET"] = APP_SECRET

    # 输出：{sheet_id: {"positions": [(row, col, embed_id)], "tokens": [file_token]}}
    out = {}
    for sheet_id, name, n_rows, n_cols in SHEETS:
        print(f"  📥 {name} ({n_rows}×{n_cols}) ...", end="", flush=True)
        positions = read_v2_embed_ids(SS_TOKEN, sheet_id, n_rows, n_cols, env)
        # 多次重试 read-rich 直到 token 数 ≥ position 数
        tokens = []
        for attempt in range(5):
            tokens = read_rich_tokens(SS_TOKEN, sheet_id, n_rows, n_cols, env)
            if len(tokens) >= len(positions):
                break
            print(f" (重试{attempt+1}: token {len(tokens)} < position {len(positions)})", end="", flush=True)
            time.sleep(2)
        print(f" positions={len(positions)}, tokens={len(tokens)}")
        out[sheet_id] = {"name": name, "positions": positions, "tokens": tokens}

    cache = root / "sheet_token_map.json"
    cache.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    total_p = sum(len(d["positions"]) for d in out.values())
    total_t = sum(len(d["tokens"]) for d in out.values())
    print(f"\n📄 {cache}  (positions: {total_p}, tokens: {total_t})")


if __name__ == "__main__":
    main()

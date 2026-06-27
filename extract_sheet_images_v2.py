#!/usr/bin/env python3
"""
extract_sheet_images_v2.py - 分块读 sheet cell，提取全部 image token
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


def col_letter(n):
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def read_chunk_imgs(ss_token, sheet_id, range_str, env):
    """读一段 cell，返回 {row: {col: [token,...]}}"""
    r = subprocess.run([FEISHU_CLI, "sheet", "read-rich", ss_token, sheet_id, range_str],
                       env=env, capture_output=True, text=True, timeout=300)
    IMAGE_RE = re.compile(r"\[image:\s*([A-Za-z0-9]+)\]")
    out = {}
    current_row = None
    current_col = 0
    for line in r.stdout.splitlines():
        m_row = re.match(r"\s*行\s+(\d+):", line)
        if m_row:
            current_row = int(m_row.group(1))
            out.setdefault(current_row, {})
            current_col = 0
            continue
        m_col = re.match(r"\s*列\s+(\d+):\s*(.*)", line)
        if m_col:
            current_col = int(m_col.group(1))
            cell_content = m_col.group(2).strip()
            imgs = IMAGE_RE.findall(cell_content)
            if imgs and current_row:
                out[current_row][current_col] = imgs
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("root", help="Wiki 根目录")
    args = p.parse_args()

    root = Path(args.root)
    env = os.environ.copy()
    env["FEISHU_APP_ID"] = APP_ID
    env["FEISHU_APP_SECRET"] = APP_SECRET

    sheets = [
        ("LyppsrqKbhUvzmtfmmIcmcThnpc", "76ec0d", "中年老妇女", 200, 36),
        ("LyppsrqKbhUvzmtfmmIcmcThnpc", "6FZq6E", "中年老妇女（副本2）", 200, 36),
        ("LyppsrqKbhUvzmtfmmIcmcThnpc", "k2Vhow", "中年老妇女（副本）", 200, 36),
        ("LyppsrqKbhUvzmtfmmIcmcThnpc", "s4NXm2", "中国形象", 200, 36),
        ("LyppsrqKbhUvzmtfmmIcmcThnpc", "iFeNfn", "中年男士", 200, 36),
        ("LyppsrqKbhUvzmtfmmIcmcThnpc", "SEMqvr", "思维认知（男）", 200, 36),
        ("LyppsrqKbhUvzmtfmmIcmcThnpc", "1xbmFi", "思维认知（女）", 213, 36),
        ("LyppsrqKbhUvzmtfmmIcmcThnpc", "m5ZanZ", "年轻美女", 213, 36),
    ]

    all_data = {}
    for ss_token, sheet_id, sheet_name, n_rows, n_cols in sheets:
        # 分块读: 一次 10 行（read-rich 一次输出太长会丢图）
        sheet_data = {}
        CHUNK = 10
        for start in range(1, n_rows + 1, CHUNK):
            end = min(start + CHUNK - 1, n_rows)
            range_str = f"{sheet_id}!A{start}:AJ{end}"
            # 多次重试直到拿全
            for attempt in range(5):
                try:
                    chunk = read_chunk_imgs(ss_token, sheet_id, range_str, env)
                except subprocess.TimeoutExpired:
                    time.sleep(2)
                    continue
                break
            for r, cols in chunk.items():
                sheet_data.setdefault(r, {})
                sheet_data[r].update(cols)
        total_imgs = sum(len(toks) for row in sheet_data.values() for toks in row.values())
        print(f"  {sheet_name:30s} {total_imgs:3d} 张图")
        all_data[sheet_id] = {"name": sheet_name, "rows": sheet_data, "n_cols": n_cols}

    # 写缓存
    cache_path = root / "sheet_cells.json"
    cache_path.write_text(json.dumps(all_data, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(sum(len(t) for row in d["rows"].values() for t in row.values()) for d in all_data.values())
    print(f"\n📊 缓存: {cache_path} (总计 {total} 张图)")


if __name__ == "__main__":
    main()

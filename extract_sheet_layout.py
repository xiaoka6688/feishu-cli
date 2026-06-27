#!/usr/bin/env python3
"""
extract_sheet_layout.py - 用 V2 API 拿 sheet 全 cell values (含 embed-image id)
然后匹配已下载的 file_token，按位置嵌入重建 MD
"""
import argparse
import datetime
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


def main():
    p = argparse.ArgumentParser()
    p.add_argument("root", help="Wiki 根目录")
    args = p.parse_args()

    root = Path(args.root)
    env = os.environ.copy()
    env["FEISHU_APP_ID"] = APP_ID
    env["FEISHU_APP_SECRET"] = APP_SECRET

    # Step 1: 拉全 embed-image id 列表
    layout = {}  # {sheet_id: {row: {col: [embed_id, ...]}}}
    for sheet_id, name, n_rows, n_cols in SHEETS:
        print(f"  📥 {name} ({n_rows}×{n_cols}) ...", end="", flush=True)
        range_str = f"{sheet_id}!A1:AJ{n_rows}"
        r = subprocess.run([FEISHU_CLI, "api", "GET",
                            f"/open-apis/sheets/v2/spreadsheets/{SS_TOKEN}/values/{range_str}?valueRenderOption=ToString"],
                           env=env, capture_output=True, text=True, timeout=300)
        try:
            data = json.loads(r.stdout)
        except json.JSONDecodeError:
            print(f" ❌ parse error")
            continue
        if data.get("code") != 0:
            print(f" ❌ {data.get('msg')}")
            continue
        values = data.get("data", {}).get("valueRange", {}).get("values", [])

        sheet_imgs = {}
        for ri, row in enumerate(values, 1):
            for ci, v in enumerate(row, 1):
                if isinstance(v, list) and v and v[0].get("type") == "embed-image":
                    embed_id = str(v[0]["id"])
                    sheet_imgs.setdefault(ri, {})[ci] = [embed_id]
                elif isinstance(v, dict) and v.get("type") == "embed-image":
                    sheet_imgs.setdefault(ri, {})[ci] = [str(v["id"])]
        layout[sheet_id] = {"name": name, "rows": sheet_imgs, "values": values}
        total = sum(len(t) for row in sheet_imgs.values() for t in row.values())
        print(f" {total} 张图")

    # Step 2: 通过 V2 API 拿每个 embed_id 对应的 file_token
    # 用 sheet image list 命令（sheet_id 必填）
    embed_to_token = {}
    print("\n  🔗 映射 embed_id → file_token")
    for sheet_id, info in layout.items():
        # 收集此 sheet 全部 embed id
        ids = set()
        for row in info["rows"].values():
            for toks in row.values():
                for t in toks:
                    ids.add(t)
        if not ids:
            continue
        # 用 sheet image list 拿
        # 实际 API: GET /open-apis/sheets/v3/spreadsheets/{token}/sheets/{sheet_id}/images
        r = subprocess.run([FEISHU_CLI, "api", "GET",
                            f"/open-apis/sheets/v3/spreadsheets/{SS_TOKEN}/sheets/{sheet_id}/images"],
                           env=env, capture_output=True, text=True, timeout=60)
        try:
            d = json.loads(r.stdout)
        except json.JSONDecodeError:
            d = {}
        items = d.get("data", {}).get("items", []) or []
        for it in items:
            eid = str(it.get("image_id") or it.get("id") or it.get("file_token"))
            ftok = it.get("file_token") or eid
            embed_to_token[eid] = ftok
        # 备选：每个 embed id 都按它本身去下载
        for eid in ids:
            if eid not in embed_to_token:
                embed_to_token[eid] = eid  # 暂时映射自身，后面通过文件名匹配
    print(f"  映射: {len(embed_to_token)} 个")

    # Step 3: 写缓存
    out = {
        "embed_to_token": embed_to_token,
        "layout": {sid: {"name": v["name"], "rows": v["rows"]} for sid, v in layout.items()},
    }
    cache = root / "sheet_layout.json"
    cache.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n📄 缓存: {cache}")


if __name__ == "__main__":
    main()

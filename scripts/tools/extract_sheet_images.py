#!/usr/bin/env python3
"""
extract_sheet_images.py - 提取 sheet 里所有 image token 并下载
"""
import argparse
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

# 列字母
def col_letter(n):
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def main():
    p = argparse.ArgumentParser()
    p.add_argument("root", help="Wiki 根目录")
    args = p.parse_args()

    root = Path(args.root)
    sheets_info = [
        # (spreadsheet_token, sheet_id, sheet_name, title)
        ("LyppsrqKbhUvzmtfmmIcmcThnpc", "76ec0d", "中年老妇女", "数字人模型"),
        ("LyppsrqKbhUvzmtfmmIcmcThnpc", "6FZq6E", "中年老妇女（副本2）", "数字人模型"),
        ("LyppsrqKbhUvzmtfmmIcmcThnpc", "k2Vhow", "中年老妇女（副本）", "数字人模型"),
        ("LyppsrqKbhUvzmtfmmIcmcThnpc", "s4NXm2", "中国形象", "数字人模型"),
        ("LyppsrqKbhUvzmtfmmIcmcThnpc", "iFeNfn", "中年男士", "数字人模型"),
        ("LyppsrqKbhUvzmtfmmIcmcThnpc", "SEMqvr", "思维认知（男）", "数字人模型"),
        ("LyppsrqKbhUvzmtfmmIcmcThnpc", "1xbmFi", "思维认知（女）", "数字人模型"),
        ("LyppsrqKbhUvzmtfmmIcmcThnpc", "m5ZanZ", "年轻美女", "数字人模型"),
        ("NhjXshc8PhmhhStog9jcum8tnMf", None, "形象定制网址链接", "形象定制网址链接"),
    ]

    env = os.environ.copy()
    env["FEISHU_APP_ID"] = APP_ID
    env["FEISHU_APP_SECRET"] = APP_SECRET

    # 资产目录
    asset_dir = root / "assets" / "常见数字人形象"
    asset_dir.mkdir(parents=True, exist_ok=True)

    IMAGE_RE = re.compile(r"\[image:\s*([A-Za-z0-9]+)\]")

    all_tokens = []
    for ss_token, sheet_id, sheet_name, title in sheets_info:
        if sheet_id is None:
            # 形象定制网址链接：读全部
            r = subprocess.run([FEISHU_CLI, "sheet", "list-sheets", ss_token],
                               env=env, capture_output=True, text=True, timeout=30)
            # 找第一张表的 ID
            m = re.search(r"ID:\s*([A-Za-z0-9]+)", r.stdout)
            if not m:
                print(f"  ⚠️  找不到 {sheet_name} 的 sheet_id")
                continue
            sheet_id = m.group(1)
            # 形象定制网址链接只有 1 张表，行 200 列 20
            range_str = f"{sheet_id}!A1:T200"
        else:
            # 数字人模型：36 列
            range_str = f"{sheet_id}!A1:AJ200"

        print(f"  📥 读 {sheet_name} ({range_str}) ...", end="", flush=True)
        r = subprocess.run([FEISHU_CLI, "sheet", "read-rich", ss_token, sheet_id, range_str],
                           env=env, capture_output=True, text=True, timeout=180)
        # 提取 image token
        tokens = IMAGE_RE.findall(r.stdout)
        print(f" {len(tokens)} 张图")
        for t in tokens:
            all_tokens.append((t, sheet_name, ss_token))

    print(f"\n📊 总计: {len(all_tokens)} 个图片 token")

    # 下载
    success = 0
    for i, (tok, sheet_name, ss_token) in enumerate(all_tokens, 1):
        out_file = asset_dir / f"feishu_{tok}.png"
        if out_file.exists() and out_file.stat().st_size > 0:
            success += 1
            continue

        # sheet 里的图片用 sheet token 就能下
        cmd = [FEISHU_CLI, "sheet", "image", "download", tok,
               "--output", str(out_file)]
        # 试 feishu-cli 的 sheet image 命令
        try:
            r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60)
        except Exception as e:
            r = None
        if out_file.exists() and out_file.stat().st_size > 0:
            print(f"  [{i:3d}/{len(all_tokens)}] ✅ {tok[:12]} ({out_file.stat().st_size:,} B)")
            success += 1
        else:
            # 退路：用 doc media-download
            cmd2 = [FEISHU_CLI, "doc", "media-download", tok, "-o", str(out_file)]
            r2 = subprocess.run(cmd2, env=env, capture_output=True, text=True, timeout=60)
            if out_file.exists() and out_file.stat().st_size > 0:
                print(f"  [{i:3d}/{len(all_tokens)}] ✅ {tok[:12]} (via doc) ({out_file.stat().st_size:,} B)")
                success += 1
            else:
                err = ((r.stderr if r else "") + (r2.stderr if r2 else ""))[:100].strip()
                print(f"  [{i:3d}/{len(all_tokens)}] ❌ {tok[:12]} {err}")

    print(f"\n📊 下载: 成功 {success}/{len(all_tokens)}")


if __name__ == "__main__":
    main()

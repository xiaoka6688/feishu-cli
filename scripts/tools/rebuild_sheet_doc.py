#!/usr/bin/env python3
"""
rebuild_sheet_doc.py - 重建 sheet 文档，把图片嵌进对应单元格

策略:  读每个 sheet 的 cell image token，按行列位置插入到 markdown 表格
"""
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# feishu-cli 路径（优先用 PATH，找不到再 fallback）
FEISHU_CLI = shutil.which("feishu-cli") or r"C:\Users\wang'zhong'wei\go\bin\feishu-cli.exe"
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
ASSET_REL = "assets/常见数字人形象"


def col_letter(n):
    """1->A, 2->B..."""
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def read_sheet_cell_images(ss_token, sheet_id, n_rows, n_cols, env):
    """读 cell 富文本，返回 {row: {col: [token,...]}}"""
    last_col = col_letter(n_cols)
    range_str = f"{sheet_id}!A1:{last_col}{n_rows}"
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


def read_sheet_cell_text(ss_token, sheet_id, n_rows, n_cols, env):
    """读 cell 纯文本，返回 {row: {col: text}}"""
    last_col = col_letter(n_cols)
    range_str = f"{sheet_id}!A1:{last_col}{n_rows}"
    r = subprocess.run([FEISHU_CLI, "sheet", "read", ss_token, f"{sheet_id}!A1:{last_col}{n_rows}",
                        "-o", "json"],
                       env=env, capture_output=True, text=True, timeout=300)
    try:
        data = json.loads(r.stdout)
        values = data.get("values", [])
    except json.JSONDecodeError:
        return {}
    out = {}
    for ri, row in enumerate(values, 1):
        # 飞书 sheet 返回的 row 可能是 list 或 dict
        if isinstance(row, list):
            out[ri] = {}
            for ci, v in enumerate(row, 1):
                if v is None:
                    out[ri][ci] = ""
                elif isinstance(v, dict):
                    out[ri][ci] = str(v)
                else:
                    out[ri][ci] = str(v)
        else:
            out[ri] = {1: str(row) if row else ""}
    return out


def build_sheet_md(title, sheets, env, asset_rel):
    """sheets: [(name, ss_token, sheet_id, n_rows, n_cols), ...]"""
    lines = [f"---"]
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines.append(f"title: {title}")
    lines.append(f"created: {now}")
    lines.append(f"source: feishu")
    lines.append(f"source_url: feishu://sheet/{sheets[0][1]}")
    lines.append("tags:")
    lines.append("  - feishu")
    lines.append("  - imported")
    lines.append("  - wiki")
    lines.append(f"---")
    lines.append("")

    for sheet_name, ss_token, sheet_id, n_rows, n_cols in sheets:
        lines.append(f"## {sheet_name}")
        lines.append("")
        print(f"  读 {sheet_name} ({n_rows}行 × {n_cols}列) ...", end="", flush=True)
        cell_imgs = read_sheet_cell_images(ss_token, sheet_id, n_rows, n_cols, env)
        cell_text = read_sheet_cell_text(ss_token, sheet_id, n_rows, n_cols, env)
        total_imgs = sum(len(toks) for row in cell_imgs.values() for toks in row.values())
        print(f" {total_imgs} 张图")

        # 渲染表格：每行最大列数，cell 含文本或图片
        # 找最大有内容的行
        max_row = max(n_rows, max(cell_imgs.keys(), default=0), max(cell_text.keys(), default=0))
        for ri in range(1, max_row + 1):
            imgs = cell_imgs.get(ri, {})
            texts = cell_text.get(ri, {})
            # 找有内容的列
            used_cols = set(imgs.keys()) | set(texts.keys())
            if not used_cols:
                continue
            row_cells = []
            for ci in range(1, n_cols + 1):
                if ci in imgs:
                    for tok in imgs[ci]:
                        row_cells.append(f"![](./{asset_rel}/feishu_{tok}.png)")
                elif ci in texts and texts[ci]:
                    row_cells.append(texts[ci])
            if row_cells:
                lines.append("| " + " | ".join(row_cells) + " |")
        lines.append("")

    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("root", help="Wiki 根目录")
    args = p.parse_args()

    root = Path(args.root)
    env = os_environ = {**__import__("os").environ,
                          "FEISHU_APP_ID": APP_ID, "FEISHU_APP_SECRET": APP_SECRET}

    # 数字人模型
    sheets_数字人 = [
        ("中年老妇女", "LyppsrqKbhUvzmtfmmIcmcThnpc", "76ec0d", 200, 36),
        ("中年老妇女（副本2）", "LyppsrqKbhUvzmtfmmIcmcThnpc", "6FZq6E", 200, 36),
        ("中年老妇女（副本）", "LyppsrqKbhUvzmtfmmIcmcThnpc", "k2Vhow", 200, 36),
        ("中国形象", "LyppsrqKbhUvzmtfmmIcmcThnpc", "s4NXm2", 200, 36),
        ("中年男士", "LyppsrqKbhUvzmtfmmIcmcThnpc", "iFeNfn", 200, 36),
        ("思维认知（男）", "LyppsrqKbhUvzmtfmmIcmcThnpc", "SEMqvr", 200, 36),
        ("思维认知（女）", "LyppsrqKbhUvzmtfmmIcmcThnpc", "1xbmFi", 213, 36),
        ("年轻美女", "LyppsrqKbhUvzmtfmmIcmcThnpc", "m5ZanZ", 213, 36),
    ]
    print("=== 重建 数字人模型.md ===")
    md = build_sheet_md("数字人模型", sheets_数字人, env, ASSET_REL)
    out = root / "常见数字人形象" / "数字人模型.md"
    out.write_text(md, encoding="utf-8")
    print(f"  ✅ {out}  ({len(md):,} 字符)")
    print(f"\n📊 完成")


if __name__ == "__main__":
    main()

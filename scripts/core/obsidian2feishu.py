#!/usr/bin/env python3
"""
obsidian2feishu.py - Obsidian 笔记 → 飞书文档同步

把 Obsidian Vault 里的 Markdown 笔记同步上传到飞书云端。
支持：
  - 增量同步（只传新文件）
  - 幂等性（已同步的跳过）
  - Frontmatter 标记（source: obsidian 的笔记才同步）
  - 写回同步状态（feishu_doc_id / feishu_url / last_synced）

用法：
  # 同步整个目录
  python obsidian2feishu.py ~/Documents/ObsidianVault/Notes/

  # 同步单个文件
  python obsidian2feishu.py my-note.md

  # 只看不同步
  python obsidian2feishu.py vault/ --dry-run

  # 强制重新同步（覆盖已同步的）
  python obsidian2feishu.py vault/ --force

工作原理：
  1. 扫描指定目录（或单个文件）的 .md 文件
  2. 读取 frontmatter：
     - 跳过没有 `source: obsidian` 的（避免误传）
     - 跳过已有 `feishu_doc_id` 的（已同步）
  3. 调用 `feishu-cli doc import` 上传
  4. 解析输出拿到 doc_id
  5. 写回 frontmatter：feishu_doc_id + feishu_url + last_synced
"""

import argparse
import datetime
import re
import subprocess
import sys
from pathlib import Path


# ============================================
# Frontmatter 工具
# ============================================

def parse_frontmatter(content: str) -> tuple[dict, str]:
    """解析 YAML frontmatter，返回 (dict, 正文)"""
    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    # parts[0] = "" (开头 --- 前的空)
    # parts[1] = "key: value\n..."
    # parts[2] = "\n# 正文..."
    fm_text = parts[1].strip()
    body = parts[2].lstrip("\n")

    # 简单解析（不依赖 PyYAML）
    fm = {}
    for line in fm_text.split("\n"):
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip()

    return fm, body


def write_frontmatter(content: str, fm: dict) -> str:
    """把 dict 写回 frontmatter"""
    fm_text = "\n".join(f"{k}: {v}" for k, v in fm.items())
    return f"---\n{fm_text}\n---\n\n{content.split('---', 2)[-1].lstrip(chr(10))}"


def update_frontmatter_field(content: str, updates: dict) -> str:
    """更新 frontmatter 中的某些字段，保留其他"""
    fm, body = parse_frontmatter(content)
    fm.update(updates)
    fm_text = "\n".join(f"{k}: {v}" for k, v in fm.items())
    return f"---\n{fm_text}\n---\n\n{body}"


# ============================================
# 文件扫描
# ============================================

def collect_md_files(target: Path) -> list:
    """收集 .md 文件（支持单文件 / 目录）"""
    if target.is_file():
        return [target]

    if target.is_dir():
        return sorted(target.rglob("*.md"))

    print(f"❌ 路径不存在: {target}", file=sys.stderr)
    sys.exit(1)


def should_sync(content: str, force: bool) -> tuple[bool, str]:
    """判断是否应该同步此文件

    返回 (是否同步, 原因)
    """
    fm, _ = parse_frontmatter(content)

    # 必须有 source: obsidian
    if fm.get("source") != "obsidian":
        return False, "无 source: obsidian frontmatter 标记"

    # 已有 feishu_doc_id 跳过
    if fm.get("feishu_doc_id") and not force:
        return False, f"已同步过 (feishu_doc_id={fm.get('feishu_doc_id')[:12]}...)"

    return True, "ok"


# ============================================
# feishu-cli 调用
# ============================================

def feishu_import(md_file: Path, title: str = None) -> dict:
    """调用 feishu-cli doc import 上传文件

    返回 {"ok": bool, "doc_id": str, "url": str, "error": str}
    """
    cmd = ["feishu-cli", "doc", "import", str(md_file)]
    if title:
        cmd.extend(["--title", title])
    cmd.extend(["--output", "json"])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 分钟
            encoding="utf-8"
        )
    except FileNotFoundError:
        return {"ok": False, "error": "feishu-cli 未安装，请先运行 setup-all.sh"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "上传超时（5分钟）"}

    if result.returncode != 0:
        return {"ok": False, "error": result.stderr or result.stdout}

    # 解析 stdout（feishu-cli 的 JSON 在末尾，前面是文本日志）
    import json
    # 找 JSON 开始位置（{ 字符）—— JSON 在最末尾
    stdout = result.stdout
    json_start = stdout.rfind("{")
    if json_start < 0:
        return {"ok": False, "error": f"未找到 JSON 输出: {stdout[:200]}"}

    try:
        output = json.loads(stdout[json_start:])
        if output.get("document_id"):
            doc_id = output["document_id"]
            # feishu-cli 不在 JSON 里给 URL，自己拼
            url = f"https://feishu.cn/docx/{doc_id}"
            return {
                "ok": True,
                "doc_id": doc_id,
                "url": url
            }
        return {"ok": False, "error": "JSON 中无 document_id 字段"}
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"无法解析 JSON: {e}\n输出: {stdout[json_start:json_start+200]}"}


# ============================================
# 主流程
# ============================================

def sync_file(md_file: Path, args) -> bool:
    """同步单个文件，返回是否成功"""
    try:
        content = md_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print(f"  ⚠ 跳过（编码问题）: {md_file.name}")
        return False

    sync, reason = should_sync(content, args.force)
    if not sync:
        if args.verbose:
            print(f"  ⏭ 跳过: {md_file.name} ({reason})")
        return False

    fm, _ = parse_frontmatter(content)
    title = fm.get("title") or md_file.stem

    print(f"  📤 上传: {md_file.name} (title={title})")

    if args.dry_run:
        print(f"     [DRY-RUN] 不会真的上传")
        return False

    result = feishu_import(md_file, title)

    if not result["ok"]:
        print(f"  ✗ 失败: {result.get('error', '未知错误')}")
        return False

    # 写回 frontmatter
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_content = update_frontmatter_field(content, {
        "feishu_doc_id": result["doc_id"],
        "feishu_url": result["url"],
        "last_synced": now
    })

    md_file.write_text(new_content, encoding="utf-8")

    print(f"  ✓ 成功: {result['doc_id']}")
    print(f"     URL: {result['url']}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Obsidian 笔记 → 飞书文档同步工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 同步整个 vault
  python obsidian2feishu.py ~/Documents/ObsidianVault/Notes/

  # 同步单个文件
  python obsidian2feishu.py my-note.md

  # 预览要同步什么
  python obsidian2feishu.py vault/ --dry-run

  # 强制重新同步（覆盖已有 feishu_doc_id）
  python obsidian2feishu.py vault/ --force

前置要求:
  1. 笔记 frontmatter 必须有: source: obsidian
  2. 已安装 feishu-cli 并配好凭证
  3. 已开通 docx 相关 scope

Frontmatter 格式示例:
  ---
  title: 我的笔记
  source: obsidian          ← 必须
  tags: [tutorial, feishu]
  ---

  # 正文开始...
        """
    )

    parser.add_argument("target", help="目标路径（文件或目录）")
    parser.add_argument("--dry-run", action="store_true",
                        help="只看不同步")
    parser.add_argument("--force", action="store_true",
                        help="强制同步（覆盖已同步的）")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="显示跳过原因等详细信息")

    args = parser.parse_args()

    target = Path(args.target).expanduser().resolve()
    md_files = collect_md_files(target)

    print(f"🔍 扫描到 {len(md_files)} 个 Markdown 文件")
    print(f"📂 目标: {target}")
    print(f"⚙  模式: {'DRY-RUN（不同步）' if args.dry_run else 'FORCE（覆盖）' if args.force else 'NORMAL（增量）'}")
    print()

    success = 0
    skipped = 0
    failed = 0

    for md_file in md_files:
        # 跳过 .obsidian 目录（Obsidian 配置目录）
        if ".obsidian" in md_file.parts:
            continue

        if sync_file(md_file, args):
            success += 1
        elif args.verbose:
            skipped += 1

    print()
    print(f"📊 同步完成:")
    print(f"   ✓ 成功: {success}")
    if args.dry_run:
        print(f"   🔍 预览模式（未实际同步）")
    elif args.force:
        print(f"   ⚠ 强制模式（已覆盖）")
    else:
        print(f"   ⏭ 跳过（已同步）: {skipped}")
    print(f"   ✗ 失败: {failed}")


if __name__ == "__main__":
    main()

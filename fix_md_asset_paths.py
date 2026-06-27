#!/usr/bin/env python3
"""
fix_md_asset_paths.py - 修复所有 MD 里的资源路径，按 MD 相对 vault 深度加 ../

策略:
  - 找每个 MD 引用 ./assets/... 的位置
  - 计算 MD 相对 vault 根的深度
  - 把 ./assets/ 替换为 ../../assets/（按深度）
"""
import re
import sys
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print("用法: python fix_md_asset_paths.py <vault_root>")
        sys.exit(1)
    root = Path(sys.argv[1])
    md_files = [p for p in root.rglob("*.md") if not p.name.endswith(".json")]

    fixed = 0
    for p in md_files:
        rel = p.relative_to(root)
        # 计算深度
        depth = len(rel.parent.parts) if str(rel.parent) != "." else 0
        # 修正
        text = p.read_text(encoding="utf-8", errors="ignore")
        new_text = text
        if depth == 0:
            # vault 根的 MD，./assets/ 是对的
            target = "./assets/"
        else:
            # vault 子目录 MD
            target = "../" * depth + "assets/"

        # 替换 ./assets/ → target
        # 同时把没 ./ 的 assets/ 也加上 target
        if depth > 0:
            new_text = re.sub(r"\./assets/", target, new_text)
        if new_text != text:
            p.write_text(new_text, encoding="utf-8")
            fixed += 1
            print(f"  ✅ {rel}  → {target}")

    print(f"\n📊 修复 {fixed} 个 MD")


if __name__ == "__main__":
    main()

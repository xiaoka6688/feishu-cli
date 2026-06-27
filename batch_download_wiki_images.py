#!/usr/bin/env python3
"""
batch_download_wiki_images.py - 递归扫描目录里所有 MD 中的飞书图片 token，批量下载

用法:
  python batch_download_wiki_images.py <vault_subdir> [<vault_subdir> ...]
  python batch_download_wiki_images.py "G:/飞书知识库/AI数字人 使用手册"

规则:
  - 扫描 root/**/*.md
  - 提取 feishu_<27位token> 图片引用
  - 映射到 <root>/assets/<同名子目录>/feishu_<token>.png
  - 跳过已存在
"""
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
TOKEN_RE = re.compile(r"feishu_([A-Za-z0-9]{27})")


def find_doc_token(md_path: Path) -> str:
    """从 MD frontmatter 或文件路径里拿 doc_token"""
    # 1. 先看 frontmatter 里有没有 feishu_doc_id
    try:
        text = md_path.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"feishu_doc_id:\s*(\S+)", text)
        if m:
            return m.group(1).strip()
    except Exception:
        pass
    # 2. 没法自动拿时，返回空字符串（调用方自己想办法）
    return ""


def main():
    if len(sys.argv) < 2:
        print("用法: python batch_download_wiki_images.py <root_dir>")
        sys.exit(1)

    env = os.environ.copy()
    env["FEISHU_APP_ID"] = APP_ID
    env["FEISHU_APP_SECRET"] = APP_SECRET

    for root_arg in sys.argv[1:]:
        root = Path(root_arg)
        if not root.exists():
            print(f"❌ 路径不存在: {root}")
            continue

        # 收集所有 token -> (md_path, doc_token)
        token_map: dict = {}  # token -> (md_path, doc_token)
        md_files = list(root.rglob("*.md"))
        print(f"📂 扫描: {root}")
        print(f"   找到 {len(md_files)} 个 MD 文件")

        for md in md_files:
            try:
                text = md.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            tokens = set(TOKEN_RE.findall(text))
            if not tokens:
                continue
            doc_token = find_doc_token(md)
            for t in tokens:
                if t not in token_map:
                    token_map[t] = (md, doc_token)
                # 同一 token 被多个文件引用没关系，跳过重复下载

        if not token_map:
            print("   未发现需要下载的图片")
            continue

        print(f"   累计 {len(token_map)} 个不重复图片 token")

        # 资产目录布局: assets/<MD相对路径的父目录>/feishu_<token>.png
        success = 0
        failed = []
        for i, (token, (md, doc_token)) in enumerate(token_map.items(), 1):
            # 资产子目录：用 md.relative_to(root).parent 的镜像
            rel = md.relative_to(root)
            asset_subdir = root / "assets" / rel.parent
            asset_subdir.mkdir(parents=True, exist_ok=True)
            out_file = asset_subdir / f"feishu_{token}.png"

            if out_file.exists() and out_file.stat().st_size > 0:
                print(f"  [{i:3d}/{len(token_map)}] ⏭  {out_file.name}")
                success += 1
                continue

            cmd = [FEISHU_CLI, "doc", "media-download", token,
                   "--doc-type", "docx",
                   "-o", str(out_file)]
            if doc_token:
                cmd[cmd.index("--doc-type")] = "--doc-token"  # 这种插法不对，单独处理
                cmd = [FEISHU_CLI, "doc", "media-download", token,
                       "--doc-token", doc_token,
                       "--doc-type", "docx",
                       "-o", str(out_file)]

            try:
                r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60)
            except subprocess.TimeoutExpired:
                r = None

            if out_file.exists() and out_file.stat().st_size > 0:
                size = out_file.stat().st_size
                print(f"  [{i:3d}/{len(token_map)}] ✅ {out_file.name} ({size:,} B)")
                success += 1
            else:
                err = (r.stderr.strip() if r else "timeout")[:80]
                print(f"  [{i:3d}/{len(token_map)}] ❌ {token[:12]}... {err}")
                failed.append(token)

        print(f"   完成: 成功 {success}/{len(token_map)}, 失败 {len(failed)}")
        if failed:
            print(f"   失败列表: {failed[:5]}{'...' if len(failed) > 5 else ''}")
        print()


if __name__ == "__main__":
    main()

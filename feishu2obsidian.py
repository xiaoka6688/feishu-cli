#!/usr/bin/env python3
"""
feishu2obsidian.py - 飞书导出的 Markdown 转 Obsidian 兼容格式

解决问题：
1. 飞书导出的 URL 会被 URL 编码（%2F, %3A 等），Obsidian 无法直接点击
2. 飞书私有 <image token="xxx"/> 标签 Obsidian 不认识
3. 飞书的 lark-table Obsidian 能渲染但更推荐标准 GFM 表格

用法：
    python feishu2obsidian.py input.md -o output.md
    python feishu2obsidian.py input.md --download-images  # 同时下载图片到 ./assets/

作者：feishu-cli 部署实战
"""

import argparse
import re
import sys
import urllib.parse
from pathlib import Path


def url_decode_text(text: str) -> str:
    """解码 Markdown 文本中的 URL 编码字符（%2F, %3A, %20, %29 等）

    飞书导出时会把 URL 编码为 %2F、%3A、%29 等，导致 Obsidian 链接无法点击
    飞书还会重复渲染同一个链接：[text](url)[ ](url)
    """
    # 简化策略：解码所有 %XX 序列（%29 → )，%2F → /，%3A → : 等）
    # 飞书会重复渲染同一链接：[`SKILL.md`](url)[ ](url)，直接全局解码 URL 编码即可
    text = urllib.parse.unquote(text)

    # 清理飞书重复渲染：删除 `[ ](url)` 模式（空文本的链接）
    # 这种是飞书特有的"双链接"渲染
    text = re.sub(r'\[ \]\([^)]+\)', '', text)

    return text


def transform_images(text: str) -> str:
    """飞书私有 <image> 标签转 Obsidian 兼容的 ![](url) 格式

    注意：飞书 image token 需要通过 media-download 接口下载真实文件
    这里先把标签转成占位符，让用户后续批量下载
    """
    def replace_image(match):
        token = match.group(1) or ""
        width = match.group(2) or ""
        height = match.group(3) or ""
        align = match.group(4) or ""

        # 占位符：用户后续用 feishu-cli media-download 下载
        # Obsidian 格式：![[filename.png]] 或 ![alt](url)
        # 这里用 Obsidian wiki-link 格式，让用户手动补充
        return f"<!-- 飞书图片 token: {token} | {width}x{height} {align} -->\n![飞书图片 {token[:8]}](./assets/feishu_{token}.png)"

    # 飞书 image 标签：<image token="xxx" width="x" height="y" align="z"/>
    text = re.sub(
        r'<image\s+token="([^"]+)"(?:\s+width="([^"]+)")?(?:\s+height="([^"]+)")?(?:\s+align="([^"]+)")?\s*/>',
        replace_image,
        text
    )
    return text


def transform_lark_table(text: str) -> str:
    """飞书 lark-table 转标准 GFM 表格（可选，Obsidian 也支持 lark-table）"""
    # Obsidian 已经能渲染 lark-table，暂不转换
    # 保留原样以确保兼容性
    return text


def add_obsidian_frontmatter(text: str, title: str, source_url: str = "") -> str:
    """添加 Obsidian 友好的 YAML frontmatter

    飞书导出的 MD 文件首行通常是 '---'，那是飞书的引用块分割线，
    不是 YAML frontmatter。需要做配对检查。
    """
    # 1. 严格按 YAML frontmatter 格式判断：开头 ---, 紧跟 ---, 中间是 YAML
    if text.lstrip().startswith("---"):
        lines = text.lstrip().split("\n")
        # 找首段 '---' 配对
        i = 0
        while i < len(lines) and lines[i].strip() == "":
            i += 1
        if i < len(lines) and lines[i].strip() == "---":
            j = i + 1
            while j < len(lines) and lines[j].strip() != "---":
                j += 1
            if j < len(lines):
                # 找到了配对，检查中间内容是否像 YAML（key: value 形式）
                yaml_content = "\n".join(lines[i+1:j])
                if ":" in yaml_content and re.search(r"^\w[\w\s]*:", yaml_content, re.MULTILINE):
                    # 看起来是真的 YAML frontmatter，跳过
                    return text

    import datetime
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # 飞书导出的首段 '---' (飞书分割线) 也要剥离，避免和我们新加的冲突
    body = text
    lines = text.split("\n")
    i = 0
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    if i < len(lines) and lines[i].strip() == "---":
        j = i + 1
        while j < len(lines) and lines[j].strip() != "---":
            j += 1
        if j < len(lines):
            # 飞书自带的元信息（标题/创建时间/来源/标签），保留
            k = j + 1
            while k < len(lines) and lines[k].strip() == "":
                k += 1
            body = "\n".join(lines[k:])

    source_url_line = (f"source_url: {source_url}" if source_url else "").rstrip()
    frontmatter_lines = [
        "---",
        f"title: {title}",
        f"created: {now}",
        "source: feishu",
    ]
    if source_url_line:
        frontmatter_lines.append(source_url_line)
    frontmatter_lines.extend([
        "tags:",
        "  - feishu",
        "  - imported",
        "---",
        "",
    ])
    frontmatter = "\n".join(frontmatter_lines)

    return frontmatter + body


def main():
    parser = argparse.ArgumentParser(
        description="飞书 Markdown 转 Obsidian 兼容格式",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基本转换
  python feishu2obsidian.py feishu-doc.md -o obsidian-doc.md

  # 转换 + 加 Obsidian frontmatter
  python feishu2obsidian.py feishu-doc.md -o obsidian-doc.md \\
    --title "我的笔记" --source-url "https://feishu.cn/docx/xxx"
        """
    )

    parser.add_argument("input", help="输入的飞书 Markdown 文件")
    parser.add_argument("-o", "--output", help="输出文件（默认: stdout）")
    parser.add_argument("--title", help="文档标题（用于 Obsidian frontmatter）")
    parser.add_argument("--source-url", help="飞书原文档 URL（用于 frontmatter）")
    parser.add_argument("--no-frontmatter", action="store_true",
                        help="不添加 Obsidian frontmatter")

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ 错误: 文件不存在: {args.input}", file=sys.stderr)
        sys.exit(1)

    # 读取
    content = input_path.read_text(encoding="utf-8")
    print(f"📖 读取: {args.input} ({len(content)} 字符)")

    # 转换
    content = url_decode_text(content)
    print("  ✓ URL 解码完成")

    content = transform_images(content)
    print("  ✓ 飞书 <image> 标签转 Obsidian 格式")

    content = transform_lark_table(content)
    print("  ✓ lark-table 保留兼容")

    if not args.no_frontmatter:
        title = args.title or input_path.stem
        content = add_obsidian_frontmatter(content, title, args.source_url or "")
        print("  ✓ 添加 Obsidian frontmatter")

    # 输出
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(content, encoding="utf-8")
        print(f"✅ 已保存: {args.output} ({len(content)} 字符)")
    else:
        print("---")
        print(content)


if __name__ == "__main__":
    main()

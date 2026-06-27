#!/usr/bin/env python3
"""
install.py - 一步安装 feishu-cli 全部依赖（Windows 优化版）

功能:
  1. 检查 Go / Node.js / Python
  2. 编译 feishu-cli 并安装到 GOPATH/bin
  3. 安装 lark-cli（npm）
  4. 创建 feishu-cli 配置文件
  5. 一次性申请所有 OAuth scope
  6. 跑 doctor 健康检查

用法:
  python install.py                          # 全自动
  python install.py --app-id "cli_xxx" --app-secret "xxx"   # 跳过手动输入
  python install.py --skip-auth              # 跳过 OAuth（之后手动跑 python scripts/tools/auth_all.py）
"""
import argparse
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

# feishu-cli 路径：优先用环境变量，否则用默认
import shutil as _shutil
import os as _os
FEISHU_CLI = _os.environ.get("FEISHU_CLI_PATH") or (
    r"C:\Users\wang'zhong'wei\go\bin\feishu-cli.exe" if _os.name == "nt"
    else (_shutil.which("feishu-cli") or "feishu-cli")
)
GOPATH_BIN = _os.environ.get(
    "GOPATH_BIN",
    r"C:\Users\wang'zhong'wei\go\bin" if _os.name == "nt"
    else str(Path.home() / "go" / "bin")
)


def step(msg):
    print(f"\n[{time.strftime('%H:%M:%S')}] {msg}")


def run(cmd, **kwargs):
    """运行命令并返回结果"""
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def check_env():
    """检查 Go / Node / Python"""
    step("1/6 检查环境...")
    ok = True
    for name, cmd in [
        ("Go", ["go", "version"]),
        ("Node.js", ["node", "--version"]),
        ("npm", ["npm", "--version"]),
        ("Python", [sys.executable, "--version"]),
    ]:
        r = run(cmd)
        if r.returncode == 0:
            print(f"  ✅ {name}: {r.stdout.strip()}")
        else:
            print(f"  ❌ {name}: 未安装")
            ok = False
    if not ok:
        print("\n请先安装缺失的工具：")
        print("  Go:      winget install --id GoLang.Go")
        print("  Node.js: winget install --id OpenJS.NodeJS.LTS")
        print("  Python:  https://www.python.org/downloads/")
        sys.exit(1)


def build_feishu_cli():
    """编译并安装 feishu-cli"""
    step("2/6 编译安装 feishu-cli...")
    here = Path(__file__).parent
    # 编译
    r = run(["go", "build", "-o", "./bin/feishu-cli.exe", "."], cwd=str(here), timeout=600)
    if r.returncode != 0:
        print(f"  ❌ 编译失败:\n{r.stderr[:500]}")
        sys.exit(1)
    print("  ✅ 编译成功")
    # 复制到 GOPATH/bin
    Path(GOPATH_BIN).mkdir(parents=True, exist_ok=True)
    src = here / "bin" / "feishu-cli.exe"
    dst = Path(GOPATH_BIN) / "feishu-cli.exe"
    if not src.exists():
        print(f"  ❌ 找不到编译产物: {src}")
        sys.exit(1)
    import shutil
    shutil.copy(src, dst)
    print(f"  ✅ 安装到 {GOPATH_BIN}")


def install_lark_cli():
    """安装 lark-cli"""
    step("3/6 安装 lark-cli（飞书官方）...")
    r = run(["npm", "install", "-g", "@larksuite/cli"], timeout=300)
    if r.returncode == 0:
        print(f"  ✅ lark-cli 安装成功")
    else:
        print(f"  ⚠️  安装失败: {r.stderr[:200]}")
        print("     可手动: npm install -g @larksuite/cli")


def setup_config(app_id: str, app_secret: str):
    """配置飞书 App 凭证"""
    step("4/6 配置 App 凭证...")
    if not app_id:
        app_id = input("  请输入 App ID (cli_xxx 开头): ").strip()
    if not app_secret:
        app_secret = input("  请输入 App Secret: ").strip()
    if not app_id or not app_secret:
        print("  ⚠️  跳过凭证配置")
        return
    # 调 feishu-cli 初始化
    r = run([FEISHU_CLI, "config", "init"], timeout=30)
    config_path = Path.home() / ".feishu-cli" / "config.yaml"
    if not config_path.exists():
        print("  ❌ feishu-cli config init 失败")
        return
    # 写入凭证
    text = config_path.read_text(encoding="utf-8")
    text = text.replace('app_id: ""', f'app_id: "{app_id}"', 1)
    text = text.replace('app_secret: ""', f'app_secret: "{app_secret}"', 1)
    config_path.write_text(text, encoding="utf-8")
    print(f"  ✅ 凭证写入 {config_path}")


def run_oauth():
    """OAuth 授权（一次性申请所有 scope）"""
    step("5/6 一次性 OAuth 授权（35 个 scope）...")
    # 调 auth_all.py
    here = Path(__file__).parent
    auth_script = here / "auth_all.py"
    if not auth_script.exists():
        print("  ⚠️  auth_all.py 不存在，跳过")
        return
    r = run([sys.executable, str(auth_script)])
    if r.returncode != 0:
        print(f"  ⚠️  授权脚本退出码: {r.returncode}")


def verify():
    """跑 doctor 健康检查"""
    step("6/6 验证安装...")
    r = run([FEISHU_CLI, "doctor"], timeout=60)
    print(r.stdout)
    if "全部通过" in r.stdout or "all pass" in r.stdout.lower():
        print("  🎉 doctor 全部通过！")
    else:
        print("  ⚠️  doctor 有警告，但通常不影响基本使用")


def main():
    p = argparse.ArgumentParser(description="一步安装 feishu-cli")
    p.add_argument("--app-id", help="飞书 App ID（跳过手动输入）")
    p.add_argument("--app-secret", help="飞书 App Secret（跳过手动输入）")
    p.add_argument("--skip-auth", action="store_true", help="跳过 OAuth（之后手动跑 python scripts/tools/auth_all.py）")
    p.add_argument("--skip-build", action="store_true", help="跳过编译 feishu-cli（已经装好）")
    args = p.parse_args()

    if platform.system() != "Windows":
        print("⚠️  本脚本主要适配 Windows。其他系统请手动按 README 操作。")

    check_env()
    if not args.skip_build:
        build_feishu_cli()
    install_lark_cli()
    setup_config(args.app_id, args.app_secret)
    if not args.skip_auth:
        run_oauth()
    else:
        print("\n  跳过 OAuth。稍后跑: python scripts/tools/auth_all.py")
    verify()

    print()
    print("=" * 60)
    print("🎉 安装完成！")
    print()
    print("下一步:")
    print("  1. 跑 doctor 验证:    feishu-cli doctor")
    print("  2. 同步 Wiki 树:      python scripts/core/sync_feishu_to_obsidian.py --wiki <WIKI_TOKEN>")
    print("  3. 同步单文档:        python scripts/core/sync_feishu_to_obsidian.py --doc <DOC_TOKEN>")
    print("  4. 完整文档:          cat TROUBLESHOOTING.md")
    print("=" * 60)


if __name__ == "__main__":
    main()

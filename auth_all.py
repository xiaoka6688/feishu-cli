#!/usr/bin/env python3
"""
auth_all.py - 一次性申请所有飞书 OpenAPI 所需 scope 的 OAuth 授权

解决：原本需要分别授权 3 次（wiki / drive / sheets）才能跑全功能，
     现在一条命令搞定。

用法:
  python auth_all.py            # 发起授权并轮询
  python auth_all.py --no-wait  # 只拿 device_code，不轮询（手动轮询）
"""
import argparse
import os
import subprocess
import sys
import time

# feishu-cli 路径：优先用环境变量，否则用默认
import shutil as _shutil
import os as _os
FEISHU_CLI = _os.environ.get("FEISHU_CLI_PATH") or (
    r"C:\Users\wang'zhong'wei\go\bin\feishu-cli.exe" if _os.name == "nt"
    else (_shutil.which("feishu-cli") or "feishu-cli")
)

# 一次申请所有 scope，覆盖：
#  - wiki 知识库（读、创建、节点管理）
#  - docs 文档（读、导出、上传、评论、权限）
#  - drive 云盘（文件下载、上传、metadata）
#  - sheets 电子表格（读写、metadata）
#  - media 媒体（下载/上传）
#  - space 空间
#  - auth 用户身份
ALL_SCOPES = " ".join([
    "auth:user.id:read",
    # docs
    "docs:document.comment:create",
    "docs:document.comment:delete",
    "docs:document.comment:read",
    "docs:document.comment:update",
    "docs:document.comment:write_only",
    "docs:document.content:read",
    "docs:document.media:download",
    "docs:document.media:upload",
    "docs:document:copy",
    "docs:document:export",
    "docs:document:import",
    "docs:event:subscribe",
    "docs:permission.member:auth",
    "docs:permission.member:create",
    "docs:permission.member:transfer",
    "docx:document:readonly",
    # drive
    "drive:drive",
    "drive:drive.metadata:readonly",
    "drive:file:download",
    "drive:file:upload",
    "drive:file:view_record:readonly",
    # sheets
    "sheets:spreadsheet",
    "sheets:spreadsheet:readonly",
    # space
    "space:document:delete",
    "space:document:move",
    "space:folder:create",
    # wiki
    "wiki:member:create",
    "wiki:member:retrieve",
    "wiki:member:update",
    "wiki:node:copy",
    "wiki:node:create",
    "wiki:node:move",
    "wiki:node:read",
    "wiki:node:retrieve",
    "wiki:node:update",
    "wiki:space:read",
    "wiki:space:retrieve",
])


def step(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")


def main():
    p = argparse.ArgumentParser(description="一次性申请所有飞书 OpenAPI 所需 scope")
    p.add_argument("--no-wait", action="store_true", help="只拿 device_code，不轮询")
    p.add_argument("--device-code", help="用已有 device_code 继续轮询")
    args = p.parse_args()

    # Step 1: 检查 feishu-cli 可用
    if not os.path.exists(FEISHU_CLI):
        print(f"❌ feishu-cli 未安装: {FEISHU_CLI}")
        print("   请先跑: go install github.com/xiaoka6688/feishu-cli@latest")
        sys.exit(1)

    # Step 2: 检查 auth 状态
    step("检查当前授权状态...")
    r = subprocess.run([FEISHU_CLI, "auth", "status"], capture_output=True, text=True, timeout=30)
    if "valid" in r.stdout.lower() or "已登录" in r.stdout:
        print(f"  ✅ 已登录:\n{r.stdout}")
        ans = input("  已有授权，是否强制重新授权？(y/N): ").strip().lower()
        if ans != "y":
            print("  跳过授权。")
            return

    # Step 3: 发起授权
    if args.device_code:
        device_code = args.device_code
        step(f"使用已有 device_code: {device_code[:20]}...")
    else:
        step("发起一次性授权申请（35 个 scope）...")
        r = subprocess.run([FEISHU_CLI, "auth", "login", "--no-wait", "--json",
                            "--scope", ALL_SCOPES],
                           capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            print(f"❌ 发起失败: {r.stderr}")
            sys.exit(1)
        import json
        try:
            data = json.loads(r.stdout)
        except json.JSONDecodeError:
            print(f"❌ 解析失败: {r.stdout[:200]}")
            sys.exit(1)
        device_code = data["device_code"]
        user_code = data["user_code"]
        verify_url = data["verification_uri_complete"]

        print()
        print("=" * 60)
        print("🌐 请在浏览器打开以下链接完成授权：")
        print(f"   {verify_url}")
        print()
        print(f"   验证码（如果链接没自动填）: {user_code}")
        print("=" * 60)
        print()

        if args.no_wait:
            print("  --no-wait 模式：拿 device_code 后退出。")
            print(f"  稍后跑: python auth_all.py --device-code {device_code}")
            return

    # Step 4: 轮询
    step("开始轮询授权状态（请在浏览器完成授权）...")
    print("  提示：完成浏览器授权后会自动检测到，最多等 10 分钟")
    print()
    r = subprocess.run([FEISHU_CLI, "auth", "login", "--device-code", device_code, "--json"],
                       capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        print(f"❌ 轮询失败: {r.stderr}")
        sys.exit(1)
    import json
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        print(f"❌ 解析失败: {r.stdout[:200]}")
        sys.exit(1)

    if data.get("event") == "authorization_complete":
        step("🎉 授权完成！")
        expires = data.get("expires_at", "")
        refresh = data.get("refresh_expires_at", "")
        granted = data.get("granted_scopes", [])
        print(f"  Token 有效期至: {expires}")
        print(f"  Refresh Token 有效期至: {refresh}")
        print(f"  已授权 scope 数: {len(granted)}")
        if granted:
            print()
            print("  授权范围（前 20 个）:")
            for s in granted[:20]:
                print(f"    - {s}")
            if len(granted) > 20:
                print(f"    ... 还有 {len(granted) - 20} 个")
    else:
        print(f"⚠️  未完成授权: {data}")
        sys.exit(1)


if __name__ == "__main__":
    main()

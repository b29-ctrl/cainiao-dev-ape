# -*- coding: utf-8 -*-
r"""
启动项目（S2 前置：风格选型 → 调试台）
=====================================

一句话：双开之后先让你选风格，选完再进调试台改界面。

用法
----
1) 指定项目目录（项目里应该有 00_环境.md）
     python "启动项目.py" --dir "D:\你的项目" --port 8792

2) 不指定 = 当前目录
     python "启动项目.py"

它会做三件事
------------
1. 看项目里的 00_环境.md 有没有写「风格：」
2. 没写 → 弹出 UI风格选型.html，选完点「确定风格」会把文本复制到剪贴板，
   你粘到 00_环境.md 里即可
3. 起来调试台（安全编辑模式），地址 http://127.0.0.1:<port>/

说明
----
- 零依赖，只要 Python 3.9+
- 选型页打不开也没关系，调试台照样起
"""
import argparse
import os
import re
import pathlib
import subprocess
import sys
import time
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
CONSOLE = os.path.join(HERE, "UI调试台.py")


def find_picker():
    """在几种常见目录结构里找 UI风格选型.html（技能包 / 平铺目录都能找到）。"""
    cands = [
        os.path.join(HERE, "..", "03_模板", "UI风格选型.html"),   # 技能包结构
        os.path.join(HERE, "..", "UI风格选型.html"),             # 平铺结构
        os.path.join(HERE, "UI风格选型.html"),                   # 同目录
    ]
    for c in cands:
        c = os.path.normpath(c)
        if os.path.exists(c):
            return c
    return os.path.normpath(cands[0])


PICKER = find_picker()


def is_placeholder(val):
    """占位符不算已选风格（S-1 模板、手写的 ____ 之类）。"""
    v = (val or "").strip()
    if not v:
        return True
    if set(v) <= set("_-—"):          # 全是下划线/横线
        return True
    if "____" in v or "选型" in v or "复制过来" in v:
        return True
    return False


def has_style(project_dir):
    """项目里 00_环境.md 是否已经写了风格。"""
    for name in ("00_环境.md", "00_环境.MD"):
        p = os.path.join(project_dir, name)
        if not os.path.exists(p):
            continue
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except Exception:
            return False
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("风格") and (":" in s or "：" in s):
                if not re.match(r"^风格\s*[：:]", s):   # 跳过「风格锁定：」等
                    continue
                val = re.sub(r"^风格\s*[：:]", "", s).strip()
                if val and not is_placeholder(val):
                    return True
    return False


def main():
    ap = argparse.ArgumentParser(description="S2 启动：先选风格，再起调试台")
    ap.add_argument("--dir", default=os.getcwd(), help="项目目录（默认当前目录）")
    ap.add_argument("--port", type=int, default=8792, help="调试台端口（默认 8792）")
    ap.add_argument("--unsafe", action="store_true", help="给 AI-A 开发用：关闭安全编辑")
    args = ap.parse_args()

    project = os.path.abspath(args.dir)
    if not os.path.isdir(project):
        print("目录不存在:", project)
        return 1

    # 1. 风格选型
    if has_style(project):
        print("[跳过] 00_环境.md 里已有风格，直接进调试台")
    else:
        print("[提示] 还没定 UI 风格 → 先弹选型页")
        if os.path.exists(PICKER):
            # 用 pathlib 生成 file URI：跨平台（Windows 盘符 / macOS / Linux），
            # 且会自动做中文与空格转义，避免多斜杠或中文文件名打不开。
            url = pathlib.Path(PICKER).as_uri() + "?auto=1"
            webbrowser.open(url)
            time.sleep(1.2)
        else:
            print("[警告] 找不到选型页:", PICKER)

    # 2. 调试台
    if not os.path.exists(CONSOLE):
        print("[错误] 找不到 UI调试台.py:", CONSOLE)
        return 1
    cmd = [sys.executable, CONSOLE, "--dir", project, "--port", str(args.port)]
    if args.unsafe:
        cmd.append("--unsafe")
    print("[启动] 调试台 → http://127.0.0.1:%d/" % args.port)
    if args.unsafe:
        print("       （开发模式：安全编辑已关闭）")
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())

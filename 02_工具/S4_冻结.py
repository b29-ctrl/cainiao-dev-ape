# -*- coding: utf-8 -*-
"""
S4 冻结：把「风格锁定：否」改成「是」+ 打 git 基线 + 生成冻结记录。

用法：
    python S4_冻结.py --dir <项目目录> [--tag s4-freeze] [--dry-run] [--force]

做什么：
    1. 前置检查：00_环境.md 存在、风格已选（非空、非占位符）
    2. 改 风格锁定：否 → 是（含日期与 tag 名）
    3. 有 git 时：git add -A → commit → tag（无 git 时跳过，只留快照）
    4. 写 S4_冻结记录.md（commit、tag、文件清单、SHA256）

退出码：
    0 成功 ｜ 1 前置不满足 ｜ 2 已冻结（未加 --force） ｜ 3 git 操作失败

零依赖，跨平台（Windows / macOS / Linux）。
"""
import argparse
import datetime
import hashlib
import os
import re
import subprocess
import sys

ENV_NAMES = ("00_环境.md", "00_环境.MD")
RECORD = "S4_冻结记录.md"


def die(msg, code=1):
    print("[失败] " + msg)
    sys.exit(code)


def read_env(root):
    for n in ENV_NAMES:
        p = os.path.join(root, n)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8", errors="replace") as fh:
                return p, fh.read()
    return None, None


def parse_style(text):
    """返回 (风格名, 是否占位符, 锁定状态原文)。"""
    name = ""
    locked_raw = ""
    placeholder = False
    for line in text.splitlines():
        s = line.strip()
        m = re.match(r"^风格\s*[：:]\s*(.*)$", s)
        if m and not name:
            v = m.group(1).strip()
            # 去掉注释尾巴（<!-- ... -->）
            v = re.sub(r"<!--.*?-->", "", v).strip()
            if v and ("____" in v or "选型" in v or "复制过来" in v):
                placeholder = True
            elif v:
                name = v
            continue
        m = re.match(r"^风格锁定\s*[：:]\s*(.*)$", s)
        if m and not locked_raw:
            locked_raw = m.group(1).strip()
    return name, placeholder, locked_raw


def is_locked(locked_raw):
    v = (locked_raw or "").lower()
    return bool(re.match(r"^(是|已锁定|true|yes|1)(?:$|\W)", v))


def git(root, *args):
    """在 root 下跑 git，返回 (ok, stdout+stderr)。"""
    try:
        p = subprocess.run(["git"] + list(args), cwd=root,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        return p.returncode == 0, (p.stdout or "") + (p.stderr or "")
    except FileNotFoundError:
        return False, "未安装 git"
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def has_git_repo(root):
    ok, _ = git(root, "rev-parse", "--is-inside-work-tree")
    return ok


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def main():
    ap = argparse.ArgumentParser(description="S4 冻结：锁定风格 + 打基线 + 出记录")
    ap.add_argument("--dir", default=os.getcwd(), help="项目目录（默认当前目录）")
    ap.add_argument("--tag", default="", help="基线 tag 名（默认 s4-freeze-YYYYMMDD-HHMM）")
    ap.add_argument("--dry-run", action="store_true", help="只检查，不改任何文件")
    ap.add_argument("--force", action="store_true", help="已冻结时仍然重做")
    ap.add_argument("--skip-git", action="store_true", help="不碰 git，只改状态并出快照")
    a = ap.parse_args()

    root = os.path.abspath(a.dir)
    if not os.path.isdir(root):
        die("目录不存在：" + root)

    now = datetime.datetime.now()
    tag = a.tag.strip() or ("s4-freeze-" + now.strftime("%Y%m%d-%H%M"))
    stamp = now.strftime("%Y-%m-%d %H:%M")

    # ---------- 前置检查 ----------
    env_path, text = read_env(root)
    if not env_path:
        die("找不到 %s —— 先跑 S-1 环境初始化" % ENV_NAMES[0])

    name, placeholder, locked_raw = parse_style(text)
    if placeholder:
        die("00_环境.md 里的「风格：」还是占位符 —— 先打开 03_模板/UI风格选型.html 选一个")
    if not name:
        die("还没有选风格（「风格：」是空的）—— 先选风格再冻结")
    if is_locked(locked_raw) and not a.force:
        die("已经是冻结状态：「风格锁定：%s」。要重做加 --force" % locked_raw, code=2)

    print("[检查] 目录：%s" % root)
    print("[检查] 风格：%s" % name)
    print("[检查] 当前锁定：%s" % (locked_raw or "（无这一行）"))
    print("[检查] 目标 tag：%s" % tag)

    # ---------- 改状态 ----------
    new_line = "风格锁定：是（S4 冻结，%s，tag %s）" % (stamp, tag)
    lines = text.splitlines()
    done = False
    for i, line in enumerate(lines):
        if re.match(r"^\s*风格锁定\s*[：:]", line):
            lines[i] = new_line
            done = True
            break
    if not done:
        # 没有锁定行：插在「风格：」后面
        for i, line in enumerate(lines):
            if re.match(r"^\s*风格\s*[：:]", line):
                lines.insert(i + 1, new_line)
                done = True
                break
    if not done:
        lines.append(new_line)
    new_text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")

    if a.dry_run:
        print("\n[dry-run] 将写入的这一行：")
        print("  " + new_line)
        print("[dry-run] 未改动任何文件。")
        return

    with open(env_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(new_text)
    print("[完成] 已写入：%s" % new_line)

    # ---------- git 基线 ----------
    commit = ""
    git_ok = False
    if not a.skip_git and has_git_repo(root):
        ok, out = git(root, "add", "-A")
        if not ok:
            print("[警告] git add 失败：" + out.strip()[:200])
        ok, out = git(root, "commit", "-m", "S4 冻结：风格 %s（tag %s）" % (name, tag))
        if ok:
            print("[完成] git commit 成功")
        else:
            msg = out.strip()
            if "nothing to commit" in msg or "无文件要提交" in msg:
                print("[提示] git 无变更可提交（状态行可能已冻结）")
            else:
                print("[警告] git commit 失败：" + msg[:200])
        ok, out = git(root, "tag", "-a", tag, "-m", "S4 冻结基线（风格：%s）" % name, "-f")
        if ok:
            print("[完成] git tag：%s" % tag)
            git_ok = True
        else:
            print("[警告] git tag 失败：" + out.strip()[:200])
        ok, out = git(root, "rev-parse", "--short", "HEAD")
        if ok:
            commit = out.strip()
            print("[完成] commit：%s" % commit)
    else:
        print("[提示] 未检测到 git 仓库（或 --skip-git）→ 跳过 commit/tag，仅生成快照记录")

    # ---------- 冻结记录 ----------
    files = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in (".git", "__pycache__", ".history", "node_modules")]
        for f in fns:
            full = os.path.join(dp, f)
            rel = os.path.relpath(full, root).replace("\\", "/")
            if rel == RECORD:
                continue
            try:
                files.append((rel, os.path.getsize(full), sha256_of(full)))
            except OSError:
                files.append((rel, 0, "（读不到）"))
    files.sort()

    rec = []
    rec.append("# S4 冻结记录")
    rec.append("")
    rec.append("> 由 `工具/S4_冻结.py` 生成。这是不可逆节点：之后要改风格必须走变更单。")
    rec.append("")
    rec.append("| 项 | 值 |")
    rec.append("|---|---|")
    rec.append("| 冻结时间 | %s |" % stamp)
    rec.append("| 项目目录 | `%s` |" % root)
    rec.append("| 风格 | **%s** |" % name)
    rec.append("| 基线 tag | `%s` |" % tag)
    rec.append("| commit | `%s` |" % (commit or "（无 git）"))
    rec.append("| git 基线 | %s |" % ("已打" if git_ok else "未打（无 git 或无变更）"))
    rec.append("| 文件数 | %d |" % len(files))
    rec.append("")
    rec.append("## 冻结文件清单")
    rec.append("")
    rec.append("| 文件 | 大小 | SHA256 |")
    rec.append("|---|---|---|")
    for rel, size, h in files:
        rec.append("| `%s` | %d B | `%s` |" % (rel, size, h[:16] + "…"))
    rec.append("")
    rec.append("## 冻结之后的规矩")
    rec.append("")
    rec.append("| 能做 | 不能做 |")
    rec.append("|---|---|")
    rec.append("| 改文案、改局部样式（B 线） | 改风格本身（颜色/圆角/阴影体系） |")
    rec.append("| 按说明书继续开发 | 改页面结构、图标体系、字体 |")
    rec.append("| 修 bug | 改共享 UI 组件、断点、数据模型 |")
    rec.append("")
    rec.append("要改左侧「不能做」的项 → 走**变更单**，重新走 S2–S4。")
    rec.append("")

    rec_path = os.path.join(root, RECORD)
    with open(rec_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(rec))
    print("[完成] 冻结记录：%s（%d 个文件入册）" % (RECORD, len(files)))

    # 记录本身也进 git（若可用）
    if git_ok:
        git(root, "add", RECORD)
        git(root, "commit", "-m", "S4 冻结记录")
        git(root, "tag", "-a", tag, "-m", "S4 冻结基线（含记录）", "-f")

    print("")
    print("S4 冻结完成。后续允许：改文案/局部样式/修 bug。")
    print("后续禁止：改风格体系/页面结构/共享组件 → 需变更单。")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)

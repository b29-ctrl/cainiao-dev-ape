# -*- coding: utf-8 -*-
"""
问卷转说明书：把问卷引擎的 MODEL 转成说明书的 §3「板块与功能」章节骨架。

这会消掉"靠人抄"里**机械的那部分**（分组 / 去前缀 / 板块标题 / 状态统计），
只剩「入口 / 结果 / 失败提示」三列需要人补——那是设计判断，不是搬运。

用法：
    python 问卷转说明书.py --q "S0.1_问卷.html" [--out "§3_板块与功能.md"] [--with-pending]

退出码：0 成功 ｜ 1 问卷里解析不到 MODEL

零依赖，跨平台。
"""
import argparse
import io
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def read_text(p):
    with io.open(p, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def parse_model(html):
    """从问卷引擎 HTML 里抽 blocks / funcs。"""
    m = re.search(r"var MODEL = \{(.*?)\n\};", html, re.S)
    if not m:
        return None, None, None
    body = m.group(1)

    blocks = []
    for mm in re.finditer(
        r"\{\s*id:\s*'([A-Z0-9_]+)',\s*name:\s*'([^']*)',\s*note:\s*'([^']*)'\s*\}", body):
        blocks.append({"id": mm.group(1), "name": mm.group(2), "note": mm.group(3)})

    funcs = []
    for mm in re.finditer(
        r"\{\s*id:\s*'([A-Z][A-Z0-9-]+)',\s*block:\s*'([A-Z0-9_]+)',\s*name:\s*'([^']*)',"
        r"\s*source:\s*'([^']*)',\s*status:\s*'([^']*)'\s*\}", body):
        funcs.append({
            "id": mm.group(1), "block": mm.group(2), "name": mm.group(3),
            "source": mm.group(4), "status": mm.group(5),
        })

    prod = re.search(r"product:\s*'([^']*)'", body)
    cat = re.search(r"category:\s*'([^']*)'", body)
    meta = {"product": prod.group(1) if prod else "", "category": cat.group(1) if cat else ""}
    return blocks, funcs, meta


def short_id(fid):
    """B-YKT-CARD-01 → CARD-01"""
    parts = fid.split("-")
    return parts[-2] + "-" + parts[-1] if len(parts) >= 2 else fid


def build(blocks, funcs, meta, with_pending=False):
    out = []
    out.append("## 3. 板块与功能")
    out.append("")
    out.append("> 由 `工具/问卷转说明书.py` 从问卷答案**自动生成**。")
    out.append("> 机械部分（分组 / 短编号 / 板块标题 / 状态统计）已自动完成；")
    out.append("> **「入口 / 结果 / 失败提示」三列必须人补**——那是设计判断，不是搬运。")
    out.append("")

    # 按板块分组，保持 MODEL 顺序
    idx = 0
    stat = {"必做": 0, "待确认": 0, "二期": 0, "不做": 0}
    for b in blocks:
        mine = [f for f in funcs if f["block"] == b["id"]]
        for f in mine:
            stat[f["status"]] = stat.get(f["status"], 0) + 1
        keep = [f for f in mine if f["status"] == "必做"]
        pend = [f for f in mine if f["status"] == "待确认"]
        if with_pending:
            keep = keep + pend
        if not keep:
            continue
        idx += 1
        prefix = ""
        if keep:
            p = keep[0]["id"].split("-")
            if len(p) >= 2:
                prefix = "-".join(p[:-1]) + "-"
        out.append("### 3.%d %s（%s*）" % (idx, b["name"], prefix))
        out.append("")
        if b.get("note"):
            out.append("> %s" % b["note"])
            out.append("")
        out.append("| 编号 | 功能 | 入口 | 结果 | 失败提示 |")
        out.append("|---|---|---|---|---|")
        for f in keep:
            mark = "" if f["status"] == "必做" else "（待确认）"
            out.append("| %s | %s%s | ____ | ____ | ____ |" % (short_id(f["id"]), f["name"], mark))
        out.append("")

    # 待确认 / 不做 清单
    pend = [f for f in funcs if f["status"] == "待确认"]
    no = [f for f in funcs if f["status"] == "不做"]
    two = [f for f in funcs if f["status"] == "二期"]
    if pend:
        out.append("### 待确认项（不进 v1.0）")
        out.append("")
        out.append("| 编号 | 功能 | 处理 |")
        out.append("|---|---|---|")
        for f in pend:
            out.append("| %s | %s | 主理人拍板后决定进/不进 |" % (short_id(f["id"]), f["name"]))
        out.append("")
    if two:
        out.append("### 二期项")
        out.append("")
        for f in two:
            out.append("- %s %s" % (short_id(f["id"]), f["name"]))
        out.append("")
    if no:
        out.append("### 明确不做")
        out.append("")
        for f in no:
            out.append("- %s %s" % (short_id(f["id"]), f["name"]))
        out.append("")

    out.append("### 统计")
    out.append("")
    out.append("| 状态 | 数量 |")
    out.append("|---|---|")
    for k in ("必做", "待确认", "二期", "不做"):
        if stat.get(k):
            out.append("| %s | %d |" % (k, stat[k]))
    out.append("| **合计** | **%d** |" % len(funcs))
    out.append("")
    return out, stat


def main():
    ap = argparse.ArgumentParser(description="问卷 MODEL → 说明书 §3 骨架")
    ap.add_argument("--q", required=True, help="问卷 HTML（问卷引擎生成的那份）")
    ap.add_argument("--out", default="", help="输出文件（默认与问卷同目录）")
    ap.add_argument("--with-pending", action="store_true", help="待确认项也列进表格（默认不列）")
    a = ap.parse_args()

    if not os.path.exists(a.q):
        print("[失败] 问卷不存在：" + a.q)
        return 1
    html = read_text(a.q)
    blocks, funcs, meta = parse_model(html)
    if not blocks or not funcs:
        print("[失败] 没能从问卷里解析出 MODEL.blocks / MODEL.funcs")
        print("       确认这是「问卷引擎」生成的 HTML（里面有 var MODEL = {...}）")
        return 1

    lines, stat = build(blocks, funcs, meta, a.with_pending)
    out_path = a.out or os.path.join(os.path.dirname(os.path.abspath(a.q)), "§3_板块与功能.md")
    io.open(out_path, "w", encoding="utf-8", newline="\n").write("\n".join(lines))

    print("[完成] 产品：%s（品类 %s）" % (meta.get("product", "?"), meta.get("category", "?")))
    print("[完成] 板块 %d 个 ｜ 功能 %d 个" % (len(blocks), len(funcs)))
    need = stat.get("必做", 0) * 3
    print("[完成] 自动生成：分组 + 短编号 + 板块标题 + 统计")
    print("[待补] 入口/结果/失败提示：%d 个功能 × 3 列 = %d 格需要人填" % (stat.get("必做", 0), need))
    print("[完成] 输出：%s" % out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())

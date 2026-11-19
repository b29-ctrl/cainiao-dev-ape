# -*- coding: utf-8 -*-
"""
门禁证据矩阵生成器：从说明书 §9 验收清单自动抽 V 项，生成可填的证据矩阵。

用法：
    python 门禁矩阵.py --doc <说明书.md> [--task <任务书.md>] [--out 门禁证据矩阵.md]

做什么：
    1. 从说明书的验收章节抽出所有 V-* / N* 行 → 生成证据矩阵（状态列留空待填）
    2. 若给了 --task：从任务书抽出功能 ID，与验收项比对，报「漏交付」
    3. 统计正向/负向项数，并把「未覆盖 / 阻断」写成必须声明的规则

退出码：
    0 生成成功且无漏交付 ｜ 1 找不到验收项 ｜ 2 有漏交付（矩阵仍会生成）

零依赖，跨平台。
"""
import argparse
import os
import re
import sys

OUT_DEFAULT = "门禁证据矩阵.md"

# 验收项编号：V-XXX-YY-01 / V1 / N1 / N-1
RE_VERIFY = re.compile(r"^\s*(V[-_]?[A-Za-z0-9_-]*\d+|N[-_]?\d+)\s*$")
# 任务书里的功能 ID：B-XXX-YY-01（允许 3–5 段，如 B-YKT-CARD-01 / B-YKT-XX-NEW-99）
RE_FID = re.compile(r"\b([A-Z]-[A-Z0-9]{2,6}(?:-[A-Z0-9]{2,6}){1,3}-\d{2})\b")


def read_text(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def split_tables(text):
    """把 markdown 表格拆成 [ (表头cells, [行cells...]) ]。"""
    tables = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            header = [c.strip() for c in lines[i].strip().strip("|").split("|")]
            rows = []
            j = i + 2
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                cells = [c.strip() for c in lines[j].strip().strip("|").split("|")]
                rows.append(cells)
                j += 1
            tables.append((header, rows))
            i = j
        else:
            i += 1
    return tables


def extract_verify(text):
    """从所有表格里找验收项。返回 [(编号, 动作/输入, 期望, 所在列说明)]。"""
    found = []
    seen = set()
    for header, rows in split_tables(text):
        # 找"编号"列
        idx_id = None
        for k, h in enumerate(header):
            if h in ("编号", "验收编号", "ID", "项") or "编号" in h:
                idx_id = k
                break
        # 若表头没有编号列，就按每行第一格猜
        for cells in rows:
            if not cells:
                continue
            cid = cells[idx_id] if idx_id is not None and idx_id < len(cells) else cells[0]
            cid = cid.strip().strip("`").strip()
            if not RE_VERIFY.match(cid):
                continue
            if cid in seen:
                continue
            seen.add(cid)
            rest = [c for k, c in enumerate(cells) if k != (idx_id if idx_id is not None else 0)]
            action = rest[0] if len(rest) > 0 else ""
            expect = rest[1] if len(rest) > 1 else ""
            found.append((cid, action, expect))
    return found


def extract_task_fids(text):
    """从任务书里抽功能 ID（B-YKT-CARD-01）与"本次做"的描述。

    会跳过格式示例（B-XXX-YY-01 / B-ABC-DE-99 之类），否则会误报漏交付。
    """
    fids = []
    seen = set()
    for m in RE_FID.finditer(text):
        f = m.group(1)
        # 占位符/格式示例不算真功能
        if re.search(r"(X{2,}|Y{2,}|x{2,}|y{2,})", f):
            continue
        norm = re.sub(r"\d+$", "", f).upper()
        if norm in ("B-ABC-DE-", "B-XXX-YY-"):
            continue
        if f not in seen:
            seen.add(f)
            fids.append(f)
    return fids


def normalize_cid(cid):
    """V-B-YKT-CARD-01 → 关键尾部，用于和功能 ID 对账。"""
    s = cid.strip("`").strip()
    s = re.sub(r"^V[-_]?", "", s, flags=re.I)
    return s


def build_matrix(verify_items, doc_name):
    out = []
    out.append("# 门禁证据矩阵")
    out.append("")
    out.append("> 由 `工具/门禁矩阵.py` 从 `%s` 的验收清单自动生成。" % doc_name)
    out.append("> 逐行填「实际结果 / 证据」；**没做的必须写「未覆盖」并给原因，不得留空、不得算通过**。")
    out.append("")
    out.append("**状态只能是三种**：`通过` / `未覆盖（原因）` / `阻断`")
    out.append("")
    out.append("| 编号 | 测试输入 / 操作 | 期望结果 | 状态 | 实际结果 | 证据（路径 + hash） |")
    out.append("|---|---|---|---|---|---|")
    for cid, action, expect in verify_items:
        out.append("| `%s` | %s | %s |  |  |  |" % (cid, action or "—", expect or "—"))
    out.append("")
    return out


def main():
    ap = argparse.ArgumentParser(description="从说明书验收清单生成门禁证据矩阵")
    ap.add_argument("--doc", required=True, help="产品功能说明书 .md")
    ap.add_argument("--task", default="", help="任务书 .md（可选，用于查漏交付）")
    ap.add_argument("--out", default="", help="输出文件（默认与说明书同目录的 %s）" % OUT_DEFAULT)
    a = ap.parse_args()

    if not os.path.exists(a.doc):
        print("[失败] 说明书不存在：" + a.doc)
        return 1
    text = read_text(a.doc)
    items = extract_verify(text)
    if not items:
        print("[失败] 没从说明书里找到验收项（编号需形如 V1 / V-XXX-01 / N1）")
        print("       检查说明书的「验收清单」章节是不是标准 markdown 表格。")
        return 1

    v_items = [x for x in items if x[0].upper().startswith("V")]
    n_items = [x for x in items if x[0].upper().startswith("N")]

    lines = build_matrix(items, os.path.basename(a.doc))

    # ---- 漏交付检测 ----
    missing = []
    if a.task and os.path.exists(a.task):
        ttext = read_text(a.task)
        fids = extract_task_fids(ttext)
        covered = set()
        for cid, _, _ in items:
            covered.add(normalize_cid(cid).upper())
        for f in fids:
            if f.upper() not in covered:
                missing.append(f)

    lines.append("## 验收纪律（流程 §4.1.1）")
    lines.append("")
    lines.append("1. **范围一致**：任务书要求的每一项，验收都要覆盖；漏了就是漏交付，不得通过。")
    lines.append("2. **结论不越界**：单测/自测通过 ≠ 页面功能可跑，三者结论分开写。")
    lines.append("3. **原型不虚假承诺**：没实现的能力不得写进 UI 文案或验收。")
    lines.append("")
    lines.append("| 覆盖情况 | 数量 |")
    lines.append("|---|---|")
    lines.append("| 正向项 V* | %d |" % len(v_items))
    lines.append("| 负向项 N* | %d |" % len(n_items))
    lines.append("| 合计 | %d |" % len(items))
    if a.task and os.path.exists(a.task):
        lines.append("| 任务书功能 ID | %d |" % len(extract_task_fids(read_text(a.task))))
        lines.append("| **疑似漏交付** | **%d** |" % len(missing))
    lines.append("")

    if missing:
        lines.append("## ⚠️ 疑似漏交付")
        lines.append("")
        lines.append("任务书里提到、但说明书验收清单没有对应项的：")
        lines.append("")
        for f in missing:
            lines.append("- `%s`" % f)
        lines.append("")
        lines.append("处置：要么补验收项，要么在任务书里说明「本批不做」。**不许默默跳过。**")
        lines.append("")

    out_path = a.out or os.path.join(os.path.dirname(os.path.abspath(a.doc)), OUT_DEFAULT)
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines))

    print("[完成] 验收项：正向 %d + 负向 %d = %d" % (len(v_items), len(n_items), len(items)))
    print("[完成] 矩阵：%s" % out_path)
    if a.task and os.path.exists(a.task):
        if missing:
            print("[警告] 疑似漏交付 %d 项：%s" % (len(missing), ", ".join(missing)))
            return 2
        print("[通过] 任务书功能 ID 与验收项无漏交付")
    return 0


if __name__ == "__main__":
    sys.exit(main())

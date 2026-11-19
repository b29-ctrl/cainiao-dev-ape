# -*- coding: utf-8 -*-
"""
任务书生成器：从说明书的板块与功能，生成任务书骨架（依赖图 / 里程碑 / 小任务 / 并行度复核）。

用法：
    python 任务书生成.py --doc <说明书.md> [--batch 1] [--out S1.1_任务书.md] [--scope "卡务,账户"]

做什么：
    1. 从说明书抽出「板块 → 功能 ID」清单
    2. 生成依赖图（阶段0 骨架 → 阶段1 可并行 → 阶段2 依赖块）
    3. 生成里程碑 M0/M1… 与小任务 T1/T2…（一个可验证变化一个）
    4. 并行度复核：**同时给「项目配置容量」和「本批活动并行度」两个口径**
    5. 输出任务书骨架（预览环境 / 回滚点 / 排期 / 已知风险）

退出码：0 成功 ｜ 1 找不到板块或功能

零依赖，跨平台。
"""
import argparse
import os
import re
import sys

OUT_DEFAULT = "S1.1_任务书.md"

# ### 3.1 卡务管理（B-YKT-CARD-*）
RE_SECTION = re.compile(r"^(#{2,4})\s*§?\s*([0-9]+(?:\.[0-9]+)+)\s+(.+?)\s*$")
# 完整功能 ID：B-YKT-CARD-01
RE_FID = re.compile(r"\b([A-Z]-[A-Z0-9]{2,6}(?:-[A-Z0-9]{2,6}){1,3}-\d{2})\b")
# 板块表格里的短 ID：| CARD-01 |（前面会补上板块前缀）
RE_SHORT = re.compile(r"\b([A-Z][A-Z0-9]{1,8})-(\d{2})\b")
# 从标题括号里取板块前缀：B-YKT-CARD-*
RE_PREFIX = re.compile(r"[（(]\s*([A-Z]-[A-Z0-9-]*?)\*\s*[）)]")
# 依赖块：名字里带这些词的板块排到阶段2
LATE_HINT = ("报表", "对账", "统计", "汇总", "审计", "日志")
# 横切块
CROSS_HINT = ("系统", "权限", "设置", "对接", "配置")


def read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def extract_blocks(text):
    """返回 [(编号, 板块名, [功能ID...])]。支持完整 ID 与表格里的短 ID。"""
    lines = text.splitlines()
    blocks = []
    cur = None
    in_sec3 = False
    for line in lines:
        s = line.strip()
        # 顶级/二级标题边界：进入 ## 3. 开区，离开则清空
        if re.match(r"^##\s", s) and not s.startswith("### "):
            if cur:
                blocks.append(cur)
                cur = None
            in_sec3 = bool(re.match(r"^##\s*3[\.、\s]", s) or re.match(r"^##\s*3\s", s))
            continue
        m = RE_SECTION.match(s)
        if m and m.group(2).startswith("3"):
            if cur:
                blocks.append(cur)
            name = m.group(3).strip()
            pm = RE_PREFIX.search(name)
            prefix = (pm.group(1) if pm else "")
            cur = [m.group(2), name, [], prefix]
            continue
        # 兼容：在 §3 区域内，任何 ### 标题都当作板块（老模板写 ### 板块 X）
        if re.match(r"^###\s+", s) and in_sec3:   # 只认三级标题，四级（#### 功能点明细）属子标题
            if cur:
                blocks.append(cur)
            name = re.sub(r"^#{3,4}\s+", "", s).strip()
            pm = RE_PREFIX.search(name)
            prefix = (pm.group(1) if pm else "")
            cur = ["", name, [], prefix]
            continue
        if cur:
            # 先抓完整 ID（B-YKT-CARD-01）
            for f in RE_FID.finditer(s):
                fid = f.group(1)
                if fid not in cur[2]:
                    cur[2].append(fid)
            # 再抓表格里的短 ID（CARD-01），用板块前缀补全
            if cur[3]:
                family = cur[3].rstrip("-").split("-")[-1]      # B-YKT-CARD- → CARD
                for f in RE_SHORT.finditer(s):
                    if f.group(1) == family:
                        fid = cur[3] + f.group(2)                # B-YKT-CARD- + 01
                        if fid not in cur[2]:
                            cur[2].append(fid)
    if cur:
        blocks.append(cur)
    return [b[:3] for b in blocks if b[2]]


def classify(name):
    if any(h in name for h in LATE_HINT):
        return "late"
    if any(h in name for h in CROSS_HINT):
        return "cross"
    return "parallel"


def build(doc_name, blocks, batch, scope_names):
    if scope_names:
        picked = [b for b in blocks if any(s in b[1] for s in scope_names)]
    else:
        picked = blocks
    phase0 = picked[:1]
    rest = picked[1:]
    late = [b for b in rest if classify(b[1]) == "late"]
    cross = [b for b in rest if classify(b[1]) == "cross"]
    para = [b for b in rest if classify(b[1]) == "parallel"]

    N = len(para) or 1
    I = 1 if N > 1 else 0
    B, C = 1, 1
    V = 1
    total = N + I + B + C + V
    active_cap = 2  # 同时活动写码分支上限

    out = []
    out.append("# S1.1 任务书 · 第 %d 批" % batch)
    out.append("")
    out.append("> 由 `工具/任务书生成.py` 从 `%s` 生成**骨架**，AI-C 必须复核后再派工。" % doc_name)
    out.append(">")
    out.append("> ⚠️ 功能数是按说明书中**可识别的 ID**（`B-XXX-YY-01` 或表里的 `YY-01`）统计的；")
    out.append("> 说明书里简写的（如「02 余额 / 03 流水」）会漏计，复核时补齐。")
    out.append("")
    out.append("## 一、本次范围（引用说明书章节，不复制功能清单）")
    out.append("")
    out.append("| 项 | 内容 |")
    out.append("|---|---|")
    out.append("| 依据章节 | 说明书 §3：" + "、".join(b[1] for b in picked) + " |")
    out.append("| 功能数 | %d |" % sum(len(b[2]) for b in picked))
    out.append("| 本次形态 | ____（单文件 HTML / 前后端 / 其他） |")
    out.append("| 本次不做 | ____（写清哪些板块留到下一批） |")
    out.append("")

    out.append("## 二、预览环境")
    out.append("")
    out.append("| 项 | 内容 |")
    out.append("|---|---|")
    out.append("| 服务 owner | ____ |")
    out.append("| 固定入口 | `http://127.0.0.1:____/` |")
    out.append("| 截图命令 | `python shot.py <url> 1440 900 <out>` |")
    out.append("| 临时文件 | `_preview_*.png`，结项清理 |")
    out.append("| 故障降级 | 端口占用换端口；入口不可用则本阶段不进入 S2 |")
    out.append("")

    out.append("## 三、任务拆分结果（开发计划）")
    out.append("")
    out.append("### 3.1 依赖图")
    out.append("")
    out.append("```")
    out.append("阶段0（骨架，共享契约）")
    for b in phase0:
        out.append("  %s：%d 个功能（%s）" % (b[1], len(b[2]), ", ".join(b[2][:2]) + ("…" if len(b[2]) > 2 else "")))
    out.append("        ↓")
    out.append("阶段1（可并行切片）")
    for b in para:
        out.append("  %s（%d 个功能）" % (b[1], len(b[2])))
    if cross:
        out.append("阶段1.5（横切，尽早开工）")
        for b in cross:
            out.append("  %s（%d 个功能）" % (b[1], len(b[2])))
    out.append("        ↓")
    out.append("阶段2（依赖块）")
    for b in late:
        out.append("  %s（%d 个功能）" % (b[1], len(b[2])))
    out.append("```")
    out.append("")

    out.append("### 3.2 里程碑")
    out.append("")
    out.append("| 里程碑 | 内容 | 可见成果 |")
    out.append("|---|---|---|")
    out.append("| M0 | 骨架可跑 | 页面能开、导航能切、令牌生效 |")
    for i, b in enumerate(para + cross, 1):
        out.append("| M%d | %s 可跑 | %d 个功能可操作 |" % (i, b[1], len(b[2])))
    if late:
        out.append("| M%d | 汇总/对账可跑 | 数字对得上 |" % (len(para + cross) + 1))
    out.append("")

    out.append("### 3.3 小任务（一个可验证变化 = 一个任务）")
    out.append("")
    out.append("| # | 小任务 | 粒度 | owner |")
    out.append("|---|---|---|---|")
    idx = 1
    out.append("| T%d | 骨架：顶栏/侧栏/令牌/假数据 | 一个可验证变化 | AI-A |" % idx); idx += 1
    for b in para + cross:
        for f in b[2]:
            out.append("| T%d | %s · %s | 用户可见 | AI-A |" % (idx, b[1], f))
            idx += 1
    out.append("")

    out.append("## 四、并行度复核（§7.4.1）—— 两个口径都写")
    out.append("")
    out.append("| 口径 | 值 | 用途 |")
    out.append("|---|---|---|")
    out.append("| **项目配置容量** | N=%d + I=%d + B=%d + C=%d + V=%d = **%d** | 整个项目最多要多少人 |" % (N, I, B, C, V, total))
    out.append("| **本批活动并行度** | 本批 %d 个可并行板块，受安全线约束 **≤%d** | 这个任务书实际派几个 |" % (N, active_cap))
    out.append("")
    out.append("> **两个数字不一样是对的**：容量是上限（立项排人用），本批是实派（任务书用）。")
    out.append("> 写任务书只用「本批活动并行度」，别把容量当成本批人数。")
    out.append("")
    out.append("| 硬规矩 | 说明 |")
    out.append("|---|---|")
    out.append("| 同时活动写码分支 ≤ %d | 超了先合并，再派新任务 |" % active_cap)
    out.append("| N>1 必须有集成 owner | 否则代码汇不到一起 |")
    out.append("| 门③ 签在集成分支 | 不按开发分支重复签 |")
    out.append("")

    out.append("## 五、交付物")
    out.append("")
    out.append("| # | 交付 | 判据 |")
    out.append("|---|---|---|")
    out.append("| 1 | 页面/代码 | 打开能用，功能可操作 |")
    out.append("| 2 | 截图 ____ 张 | 列表态 / 关键操作态 |")
    out.append("| 3 | 自测记录 | 正向 + 负向，命令与退出码入档 |")
    out.append("")

    out.append("## 六、验收标准")
    out.append("")
    out.append("> 用 `工具/门禁矩阵.py --doc <说明书> --task <本任务书>` 自动生成证据矩阵，**别手写**。")
    out.append("")
    out.append("| 项 | 判据 |")
    out.append("|---|---|")
    out.append("| 正向 | 说明书 §9 的全部 V 项逐条通过 |")
    out.append("| 负向 | 至少 3 项：空态 / 越权 / 边界 |")
    out.append("| 漏交付 | `门禁矩阵.py` 退出码必须为 0 |")
    out.append("")

    out.append("## 七、回滚点")
    out.append("")
    out.append("| 项 | 值 |")
    out.append("|---|---|")
    out.append("| 前一个基线 | `____`（S4 冻结 tag） |")
    out.append("| 本批失败处置 | `git revert` 到前基线，**不要用 `reset --hard`**（会毁掉别人的和未提交的） |")
    out.append("")

    out.append("## 八、已知风险")
    out.append("")
    out.append("| # | 风险 | 处置 |")
    out.append("|---|---|---|")
    out.append("| 1 | ____（从说明书的「已知风险与待确认」抄过来） | ____ |")
    out.append("")
    return out, dict(N=N, I=I, B=B, C=C, V=V, total=total, blocks=len(picked))


def main():
    ap = argparse.ArgumentParser(description="从说明书生成任务书骨架")
    ap.add_argument("--doc", required=True, help="产品功能说明书 .md")
    ap.add_argument("--batch", type=int, default=1, help="第几批（默认 1）")
    ap.add_argument("--scope", default="", help="本批只做哪些板块（逗号分隔，模糊匹配）")
    ap.add_argument("--out", default="", help="输出文件")
    a = ap.parse_args()

    if not os.path.exists(a.doc):
        print("[失败] 说明书不存在：" + a.doc)
        return 1
    text = read(a.doc)
    blocks = extract_blocks(text)
    if not blocks:
        print("[失败] 没从说明书抽出「板块 → 功能」结构")
        print("       两种标题都认：### 3.1 板块名（B-XXX-YY-*） 或 ### 板块名")
        return 1

    scope = [s.strip() for s in a.scope.split(",") if s.strip()]
    lines, stats = build(os.path.basename(a.doc), blocks, a.batch, scope)

    out_path = a.out or os.path.join(os.path.dirname(os.path.abspath(a.doc)), OUT_DEFAULT)
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines))

    print("[完成] 板块 %d 个 → 本批 %d 个" % (len(blocks), stats["blocks"]))
    print("[完成] 并行度：项目容量 %d ｜ 本批受安全线 ≤2" % stats["total"])
    print("[完成] 任务书骨架：%s" % out_path)
    print("[提示] 这是骨架，AI-C 必须补：本次不做、预览环境、已知风险、回滚点基线")
    return 0


if __name__ == "__main__":
    sys.exit(main())

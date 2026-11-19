# 组件状态清单（菜鸟开发猿 v4.64 · `03_模板/UI交付/`）

> 交付时每个组件都要能回答："它的各个状态长什么样？"答不上，说明只做了 happy path。
> 用法：S3 看图批注时对着这张表逐项打勾；没做过的状态，要么补，要么在回报里写明"本版不做"。

## 1. 列表项（最高频、最易漏，共 8 态）

| 状态 | 触发 | 视觉要求 |
|---|---|---|
| default | 静止 | 常规底色，无描边 |
| hover | 鼠标移入 | 底色浅一档，形状不变（不要加阴影导致抖动） |
| selected / active | 被选中 | 底色 + 左侧 3px 品牌色条，或 inset 描边；**不要**只靠文字变色 |
| pressed | mousedown | 比 hover 再深一档，缩放不超过 0.99 |
| disabled | 不可操作 | 整体降透明到 0.45，指针 `not-allowed`，hover 不响应 |
| unread | 有新内容 | 左侧圆点或加粗标题，**不能**只靠角标数字 |
| expanded | 展开态 | 箭头旋转 180°（同一元素同一缓动），内容不被裁切 |
| swipe / actions | 悬停或滑动出现 | 操作区从右侧推入，不与标题重叠 |

补充约束：
- 行高一致：单项高度由最小内容决定；长标题走 2 行截断（`-webkit-line-clamp:2`），不要每行高度不同。
- 编号类字段（工单号、ID）固定宽度（如 112px）+ `tabular-nums`，避免列表左右跳动。
- 列表容器用 `overflow:auto` + 内部滚动，**不要**让整页跟着滚。

## 2. 按钮（6 态）

| 状态 | 要求 |
|---|---|
| default | 主按钮实底品牌色 + 深墨字；次按钮白底 + 描边 |
| hover | 亮度 ±6%，不加位移动画 |
| active | 底色再深一档 |
| focus-visible | 2px 聚焦环（`--shadow-focus`），必须可见 |
| disabled | 降透明 + `cursor:not-allowed`，且**真的不可点**（`disabled` 属性） |
| loading | 文案换成"处理中…"，宽度不变，防布局跳动 |

同一屏内主按钮最多一个；危险操作（驳回、删除）用 `--danger` 描边或浅底，不要和主按钮同权重。

## 3. 状态 chip

```css
.cp{ /* 基础态写在全局类上 */
  display:inline-flex;align-items:center;gap:4px;
  padding:2px 10px;border-radius:999px;
  font-size:12px;font-weight:600;white-space:nowrap;
}
.cp.is-warn{ background:var(--warning-soft); color:var(--amber-deep); }   /* 待处理/待验 */
.cp.is-done{ background:var(--success-soft); color:var(--green-deep); }   /* 已完成 */
.cp.is-fail{ background:var(--danger-soft);  color:var(--red-deep); }    /* 失败/退回 */
```

**状态类名以 `theme.template.css` 为准**：`.is-warn` / `.is-done` / `.is-fail`（v4.64 更正）。

| 状态 | 唯一写法 | 用在 |
|---|---|---|
| 进行中 / 待处理 / 待验 | `.cp.is-warn` | 中性提醒色（桃黄） |
| 已完成 / 已通过 | `.cp.is-done` | 成功色（青绿） |
| 失败 / 退回 / 拦截 | `.cp.is-fail` | 危险色（珊瑚） |

> 早期稿里写过的 `.cp-p` / `.cp-x` / `.cp-f` 是同一套东西的缩写（p=pending、x=done、f=fail），**已废弃**，照抄会和模板对不上、状态色全部失效、只剩药丸形状。看到旧写法一律改成上表。

**关键**：基础态必须在 `.cp` 本身。写成 `.tlist .ti .cp` 会导致详情面板/弹窗里的 chip 没有药丸形状——这是最常见的返工原因。

## 4. 输入框 / 文本域（7 态）

default → hover（描边加深）→ focus（描边品牌色 + 聚焦环）→ filled（有值）→ error（描边 danger + 下方错误文案）→ disabled → readonly。
字符计数在右下角，超过 90% 变 warning 色，达到上限变 danger 色并阻止继续输入。

## 5. 弹窗

必须有：遮罩（点击关闭）、标题、内容区独立滚动（`max-height` + `overflow:auto`）、底部操作区固定、`Esc` 关闭、焦点回到触发元素。
宽度：常规 520–580px；宽表用 `wide` 变体但不超过 880px。**不要**让详情类内容占满整屏——需要满屏说明信息层级没收敛。

## 6. 空态 / 错误态 / 加载态

| 态 | 文案结构 | 不能做的事 |
|---|---|---|
| 空 | 一句标题 + 一句怎么开始 + 一个主操作 | 不要放插画占位图后什么都不说 |
| 错误 | 出了什么问题 + 影响范围 + 重试入口 | 不要只写"加载失败" |
| 加载 | 骨架屏优先于转圈 | 不要让容器高度塌陷导致页面跳动 |

## 7. 交付前逐项打勾

- [ ] 列表 8 态齐（含 selected、unread、expanded）
- [ ] 按钮 6 态齐（含 focus-visible、disabled 真禁用）
- [ ] chip 基础态在全局类
- [ ] 输入框 7 态齐
- [ ] 弹窗可 Esc / 点遮罩关闭，内容区独立滚动
- [ ] 空/错/载三态各有文案与出口
- [ ] 1440、1280、980 各过一遍

把这张表填完的结果直接贴进四行头的「证据」行，比写"界面已完善"有用得多。

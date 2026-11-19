# 验收手册（菜鸟开发猿 v4.64 · `03_模板/UI交付/`）

> 交付前的三次检查：**机器查 → 交互查 → 截图查**。任何一项没跑，都不算完成。
> 命令示例以 Windows + Edge 为准；macOS/Linux 用 Chrome 等价参数，或退回"调试台人工核对 + 勾清单"。

## 一查：机器可查项

**命令只有一份，在 `06_UI交付与验收.md` 的「四、验收三查 · 一查」。本文件不再抄一遍。**
（v4.63 就是两边各抄一套、口径写歪了：playbook 那套不挖 `:root`，照跑会把合法的 token 定义报成违规。一个规则只留一处，改也只改一处。）

跑之前只要确认这 5 条口径：

1. `$files` 改成你真实的文件名；**单文件页面**就写 `@("index.html")`，别去凑 `app.css/app.js/theme.css` 三件套。
2. `:root` 块里定义 token 是**合法**的，脚本会先把它挖掉；以 `--x:` 开头的 token 定义行也放过（暗色主题块同理）。
3. 输出必须是 **`文件:行号` + 那一行原文**，只给个数字不行——数字只能证明有问题，不能告诉你改哪。
4. 计数口径是 `根部以外颜色值=0`：同时查 `#hex`、`rgb()/rgba()/hsl()/hsla()`、CSS 颜色名。**它查不到 JS 里写的颜色和行内 style**，那些靠二查。
5. 未定义 `var()` 跨文件合并后算差集，期望 0。

补充人工检查（这四条脚本查不了）：
- [ ] `index.html` 只有一个 `<style>` 块（或没有），样式全在外链文件
- [ ] 无 CDN / 字体 / 图片 / 接口请求（离线双击打开无 404）
- [ ] HTML 标签闭合（交给编辑器格式化验证）
- [ ] 页面上没有行内 `style="color:#..."`、没有 JS 里直接写颜色

**没有 Node 时**：跳过语法检查那一条；其余两条纯 PowerShell，照跑。

## 二查：交互真点一遍

**不要**只截静态图。用临时页驱动真实 DOM：

```html
<!-- 只放骨架：把下面 4 个选择器换成你自己页面里真实存在的（完整写法与映射表见 06 文档「二查」） -->
<script>
setTimeout(function () {
  var R = [];
  var SEL = { row: '你的列表行', modal: '你的弹窗', ok: '你的主按钮', gate: '你的勾选项' };
  var M = document.querySelector(SEL.modal);
  document.querySelector(SEL.row).click();
  R.push('popup=' + M.classList.contains('open'));
  document.querySelectorAll(SEL.gate).forEach(function (b) { b.checked = true; b.dispatchEvent(new Event('change', { bubbles: true })); });
  document.querySelector(SEL.ok).click();
  R.push('closed=' + !M.classList.contains('open'));
  document.body.setAttribute('data-check', R.join(' | '));
}, 600);
</script>
```

```powershell
$edge = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"   # 或 chrome.exe
$d = & $edge --headless --disable-gpu --no-sandbox `
     --user-data-dir="$env:TEMP\edge-t" --virtual-time-budget=4000 `
     --dump-dom "file:///.../_t.html" | Out-String
if ($d -match 'data-check="([^"]+)"') { $matches[1] }
```

要点：
- `--user-data-dir` 必须有独立值，否则会被已打开的浏览器单例接管（表现为窗口尺寸不对、脚本不执行）。
- `--virtual-time-budget` 要大于所有 `setTimeout` 之和。
- 断言写布尔或短字符串，结果拼一行便于贴进回报。
- **测完删除临时页**，不要混进交付目录。

**没有浏览器命令行时**：用 `<skill-pack-root>/02_工具/UI调试台.py`（技能包根下 `02_工具/`）打开效果图，手点主路径（开弹窗 → 勾门槛 → 提交 → 关闭），把结果写成"`popup=true | gate=true | closed=true`"，一样算通过——三查要的是"真的动过"。

## 三查：截图核对

```powershell
& $edge --headless --disable-gpu --no-sandbox --user-data-dir="$env:TEMP\edge-shot" `
  --hide-scrollbars --window-size=1440,900 --screenshot="1440_chat.png" `
  "file:///.../index.html#/chat"

# 长页面：高度给足，一次截完
& $edge ... --window-size=1440,2200 --screenshot="1440_members_full.png" "..."
```

清单：

| 图 | 尺寸 | 看什么 |
|---|---|---|
| 每个主视图 | 1440×900 | 信息层级、留白、对齐 |
| 首页 | 1280×800 | 顶栏是否换行、右栏是否挤压、有无横向滚动 |
| 长页面 | 1440×2200 | 下方区块是否真的渲染了 |
| 弹窗 | 1440×900 | 是否居中、遮罩是否覆盖、按钮是否在视口内 |
| 极窄 | 980×800 | 是否按设计降级为单列 |

截图必须**自己看过再发**。"已生成 N 张图"不等于图是对的。

## 交付清单模板（贴进四行头）

```markdown
任务：<做什么 + 边界>
结论：<完成度 + 关键数字>
产物：<绝对路径清单>
证据：
  机器：根部以外颜色值=0 | 未定义 var=0 | 语法 OK | 5 路由无 Uncaught
  交互：popup=true | gate0=true | gate3=true | closed=true | row=已验
  截图：1440_chat.png / 1280_chat.png / 1440_modal.png
交互说明：<点哪里 → 发生什么，3–6 条>
状态清单：<组件 × 状态 打勾表>
已知限制：<演示数据、无持久化、占位功能>
待决策：<需要对方拍板的点，2–4 条>
```

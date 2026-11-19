# -*- coding: utf-8 -*-
r"""
UI 调试台（单文件 · 零依赖）
==============================

一句话：左边看真实页面，右边看对应源码，点哪儿跳哪儿；双击改代码，Ctrl+S 即生效。

前置：装了 Python 3.9+ 就能跑，不需要装任何库。

用法（三条命令，任选）
--------------------
1) 监视整个目录（推荐）
     python "UI调试台.py" --dir "D:\你的项目" --port 8792
     默认开启 UI 安全编辑：只允许文案和局部内联样式；越界改动保存在
     .history\candidates\*.candidate.patch，不覆盖源码。

2) 只看一个文件
     python "UI调试台.py" "D:\你的项目\index.html" 8792

3) 什么都不给 = 监视当前目录
     python "UI调试台.py"

开发人员需要整文件编辑时显式关闭安全模式：
     python "UI调试台.py" --dir "D:\你的项目" --unsafe

启动后浏览器自动打开 http://127.0.0.1:8792/

界面
----
顶栏    文件下拉框 / 监视目录 / 更新时间 / 缩放 / 手动刷新
板块条  由 <!-- ===== 名称 ===== --> 注释自动生成，点了滚到该块
左侧    真实页面          右侧  源码（带行号，改动行高亮）

六个操作
--------
点左边元素 → 右边跳到那行          点右边代码 → 左边描蓝框
搜代码 → 回车定位                  勾「只看中文说明」→ 只剩目录
双击代码行 → 改 → Ctrl+S           改坏了 → 点「撤销」

网格与量尺（给"挪 10px"这类精细活用的）
--------------------------------------
预览区左上角有工具条，两个开关都是叠加层，不改任何源码：

  ▦ 网格  细格 8px、粗格 80px 的虚线格。8px 是常见间距基数，粗格用来
          一眼定位"在第几格到第几格之间"。pointer-events:none，不挡点击。

  ⌖ 量尺  开启后【点击即钉住坐标】，不是跟着鼠标跑：
            · 点第 1 下 → 钉 A 点，画红十字 + 标签，坐标定住
            · 点第 2 下 → 钉 B 点，显示 dx / dy / 直线距离
            · 点第 3 下 → 清空重来
            · 钉住后鼠标怎么移，坐标都不会变（可以放心去点「复制」）
            · 「复制」给出可粘贴的文本，含元素选择器，直接发给 AI 就能改

  为什么必须"点击钉住"：原来的做法是鼠标移动实时刷新坐标，手一抬数字就没了，
  根本记不住。钉住之后坐标冻结，才能读数、复制、报给 AI。

  例（复制出来的内容）：
    点A：x=120 y=60  元素 h1.title
    点B：x=240 y=90  元素 h1.title
    两点差：dx=120px  dy=30px（从 A 到 B）
    距离：124px

  跨源限制：用 --url 打开外部地址时浏览器禁止注入，网格/量尺会自动禁用并提示。

安全网
------
每次保存前自动备份到 <项目>\.history\（留最近 30 份）
每次保存/撤销写一行 <项目>\.history\edits.log

能力边界
--------
只支持静态文件（html/css/js/json/md/vue）。需要构建的工程（React/Vue 项目）、
PHP 后端、需要登录的页面跑不起来；只做单人本地使用。
"""

import argparse
import difflib
import hashlib
import json
import mimetypes
import os
import re
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

TEXT_EXT = {".html", ".htm", ".php", ".css", ".js", ".json", ".txt", ".md", ".vue"}
VOID_PY = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
           "meta", "param", "source", "track", "wbr"}
SAFE_STYLE_PROPS = {
    "color", "background-color",
    "border-color", "border-top-color", "border-right-color",
    "border-bottom-color", "border-left-color",
    "border-radius", "border-top-left-radius", "border-top-right-radius",
    "border-bottom-left-radius", "border-bottom-right-radius",
    "font-size", "line-height", "letter-spacing",
    "margin", "margin-top", "margin-right", "margin-bottom", "margin-left",
    "padding", "padding-top", "padding-right", "padding-bottom", "padding-left",
    "gap", "row-gap", "column-gap"
}
CFG = {"mode": "file", "target": "", "root": "", "url": "", "port": 8790, "safe_ui": True}

VIEWER = r"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>UI 调试台</title>
<style>
  :root{--bg:#0f1115;--panel:#14171c;--line:#232830;--ink:#e7eaf0;--muted:#8b93a7;
        --ok:#22c55e;--new:#a78bfa}
  *{box-sizing:border-box}
  html,body{height:100%;margin:0}
  body{display:flex;flex-direction:column;background:var(--bg);color:var(--ink);
       font:13px/1.5 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif;overflow:hidden}
  header{display:flex;align-items:center;gap:10px;padding:9px 14px;border-bottom:1px solid var(--line);background:var(--panel)}
  header b{font-size:13px;font-weight:600;white-space:nowrap}
  header .path{color:var(--muted);font-family:Consolas,monospace;font-size:11px;
               max-width:30vw;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  header .dot{width:7px;height:7px;border-radius:50%;background:var(--ok);flex:0 0 auto}
  header .dot.flash{background:var(--new);box-shadow:0 0 0 3px rgba(167,139,250,.22)}
  header .st{color:var(--muted);font-size:11px;white-space:nowrap;max-width:34vw;overflow:hidden;text-overflow:ellipsis}
  header .stylelock{color:#bfdbfe;background:#172554;border:1px solid #1e40af;border-radius:99px;
                    padding:2px 8px;font-size:11px;white-space:nowrap;max-width:40vw;overflow:hidden;text-overflow:ellipsis}
  header .stylelock.adjustable{color:#fed7aa;background:#431407;border-color:#c2410c}
  header .stylelock.unset{color:#cbd5e1;background:#1f2937;border-color:#475569}
  header .grow{flex:1}
  header .zoom{color:var(--muted);font-size:11px;font-family:Consolas,monospace;min-width:44px;text-align:right}
  select{background:#0f1115;border:1px solid var(--line);color:var(--ink);border-radius:6px;padding:4px 8px;font-size:12px;max-width:280px}
  button{background:#2563eb;color:#fff;border:0;border-radius:6px;padding:5px 11px;font-size:12px;cursor:pointer;white-space:nowrap}
  button.ghost{background:transparent;color:var(--muted);border:1px solid var(--line)}
  .mode{font-size:11px;padding:2px 8px;border-radius:99px;background:#12351f;color:#86efac;border:1px solid #1f6b38}
  .mode.unsafe{background:#3a2112;color:#f5c56b;border-color:#815a24}

  .wrap{flex:1;display:flex;min-height:0}
  .left{flex:1;min-width:0;position:relative;overflow:hidden;background:#e9ecf0}
  .stage{position:absolute;top:0;left:0;width:1360px;height:900px;transform-origin:0 0;
         box-shadow:0 8px 40px rgba(0,0,0,.35);background:#fff}
  .stage iframe{width:1360px;height:900px;border:0;display:block;background:#fff}

  /* 网格 / 量尺工具条（不随 stage 缩放） */
  .gridbar{position:absolute;top:8px;left:8px;z-index:30;display:flex;gap:6px;align-items:center;
    background:rgba(20,24,32,.9);border:1px solid #2b3240;border-radius:8px;padding:5px 8px;
    font-size:11px;color:#c9d3e0;box-shadow:0 4px 14px rgba(0,0,0,.32)}
  .gridbar button{background:#1e2530;border:1px solid #33405a;color:#a9b6c9;border-radius:6px;
    padding:3px 9px;font-size:11px;cursor:pointer;font:inherit;font-size:11px}
  .gridbar button:hover{color:#fff;border-color:#4a5c80}
  .gridbar button.on{background:#1d4ed8;border-color:#3b82f6;color:#fff}
  .gridbar .coord{font-variant-numeric:tabular-nums;color:#8fd6ff;min-width:132px;
    font-family:ui-monospace,Consolas,monospace;font-size:11px}
  .gridbar .hintpx{color:#6b7a90;font-size:10.5px}
  .splitter{width:5px;background:var(--line);cursor:col-resize;flex:0 0 5px}
  .right{width:36%;min-width:240px;display:flex;flex-direction:column;background:var(--panel);border-left:1px solid var(--line)}
  .tabs{display:flex;align-items:center;gap:8px;padding:7px 12px;border-bottom:1px solid var(--line);color:var(--muted);font-size:11px}
  .tabs b{color:var(--ink);font-weight:500}
  .code{flex:1;overflow:auto;padding:8px 0}
  .code pre{margin:0;font:12px/1.65 Consolas,"SFMono-Regular",monospace;tab-size:2}
  .row{display:flex;gap:10px;padding:0 12px;cursor:pointer}
  .row:hover{background:rgba(255,255,255,.03)}
  .row .ln{color:#4b5563;text-align:right;width:38px;flex:0 0 38px;user-select:none}
  .row .tx{white-space:pre-wrap;word-break:break-word;flex:1;color:#c9d1e0}
  .row.new{background:rgba(167,139,250,.10)}
  .row.new .tx{color:#d6c7ff}
  .row.hit{background:rgba(79,140,255,.16)}
  .row.hit .tx{color:#cfe1ff}
  .row.cmt .tx{color:#7ee787;font-style:italic}
  .row.cmt .ln{color:#3f5f45}
  .code.only .row:not(.cmt){display:none}
  .chk{color:var(--muted);font-size:11px;display:flex;align-items:center;gap:4px;cursor:pointer;white-space:nowrap}
  #editArea{display:none;flex:1;width:100%;border:0;outline:none;resize:none;
            background:#0f1115;color:#c9d1e0;font:12px/1.65 Consolas,"SFMono-Regular",monospace;
            padding:8px 12px;tab-size:2;white-space:pre;overflow:auto}
  body.editing #code{display:none}
  body.editing #editArea{display:block}
  #btnSave{background:#16a34a}
  .conflict{background:#3a2112;color:#f5c56b;font-size:11px;padding:5px 12px;display:none;align-items:center;gap:10px}
  .conflict a{color:#f5c56b;text-decoration:underline;cursor:pointer}
  .safeerr{display:none;background:#32161a;color:#fecaca;border-bottom:1px solid #7f1d1d;padding:10px 12px;font-size:12px}
  .safeerr b{color:#fca5a5}
  .safeerr ul{margin:6px 0 0 18px}
  .safeerr code{font-family:Consolas,monospace;color:#fde68a;word-break:break-all}
  #find{background:#0f1115;border:1px solid var(--line);color:var(--ink);border-radius:5px;
        padding:4px 8px;font-size:11px;width:170px;font-family:Consolas,monospace;outline:none}
  #findinfo{color:var(--muted);font-size:11px;white-space:nowrap}
  .hint{padding:6px 12px;border-top:1px solid var(--line);color:var(--muted);font-size:11px}
  .warn{background:#3a2a12;color:#f5c56b;font-size:11px;padding:4px 12px;display:none}
  .secbar{display:none;gap:6px;flex-wrap:wrap;align-items:center;padding:6px 10px;
          background:#0b1220;border-bottom:1px solid #1e293b}
  .secbar .tip{color:#64748b;font-size:12px;margin-right:2px}
  .secbar button{font:12px/1.2 inherit;color:#cbd5e1;background:#1e293b;border:1px solid #334155;
          border-radius:14px;padding:5px 11px;cursor:pointer}
  .secbar button:hover{background:#334155;color:#f8fafc}
  .secbar button.on{background:#2563eb;border-color:#2563eb;color:#fff}
</style></head>
<body>
<header>
  <span class="dot" id="dot"></span>
  <b>UI 调试台</b>
  <span class="mode" id="safeMode">安全编辑</span>
  <span class="stylelock unset" id="styleLock">风格：未选择</span>
  <select id="files" style="display:none"></select>
  <span class="path" id="path">—</span>
  <span class="st" id="st">等待第一次刷新</span>
  <span class="grow"></span>
  <span class="zoom" id="zoom">—</span>
  <button class="ghost" onclick="reloadAll(true)">手动刷新</button>
</header>
<div class="warn" id="warn"></div>
<div class="secbar" id="secbar"></div>
<div class="wrap">
  <div class="left" id="left">
    <div class="gridbar" id="gridbar">
      <button id="btnGrid" title="叠加虚线网格：细格 8px，粗格 80px">▦ 网格</button>
      <button id="btnInteract" title="开启后：预览里可直接点击页面（切板块/切角色/点按钮）；关闭时：点击预览=跳到对应源码行">▷ 交互</button>
      <button id="btnPick" title="开量尺后点击钉住坐标（再点一次=第二点，第三点重来）">⌖ 量尺</button>
      <span class="coord" id="coord">—</span>
      <button id="btnCoord" title="复制钉住的坐标">复制</button>
      <button id="btnClearPin" title="清空钉住的点">清空</button>
      <span class="hintpx">细格 8 / 粗格 80</span>
    </div>
    <div class="stage" id="stage"><iframe id="view"></iframe></div>
  </div>
  <div class="splitter" id="sp"></div>
  <div class="right">
    <div class="tabs"><b>源码</b><span id="info"></span>
      <span style="flex:1"></span>
      <label class="chk"><input type="checkbox" id="onlyCmt"> 只看中文说明</label>
      <input id="find" placeholder="搜代码 / 回车定位">
      <span id="findinfo"></span>
      <button class="ghost" id="btnEdit">编辑</button>
      <button id="btnSave" style="display:none">保存</button>
      <button class="ghost" id="btnUndo" title="恢复成上一次保存之前的内容">撤销</button>
    </div>
    <div class="conflict" id="conflict">
      <span>文件已被外部改动（可能是你自己的编辑器）</span>
      <a onclick="adoptDisk()">重新载入磁盘版本</a>
      <a onclick="hideConflict()">继续我的修改</a>
    </div>
    <div class="safeerr" id="safeError">
      <b>UI 安全编辑已拦截，源码未写入</b>
      <ul id="safeReasons"></ul>
      <div id="safePatch"></div>
      <div style="margin-top:8px"><button class="ghost" onclick="hideSafeError()">关闭提示</button></div>
    </div>
    <div class="code" id="code"></div>
    <textarea id="editArea" spellcheck="false"></textarea>
    <div class="hint">点左边元素 → 右边跳代码　|　点右边代码 → 左边描蓝框　|　▦ 网格叠格子　|　⌖ 量尺点击钉住坐标（钉住后坐标不动，可复制发给 AI）</div>
  </div>
</div>
<script>
const DW = 1360, DH = 900;
let lastMtime = 0, prevArr = [], first = true, query = '', srcText = '';
let EDITING = false, DIRTY = false, INTERACT = false;   // INTERACT=true 时不拦截预览里的点击
let MODE = 'file', DIRFILES = [], CURRENT = '';

function fit() {
  const left = document.getElementById('left'), stage = document.getElementById('stage');
  const k = Math.min((left.clientWidth - 24) / DW, (left.clientHeight - 24) / DH);
  const s = Math.max(0.2, k);
  stage.style.transform = 'scale(' + s + ')';
  stage.style.left = Math.max(0, (left.clientWidth - DW * s) / 2) + 'px';
  stage.style.top  = Math.max(0, (left.clientHeight - DH * s) / 2) + 'px';
  document.getElementById('zoom').textContent = Math.round(s * 100) + '%';
}

function applyFind(q, jump) {
  query = (q || '').trim();
  const box = document.getElementById('code'), rows = Array.from(box.children), hits = [];
  rows.forEach((r, i) => { r.classList.remove('hit'); if (query && r.textContent.includes(query)) hits.push(i); });
  hits.forEach(i => rows[i].classList.add('hit'));
  document.getElementById('findinfo').textContent = query ? (hits.length ? '第 ' + (hits[0]+1) + ' 行 · 共 ' + hits.length + ' 处' : '没找到') : '';
  if (query && hits.length && jump !== false) box.scrollTop = Math.max(0, rows[hits[0]].offsetTop - box.clientHeight/3);
}

async function pullCode() {
  const name = encodeURIComponent(CURRENT);
  const r = await fetch('/source?f=' + name, {cache: 'no-store'});
  const text = await r.text();
  srcText = text;
  const lines = text.split('\n'), box = document.getElementById('code');
  const changed = [];
  lines.forEach((ln, i) => { if (prevArr[i] !== ln) changed.push(i); });
  const changedSet = new Set(changed);
  box.innerHTML = '';
  lines.forEach((ln, i) => {
    const d = document.createElement('div'), t0 = ln.trim();
    const isCmt = t0.startsWith('/*') || t0.startsWith('*/') || t0.startsWith('<!--') ||
                  t0.startsWith('//') || t0.startsWith('* ') || t0 === '*';
    d.className = 'row' + (isCmt ? ' cmt' : '') + (!first && changedSet.has(i) ? ' new' : '');
    const n = document.createElement('span'); n.className = 'ln'; n.textContent = i + 1;
    const t = document.createElement('span'); t.className = 'tx'; t.textContent = ln || ' ';
    d.append(n, t); box.append(d);
  });
  prevArr = lines;
  buildSections();
  document.getElementById('info').textContent = lines.length + ' 行';
  if (query) applyFind(query, false);
  if (!first && changed.length) return changed[0] + 1;
  return 0;
}

function frameSrc(stamp) {
  if (MODE === 'url') return (window.__URL__ || '') + (window.__URL__ ? (window.__URL__.includes('?') ? '&' : '?') + 't=' + stamp : '');
  return '/site/' + encodeURIComponent(CURRENT) + '?t=' + stamp;
}

async function reloadAll(manual) {
  const s = await (await fetch('/stat', {cache: 'no-store'})).json();
  MODE = s.mode; DIRFILES = s.files || []; window.__URL__ = s.url || '';
  const mode = document.getElementById('safeMode');
  mode.textContent = s.safe_ui ? '安全编辑' : '开发模式 · 不拦截';
  mode.className = 'mode' + (s.safe_ui ? '' : ' unsafe');
  const styleLock = document.getElementById('styleLock');
  styleLock.textContent = s.style_name
    ? '风格：' + s.style_name + (s.style_locked ? '（已锁定）' : '（可调）')
    : '风格：未选择';
  styleLock.title = styleLock.textContent;
  styleLock.className = 'stylelock' + (!s.style_name ? ' unset' : (s.style_locked ? '' : ' adjustable'));
  // 编辑中若磁盘被改动，先提示冲突，别把用户正在写的内容冲掉
  if (EDITING && !manual && s.mtime !== lastMtime) {
    document.getElementById('conflict').style.display = 'flex';
    return;
  }
  document.getElementById('path').textContent = s.url || s.path || s.root;
  if (MODE !== 'file') {
    const sel = document.getElementById('files');
    sel.style.display = '';
    if (sel.options.length !== DIRFILES.length || (DIRFILES[0] && sel.options[0].value !== DIRFILES[0])) {
      sel.innerHTML = '';
      DIRFILES.forEach(f => { const o = document.createElement('option'); o.value = f; o.textContent = f; sel.append(o); });
      sel.value = s.current || DIRFILES[0] || '';
    }
    if (!CURRENT) CURRENT = s.current || DIRFILES[0] || '';
  }
  if (manual || s.mtime !== lastMtime) {
    lastMtime = s.mtime;
    document.getElementById('view').src = frameSrc(Date.now());
    const line = await pullCode();
    const dot = document.getElementById('dot');
    dot.classList.add('flash'); setTimeout(() => dot.classList.remove('flash'), 1200);
    const t = new Date().toLocaleTimeString('zh-CN', {hour12: false});
    document.getElementById('st').textContent = (line ? '已更新 · 跳到第 ' + line + ' 行 · ' : '已更新 · ') + t;
    first = false;
    setTimeout(indexFrame, 120);
  }
}

document.getElementById('files').addEventListener('change', e => {
  CURRENT = e.target.value; prevArr = []; lastMtime = 0;
  document.getElementById('view').src = frameSrc(Date.now());
  reloadAll(true);
});

setInterval(() => reloadAll(false), 900);
window.addEventListener('resize', fit);
document.getElementById('find').addEventListener('keydown', e => { if (e.key === 'Enter') applyFind(e.target.value, true); });
document.getElementById('onlyCmt').addEventListener('change', e => {
  document.getElementById('code').classList.toggle('only', e.target.checked);
});
// 双击代码行 → 进入编辑并定位到该行
function offsetOfLine(n) {
  const lines = srcText.split('\n');
  let off = 0;
  for (let i = 0; i < n - 1 && i < lines.length; i++) off += lines[i].length + 1;
  return off;
}

document.getElementById('code').addEventListener('dblclick', ev => {
  const row = ev.target.closest('.row');
  if (!row || !row.children[0]) return;
  const n = parseInt(row.children[0].textContent, 10) || 1;
  if (!EDITING) toggleEdit(true);
  const area = document.getElementById('editArea');
  const off = offsetOfLine(n);
  area.focus();
  area.setSelectionRange(off, off);
  const lh = parseFloat(getComputedStyle(area).lineHeight) || 20;
  area.scrollTop = Math.max(0, (n - 1) * lh - area.clientHeight / 3);
  document.getElementById('findinfo').textContent = '双击定位到第 ' + n + ' 行';
});

document.getElementById('btnEdit').addEventListener('click', () => toggleEdit(!EDITING));
document.getElementById('btnInteract').addEventListener('click', function(){
  INTERACT = !INTERACT;
  this.classList.toggle('on', INTERACT);
  const st = document.getElementById('st');
  if (st) st.textContent = INTERACT
    ? '交互模式：预览里可直接点击页面（点元素不再跳源码）'
    : '定位模式：点击预览 = 跳到对应源码行';
});
document.getElementById('btnUndo').addEventListener('click', undoLast);

async function undoLast() {
  if (!confirm('把当前文件恢复成「上一次保存之前」的内容？')) return;
  const r = await fetch('/undo', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({f: CURRENT})
  });
  let j = {};
  try { j = await r.json(); } catch (e) {}
  if (j.ok) {
    lastMtime = 0;
    await reloadAll(true);
    if (EDITING) document.getElementById('editArea').value = srcText;
    document.getElementById('st').textContent = '已回滚 · 来自 ' + (j.from || '历史版本');
  } else {
    alert('回滚失败：' + (j.error || '未知错误'));
  }
}
document.getElementById('btnSave').addEventListener('click', saveFile);
document.getElementById('editArea').addEventListener('input', () => { DIRTY = true; hideSafeError(); });
document.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
    e.preventDefault();
    if (EDITING) saveFile();
  }
});

reloadAll(true).then(() => {
  fit();
  const q = new URLSearchParams(location.search).get('q');
  if (q) { document.getElementById('find').value = q; applyFind(q, true); }
});

/* ============ 双向联动 ============ */
const VOID = new Set(['area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr']);
let ELEM = [], frameMap = new WeakMap(), linkOK = false;

function countNL(s){ let n=0; for(let i=0;i<s.length;i++) if(s.charCodeAt(i)===10) n++; return n; }

function buildElemIndex(src){
  const re = /<!--[\s\S]*?-->|<!doctype[^>]*>|<\s*(\/?)\s*([a-zA-Z][\w:-]*)([^>]*)>/gi;
  const out = [], stack = [];
  let m, line = 1, last = 0;
  while((m = re.exec(src)) !== null){
    line += countNL(src.slice(last, m.index)); last = m.index;
    if(m[0].startsWith('<!--') || /^<!doctype/i.test(m[0]) || !m[2]) continue;
    const closing = !!m[1], tag = m[2].toLowerCase();
    const selfClose = /\/\s*>$/.test(m[0]) || VOID.has(tag);
    if(!closing){
      const node = {line, end: line, tag};
      out.push(node);
      if(!selfClose) stack.push(node);
    } else {
      for(let i=stack.length-1;i>=0;i--){ if(stack[i].tag === tag){ stack[i].end = line; stack.length = i; break; } }
    }
  }
  return out;
}

function iframeEls(){
  try {
    const doc = document.getElementById('view').contentDocument;
    if(!doc || !doc.documentElement) return null;
    const all = [];
    (function walk(n){ all.push(n); for(const c of n.children) walk(c); })(doc.documentElement);
    return all;
  } catch(e) { return null; }   // 跨源
}

function markInFrame(el){
  const doc = el.ownerDocument;
  doc.querySelectorAll('[data-dsh-hl]').forEach(x => { x.style.outline=''; x.style.outlineOffset=''; x.removeAttribute('data-dsh-hl'); });
  el.style.outline = '2px solid #4f8cff'; el.style.outlineOffset = '2px';
  el.setAttribute('data-dsh-hl','1');
  setTimeout(() => { el.style.outline=''; el.style.outlineOffset=''; el.removeAttribute('data-dsh-hl'); }, 2600);
}

function toggleEdit(on) {
  EDITING = on;
  document.body.classList.toggle('editing', on);
  document.getElementById('btnEdit').textContent = on ? '退出编辑' : '编辑';
  document.getElementById('btnSave').style.display = on ? '' : 'none';
  const area = document.getElementById('editArea');
  if (on) { area.value = srcText; DIRTY = false; area.focus(); }
  hideSafeError();
}

async function saveFile() {
  const area = document.getElementById('editArea');
  const r = await fetch('/save', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({f: CURRENT, content: area.value})
  });
  let j = {};
  try { j = await r.json(); } catch (e) {}
  if (j.ok) {
    DIRTY = false;
    document.getElementById('conflict').style.display = 'none';
    hideSafeError();
    const t = new Date().toLocaleTimeString('zh-CN', {hour12: false});
    lastMtime = 0;
    // 保存成功后自动退出编辑态，回到"看页面 + 看代码"的常态
    if (EDITING) toggleEdit(false);
    await reloadAll(true);
    if (EDITING) area.value = srcText;
    document.getElementById('st').textContent = '已保存并退出编辑 · ' + t;
  } else {
    if (j.blocked) showSafeError(j);
    else alert('保存失败：' + (j.error || '未知错误'));
  }
}

function showSafeError(j) {
  const box = document.getElementById('safeError');
  const list = document.getElementById('safeReasons');
  const patch = document.getElementById('safePatch');
  list.replaceChildren();
  (j.reasons || [j.error || '改动超出 UI 安全编辑范围']).forEach(function (textValue) {
    const li = document.createElement('li');
    li.textContent = textValue;
    list.append(li);
  });
  patch.replaceChildren();
  if (j.patch) {
    patch.append('候选补丁：');
    const code = document.createElement('code');
    code.textContent = j.patch;
    patch.append(code);
  } else {
    patch.textContent = '候选补丁生成失败，但源码仍未被修改。请保留编辑框内容并联系 AI-C。';
  }
  box.style.display = 'block';
  box.scrollIntoView({block: 'nearest'});
}

function hideSafeError() {
  document.getElementById('safeError').style.display = 'none';
}

function adoptDisk() {
  document.getElementById('conflict').style.display = 'none';
  lastMtime = 0;
  reloadAll(true).then(() => {
    if (EDITING) document.getElementById('editArea').value = srcText;
  });
}
function hideConflict() {
  document.getElementById('conflict').style.display = 'none';
  lastMtime = 0;
}

function jumpToLine(line, msg){
  const box = document.getElementById('code'), row = box.children[line-1];
  if(!row) return;
  box.scrollTop = Math.max(0, row.offsetTop - box.clientHeight/3);
  row.classList.add('hit'); setTimeout(()=>row.classList.remove('hit'), 2400);
  document.getElementById('findinfo').textContent = msg || ('第 ' + line + ' 行');
}

// 交互模式：把源码区滚到「当前可见页面容器」对应的源码行
function followVisiblePage(doc){
  try{
    if(!linkOK || !doc) return;
    const all = Array.from(doc.querySelectorAll('section, main, [data-page-view]'));
    // 只取最外层容器（排除嵌套在其它 section 里的），并且确实可见、有高度
    const vis = all.filter(el => {
      if(el.parentElement && el.parentElement.closest('section, main')) return false;
      const r = el.getBoundingClientRect();
      if(r.width < 100 || r.height < 120) return false;
      const cs = doc.defaultView.getComputedStyle(el);
      return cs.display !== 'none' && cs.visibility !== 'hidden';
    });
    const target = vis[0];
    if(!target) return;
    let el = target;
    while(el && !frameMap.has(el)) el = el.parentElement;
    if(!el) return;
    const node = ELEM[frameMap.get(el)];
    if(!node) return;
    jumpToLine(node.line, '交互 → 已跟随到当前页面：第 ' + node.line + ' 行');
  }catch(e){ /* 跟随失败不影响交互 */ }
}

function indexFrame(){
  const all = iframeEls();
  const warn = document.getElementById('warn');
  if(!all || !all.length){ linkOK = false; }
  else {
    linkOK = true;
    frameMap = new WeakMap();
    all.forEach((el,i) => frameMap.set(el,i));
    ELEM = buildElemIndex(srcText);
    const doc = document.getElementById('view').contentDocument;
    doc.addEventListener('click', ev => {
      if (INTERACT) {                           // 交互模式：让页面自己处理点击
        setTimeout(function(){ followVisiblePage(document.getElementById('view').contentDocument); }, 220);
        return;
      }
      ev.preventDefault(); ev.stopPropagation();
      let el = ev.target;
      while(el && !frameMap.has(el)) el = el.parentElement;
      if(!el) return;
      const node = ELEM[frameMap.get(el)];
      if(!node) return;
      markInFrame(el);
      jumpToLine(node.line, '预览 → 代码：第 ' + node.line + ' 行 <' + node.tag + '>');
    }, true);
  }
  if(MODE === 'url' && !linkOK){
    warn.style.display = 'block';
    warn.textContent = '注意：左侧是外部地址（跨源），双向联动已关闭，右侧只做源码查看。若要联动，请用 --dir 让本工具自己托管静态目录。';
  } else { warn.style.display = 'none'; }
}

document.getElementById('code').addEventListener('click', ev => {
  const row = ev.target.closest('.row');
  if(!row || !row.children[0] || !ELEM.length || !linkOK) return;
  const line = parseInt(row.children[0].textContent, 10);
  if(!line) return;
  let best = null;
  ELEM.forEach(n => { if(n.line <= line && line <= n.end && (!best || (n.end-n.line) <= (best.end-best.line))) best = n; });
  if(!best) return;
  const all = iframeEls();
  const el = all && all[ELEM.indexOf(best)];
  if(!el) return;
  markInFrame(el);
  el.scrollIntoView({block:'center', inline:'center'});
  document.getElementById('findinfo').textContent = '代码 → 预览：第 ' + line + ' 行 <' + best.tag + '>';
});

/* ============ 虚线网格 + 量尺（报坐标给 AI 用） ============ */
let gridOn = false, pickOn = false, coordText = '';

function frameDoc(){
  try { const d = document.getElementById('view').contentDocument;
        return (d && d.documentElement) ? d : null; } catch(e) { return null; }
}

function applyGrid(){
  const doc = frameDoc(); if(!doc) return;
  const old = doc.getElementById('__dsh_grid');
  if(!gridOn){ if(old) old.remove(); return; }
  if(old) return;
  const g = doc.createElement('div');
  g.id = '__dsh_grid';
  g.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:2147483647;';
  g.style.backgroundImage = [
    'repeating-linear-gradient(0deg, rgba(37,99,235,.15) 0 1px, transparent 1px 8px)',
    'repeating-linear-gradient(90deg, rgba(37,99,235,.15) 0 1px, transparent 1px 8px)',
    'repeating-linear-gradient(0deg, rgba(37,99,235,.42) 0 1px, transparent 1px 80px)',
    'repeating-linear-gradient(90deg, rgba(37,99,235,.42) 0 1px, transparent 1px 80px)'
  ].join(',');
  (doc.body || doc.documentElement).appendChild(g);
}

function shortSel(el){
  if(!el || !el.tagName) return '?';
  let s = el.tagName.toLowerCase();
  if(el.id) return s + '#' + el.id;          // 有 id 就够定位了，不再堆 class
  const cls = (el.getAttribute && el.getAttribute('class') || '').trim().split(/\s+/).filter(Boolean).slice(0,2);
  if(cls.length) s += '.' + cls.join('.');
  return s;
}

function describe(el){
  const r = el.getBoundingClientRect();
  const x = Math.round(r.left), y = Math.round(r.top);
  const w = Math.round(r.width), h = Math.round(r.height);
  // 相对父元素的偏移（gap 用）
  let pl = 0, pt = 0, psel = '—';
  const p = el.parentElement;
  if(p){
    const pr = p.getBoundingClientRect();
    pl = Math.round(r.left - pr.left); pt = Math.round(r.top - pr.top);
    psel = shortSel(p);
  }
  coordText =
    '[元素] ' + shortSel(el) + '\n' +
    '[视口] x=' + x + ' y=' + y + ' 宽=' + w + ' 高=' + h + '\n' +
    '[父内] left=' + pl + ' top=' + pt + '（父：' + psel + '）\n' +
    '[改这里] 往右 ____px / 往下 ____px / 宽 ____px / 高 ____px';
  document.getElementById('coord').textContent = x + ',' + y + ' · ' + w + '×' + h;
  document.getElementById('coord').title = coordText;
}

function setCoord(txt){
  document.getElementById('coord').textContent = txt;
}

/* 钉住的测量点：点击即记录，鼠标移开也不丢 */
let pins = [];          // [{x, y, el, tag}]

function clearPins(doc){
  doc = doc || frameDoc();
  if(doc){
    doc.querySelectorAll('[data-dsh-pin]').forEach(n => n.remove());
  }
  pins = [];
  coordText = '';
  setCoord('—');
}

function drawPin(doc, x, y, label){
  const mk = (css) => {
    const d = doc.createElement('div');
    d.setAttribute('data-dsh-pin', '1');
    d.style.cssText = 'position:absolute;pointer-events:none;z-index:2147483646;' + css;
    (doc.body || doc.documentElement).appendChild(d);
    return d;
  };
  const sx = doc.documentElement.scrollLeft || doc.body.scrollLeft || 0;
  const sy = doc.documentElement.scrollTop || doc.body.scrollTop || 0;
  // 十字线
  mk('left:' + (x + sx - 0.5) + 'px;top:0;width:1px;height:100%;background:rgba(239,68,68,.85);');
  mk('top:' + (y + sy - 0.5) + 'px;left:0;height:1px;width:100%;background:rgba(239,68,68,.85);');
  // 标签
  const tag = mk('left:' + (x + sx + 6) + 'px;top:' + (y + sy + 6) + 'px;' +
    'background:#ef4444;color:#fff;font:11px/1.4 ui-monospace,Consolas,monospace;' +
    'padding:2px 6px;border-radius:4px;white-space:nowrap;box-shadow:0 2px 6px rgba(0,0,0,.3);');
  tag.textContent = label + ' ' + x + ',' + y;
}

function buildPinText(){
  const L = [];
  if(!pins.length) return '';
  pins.forEach(function(p, i){
    const n = String.fromCharCode(65 + i);   // A/B/C
    L.push('点' + n + '：x=' + p.x + ' y=' + p.y + (p.tag ? '　元素 ' + p.tag : ''));
  });
  if(pins.length >= 2){
    const a = pins[0], b = pins[1];
    L.push('');
    L.push('两点差：dx=' + (b.x - a.x) + 'px  dy=' + (b.y - a.y) + 'px（从 A 到 B）');
    L.push('距离：' + Math.round(Math.hypot(b.x - a.x, b.y - a.y)) + 'px');
  }
  L.push('');
  L.push('[用来改位置] 往右 ____px / 往下 ____px');
  return L.join('\n');
}

function hookFrame(){
  const doc = frameDoc(); if(!doc) return;
  applyGrid();
  if(doc.__dshHooked) return;
  doc.__dshHooked = true;

  // 鼠标移动只做"预览坐标"；钉住之后不再覆盖
  doc.addEventListener('mousemove', function(e){
    if(!pickOn) return;
    if(pins.length) return;                 // 已钉住 → 不刷新，坐标保持
    setCoord('x=' + e.clientX + '  y=' + e.clientY + '　（点击钉住）');
  }, true);

  doc.addEventListener('click', function(e){
    if(!pickOn) return;
    e.preventDefault(); e.stopPropagation();

    // 第三个点开始重来
    if(pins.length >= 2) clearPins(doc);

    const x = e.clientX, y = e.clientY;
    const el = e.target;
    const tag = shortSel(el);
    pins.push({x: x, y: y, tag: tag});
    drawPin(doc, x, y, String.fromCharCode(64 + pins.length));

    if(pins.length === 1){
      setCoord('钉住 A：' + x + ',' + y);
    } else {
      const a = pins[0], b = pins[1];
      setCoord('A→B：dx=' + (b.x - a.x) + ' dy=' + (b.y - a.y));
    }
  }, true);
}

document.getElementById('btnGrid').addEventListener('click', function(){
  gridOn = !gridOn;
  this.classList.toggle('on', gridOn);
  if(gridOn && !frameDoc()) { alert('左侧是外部地址（跨源），网格不可用。请用 --dir 打开本地目录。'); gridOn=false; this.classList.remove('on'); return; }
  applyGrid();
});

document.getElementById('btnPick').addEventListener('click', function(){
  pickOn = !pickOn;
  this.classList.toggle('on', pickOn);
  if(!pickOn) { clearPins(); return; }
  const doc = frameDoc();
  if(!doc){ alert('左侧是外部地址（跨源），量尺不可用。请用 --dir 打开本地目录。'); pickOn=false; this.classList.remove('on'); return; }
  hookFrame();
  setCoord('点击钉住坐标');
});

document.getElementById('btnClearPin').addEventListener('click', function(){
  clearPins();
  setCoord('已清空');
});

document.getElementById('btnCoord').addEventListener('click', function(){
  const txt = buildPinText();
  if(!txt){ setCoord('先点击钉一个点'); return; }
  coordText = txt;
  const ta = document.createElement('textarea');
  ta.value = coordText; ta.style.position='fixed'; ta.style.left='-9999px';
  document.body.appendChild(ta); ta.select();
  try { document.execCommand('copy'); setCoord('已复制 ✓（' + pins.length + ' 个点）'); }
  catch(e) { setCoord('复制失败'); }
  document.body.removeChild(ta);
});

document.getElementById('view').addEventListener('load', () => setTimeout(indexFrame, 120));
document.getElementById('view').addEventListener('load', () => setTimeout(hookFrame, 200));

/* ============ 板块跳转：从中文分区注释里生成按钮 ============ */
function buildSections() {
  const bar = document.getElementById('secbar');
  bar.innerHTML = '';
  const re = /^\s*(?:<!--|\/\*)\s*=*\s*([^=<>*]{1,40}?)\s*=*\s*(?:-->|\*\/)\s*$/;
  let n = 0;
  srcText.split('\n').forEach((ln, i) => {
    const m = ln.match(re);
    if (!m) return;
    const name = m[1].trim();
    if (!name || /^[-=\s]+$/.test(name)) return;
    if (n === 0) {
      const tip = document.createElement('span');
      tip.className = 'tip';
      tip.textContent = '板块：';
      bar.append(tip);
    }
    const b = document.createElement('button');
    b.textContent = name;
    b.title = '第 ' + (i + 1) + ' 行';
    b.onclick = () => gotoSection(i + 1, b);
    bar.append(b);
    n++;
  });
  bar.style.display = n ? 'flex' : 'none';
}

function gotoSection(line, btn) {
  document.querySelectorAll('#secbar button').forEach(b => b.classList.remove('on'));
  if (btn) btn.classList.add('on');
  const rows = document.getElementById('code').children;
  if (rows[line - 1]) rows[line - 1].scrollIntoView({ block: 'center' });
  if (!ELEM.length || !linkOK) return;
  let best = ELEM.find(x => x.line >= line);
  if (!best) {
    ELEM.forEach(x => { if (x.line <= line && line <= x.end && (!best || (x.end - x.line) <= (best.end - best.line))) best = x; });
  }
  if (!best) return;
  const all = iframeEls();
  const el = all && all[ELEM.indexOf(best)];
  if (!el) return;
  markInFrame(el);
  el.scrollIntoView({ block: 'start', inline: 'center' });
  document.getElementById('findinfo').textContent = '板块 → 第 ' + line + ' 行 <' + best.tag + '>';
}

const sp = document.getElementById('sp');
sp.onmousedown = e => {
  const right = document.querySelector('.right'), startX = e.clientX, startW = right.offsetWidth;
  const mv = ev => { right.style.width = Math.max(220, Math.min(innerWidth-320, startW - (ev.clientX-startX))) + 'px'; fit(); };
  const up = () => { document.removeEventListener('mousemove', mv); document.removeEventListener('mouseup', up); };
  document.addEventListener('mousemove', mv); document.addEventListener('mouseup', up);
  e.preventDefault();
};
</script>
</body></html>"""


def list_text_files(root):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith('.') and d not in ("node_modules", "__pycache__", "build", "dist")]
        for fn in filenames:
            if os.path.splitext(fn)[1].lower() in TEXT_EXT:
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, root).replace("\\", "/")
                out.append((rel, os.stat(full).st_mtime))
    out.sort(key=lambda x: x[0])
    return out


def safe_join(root, rel):
    rel = unquote(rel).replace("\\", "/").lstrip("/")
    full = os.path.abspath(os.path.join(root, rel))
    if os.path.commonpath([full, os.path.abspath(root)]) != os.path.abspath(root):
        return None
    return full


def newest(root, files):
    best, best_m = None, 0.0
    for rel, m in files:
        if m > best_m:
            best, best_m = rel, m
    return best, best_m


def pick_current(files):
    """优先选可预览的 HTML（最新的那个）；没有 HTML 才退回最新文本文件。

    否则项目里只要有 00_环境.md 且它比页面新，预览区就会去渲染 markdown。
    """
    pages = [(rel, m) for rel, m in files
             if os.path.splitext(rel)[1].lower() in (".html", ".htm")]
    if pages:
        return newest(None, pages)
    return newest(None, files)


def history_dir(full):
    d = os.path.join(os.path.dirname(full), ".history")
    os.makedirs(d, exist_ok=True)
    return d


def backup(full):
    """写之前先备份；只保留最近 30 份。"""
    d = history_dir(full)
    stamp = time.strftime("%Y%m%d_%H%M%S") + "_%03d" % int((time.time() * 1000) % 1000)
    dst = os.path.join(d, os.path.basename(full) + "." + stamp + ".bak")
    with open(full, "rb") as src, open(dst, "wb") as out:
        out.write(src.read())
    olds = sorted([os.path.join(d, n) for n in os.listdir(d)
                   if n.startswith(os.path.basename(full) + ".") and n.endswith(".bak")],
                  key=os.path.getmtime)
    for p in olds[:-30]:
        try:
            os.remove(p)
        except OSError:
            pass
    return dst


def latest_backup(full):
    d = history_dir(full)
    cands = [os.path.join(d, n) for n in os.listdir(d)
             if n.startswith(os.path.basename(full) + ".") and n.endswith(".bak")]
    return max(cands, key=os.path.getmtime) if cands else None


def candidate_dir(full):
    d = os.path.join(history_dir(full), "candidates")
    os.makedirs(d, exist_ok=True)
    return d


def log_edit(full, old_text, new_text, action):
    """每次保存/撤销追加一条操作日志（<root>\\.history\\edits.log，一行一个 JSON）。失败不影响保存。"""
    try:
        root = CFG.get("root") or os.path.dirname(full)
        d = os.path.join(root, ".history")
        os.makedirs(d, exist_ok=True)
        a = (old_text or "").split("\n")
        b = (new_text or "").split("\n")
        sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
        add = dele = 0
        first = None
        hunks = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                continue
            if first is None:
                first = i1 + 1
            if tag in ("replace", "delete"):
                dele += i2 - i1
            if tag in ("replace", "insert"):
                add += j2 - j1
            if len(hunks) < 12:
                hunks.append({
                    "line": i1 + 1,
                    "old": [ln.strip()[:160] for ln in a[i1:i2]][:4],
                    "new": [ln.strip()[:160] for ln in b[j1:j2]][:4],
                })
        if len(hunks) >= 12:
            hunks.append({"line": None, "old": [], "new": []})
        rec = {
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "action": action,
            "file": os.path.relpath(full, root).replace("\\", "/"),
            "add": add,
            "del": dele,
            "first_line": first,
            "hash_before": hashlib.sha256((old_text or "").encode("utf-8")).hexdigest()[:16],
            "hash_after": hashlib.sha256((new_text or "").encode("utf-8")).hexdigest()[:16],
            "size": len((new_text or "").encode("utf-8")),
            "hunks": hunks,
        }
        with open(os.path.join(d, "edits.log"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def tag_balance_error(text):
    """粗检标签配平；返回错误描述，没问题返回空串。"""
    stack = []
    for m in re.finditer(r"<!--.*?-->|<\s*(/?)\s*([a-zA-Z][\w:-]*)([^>]*)>", text, re.S):
        if m.group(0).startswith("<!--"):
            continue
        closing, tag = bool(m.group(1)), m.group(2).lower()
        self_close = m.group(3).rstrip().endswith("/") or tag in VOID_PY
        if not closing:
            if not self_close:
                stack.append(tag)
        else:
            if stack and stack[-1] == tag:
                stack.pop()
            else:
                line = text[:m.start()].count("\n") + 1
                return "第 %d 行：</%s> 没有对应的开标签" % (line, tag)
    if stack:
        pos = text.rfind("<" + stack[-1])
        line = text[:pos].count("\n") + 1 if pos > 0 else 0
        return "有标签没闭合（%s），约在第 %d 行" % ("、".join(stack[-3:]), line)
    return ""


def _block_bodies(text, tag):
    pat = r"<%s\b[^>]*>(.*?)</%s\s*>" % (tag, tag)
    return [m.group(1) for m in re.finditer(pat, text, re.I | re.S)]


def _mask_block_bodies(text):
    text = re.sub(r"(<script\b[^>]*>).*?(</script\s*>)", r"\1\2", text, flags=re.I | re.S)
    return re.sub(r"(<style\b[^>]*>).*?(</style\s*>)", r"\1\2", text, flags=re.I | re.S)


def _parse_attrs(raw):
    attrs = {}
    duplicates = set()
    pat = re.compile(
        r"""([^\s=/>]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?""",
        re.S,
    )
    for m in pat.finditer(raw or ""):
        name = m.group(1).lower()
        if name == "/":
            continue
        value = next((x for x in m.groups()[1:] if x is not None), "")
        if name in attrs:
            duplicates.add(name)
        attrs[name] = value
    return attrs, duplicates


def _tag_tokens(text):
    text = _mask_block_bodies(text)
    pat = re.compile(
        r"<!--.*?-->|<!doctype[^>]*>|<\s*(/?)\s*([a-zA-Z][\w:-]*)([^>]*)>",
        re.I | re.S,
    )
    out = []
    for m in pat.finditer(text):
        if m.group(0).startswith("<!--") or m.group(0).lower().startswith("<!doctype"):
            continue
        closing = bool(m.group(1))
        tag = m.group(2).lower()
        if closing:
            out.append(("close", tag, None, set()))
        else:
            attrs, duplicates = _parse_attrs(m.group(3))
            out.append(("open", tag, attrs, duplicates))
    return out


def _parse_inline_style(value):
    props = {}
    for part in (value or "").split(";"):
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            return None, "样式声明格式无效：%s" % part[:80]
        name, val = part.split(":", 1)
        name = name.strip().lower()
        val = val.strip()
        if not name or name.startswith("--"):
            return None, "不允许修改设计令牌或空样式属性"
        if name in props:
            return None, "样式属性重复：%s" % name
        props[name] = val
    return props, ""


def _find_css_close(text, start):
    depth = 1
    quote = None
    i = start + 1
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == quote and text[i - 1] != "\\":
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _css_rules(css, prefix=""):
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    out = []
    i = 0
    while i < len(css):
        while i < len(css) and css[i].isspace():
            i += 1
        if i >= len(css):
            break
        start = i
        quote = None
        while i < len(css):
            ch = css[i]
            if quote:
                if ch == quote and css[i - 1] != "\\":
                    quote = None
            elif ch in ("'", '"'):
                quote = ch
            elif ch in "{;":
                break
            i += 1
        prelude = re.sub(r"\s+", " ", css[start:i]).strip()
        if i >= len(css):
            break
        if css[i] == ";":
            out.append((prefix + "@" + prelude, None))
            i += 1
            continue
        end = _find_css_close(css, i)
        if end < 0:
            return None
        body = css[i + 1:end]
        if prelude.startswith("@"):
            nested = _css_rules(body, prefix + prelude + " > ")
            if nested is None:
                return None
            if nested:
                out.extend(nested)
            else:
                out.append((prefix + prelude, body.strip()))
        else:
            out.append((prefix + prelude, body.strip()))
        i = end + 1
    return out


def _selector_match_count(tokens, selector):
    if selector.startswith("#") and re.fullmatch(r"#[A-Za-z_][\w:-]*", selector):
        name = selector[1:]
        return sum(1 for t in tokens if t[0] == "open" and t[2].get("id") == name)
    if selector.startswith(".") and re.fullmatch(r"\.[A-Za-z_][\w:-]*", selector):
        name = selector[1:]
        return sum(1 for t in tokens if t[0] == "open"
                   and name in (t[2].get("class") or "").split())
    return -1


def _safe_css_block_change(old_html, old_css, new_css):
    old_rules = _css_rules(old_css)
    new_rules = _css_rules(new_css)
    if old_rules is None or new_rules is None:
        return False, "样式规则无法安全解析"
    if [x[0] for x in old_rules] != [x[0] for x in new_rules]:
        return False, "样式选择器、@media/断点或规则结构发生变化"
    tokens = _tag_tokens(old_html)
    for (selector, old_body), (_, new_body) in zip(old_rules, new_rules):
        if old_body == new_body:
            continue
        if selector.startswith("@") or " > @" in selector:
            return False, "断点或 at-rule 内的样式必须走 A 线：%s" % selector
        if _selector_match_count(tokens, selector) != 1:
            return False, "共享或无法确认唯一的样式选择器必须走 A 线：%s" % selector
        ok, why = _safe_inline_style_change(old_body or "", new_body or "")
        if not ok:
            return False, "样式规则 %s：%s" % (selector, why)
    return True, ""


def _safe_inline_style_change(old_value, new_value):
    old_map, old_err = _parse_inline_style(old_value)
    new_map, new_err = _parse_inline_style(new_value)
    if old_map is None or new_map is None:
        return False, old_err or new_err
    for name in sorted(set(old_map) | set(new_map)):
        if old_map.get(name) == new_map.get(name):
            continue
        if name not in SAFE_STYLE_PROPS:
            return False, "内联样式属性不允许：%s" % name
        value = (new_map.get(name) or old_map.get(name) or "").lower()
        if any(token in value for token in ("url(", "var(", "expression(", "javascript:")):
            return False, "内联样式值包含不允许的内容：%s" % name
    return True, ""


def safe_edit_reasons(full, old_text, new_text):
    """Return human-readable reasons why a safe-mode save is not allowed."""
    reasons = []
    ext = os.path.splitext(full)[1].lower()
    if os.path.basename(full).lower() == "00_环境.md":
        return []
    if ext not in (".html", ".htm", ".vue"):
        return ["安全编辑只允许 HTML/Vue 页面中的文案和局部内联样式；当前文件类型为 %s" % (ext or "未知")]

    old_scripts = _block_bodies(old_text, "script")
    new_scripts = _block_bodies(new_text, "script")
    if old_scripts != new_scripts:
        reasons.append("脚本逻辑发生变化；脚本、存储键和事件必须走 A 线")

    old_styles = _block_bodies(old_text, "style")
    new_styles = _block_bodies(new_text, "style")
    if old_styles != new_styles:
        if len(old_styles) != len(new_styles):
            reasons.append("样式块数量发生变化；新增/删除样式区必须走 A 线")
        else:
            for old_css, new_css in zip(old_styles, new_styles):
                if old_css == new_css:
                    continue
                ok, why = _safe_css_block_change(old_text, old_css, new_css)
                if not ok:
                    reasons.append(why)

    old_tokens = _tag_tokens(old_text)
    new_tokens = _tag_tokens(new_text)
    if len(old_tokens) != len(new_tokens) or any(
        old_tokens[i][0] != new_tokens[i][0] or old_tokens[i][1] != new_tokens[i][1]
        for i in range(min(len(old_tokens), len(new_tokens)))
    ):
        reasons.append("DOM 标签、层级或表单结构发生变化")
        return list(dict.fromkeys(reasons))

    for old_token, new_token in zip(old_tokens, new_tokens):
        if old_token[0] == "close":
            continue
        old_attrs, old_dups = old_token[2], old_token[3]
        new_attrs, new_dups = new_token[2], new_token[3]
        if old_dups or new_dups:
            reasons.append("标签 %s 存在重复属性" % old_token[1])
        for name in sorted(set(old_attrs) | set(new_attrs)):
            if name == "style":
                continue
            if old_attrs.get(name) != new_attrs.get(name):
                if name.startswith("data-"):
                    reasons.append("数据属性发生变化：%s" % name)
                elif name == "class" or name == "id":
                    reasons.append("class/id 语义发生变化：%s" % name)
                elif name.startswith("on"):
                    reasons.append("内联事件属性发生变化：%s" % name)
                else:
                    reasons.append("属性发生变化：%s" % name)
        if old_attrs.get("style", "") != new_attrs.get("style", ""):
            ok, why = _safe_inline_style_change(old_attrs.get("style", ""), new_attrs.get("style", ""))
            if not ok:
                reasons.append(why)

    return list(dict.fromkeys(reasons))


def write_candidate_patch(full, old_text, new_text, reasons):
    d = candidate_dir(full)
    stamp = time.strftime("%Y%m%d_%H%M%S") + "_%03d" % int((time.time() * 1000) % 1000)
    base = os.path.basename(full) + "." + stamp + ".candidate.patch"
    path = os.path.join(d, base)
    n = 1
    while os.path.exists(path):
        path = os.path.join(d, os.path.basename(full) + "." + stamp + "_%d.candidate.patch" % n)
        n += 1
    header = ["# UI 安全编辑候选补丁", "# 原因："] + ["# - " + x for x in reasons] + [""]
    diff = difflib.unified_diff(
        old_text.splitlines(True),
        new_text.splitlines(True),
        fromfile=os.path.basename(full) + "（磁盘）",
        tofile=os.path.basename(full) + "（候选）",
    )
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write("\n".join(header))
        fh.writelines(diff)
    log_edit(full, old_text, new_text, "候选补丁")
    return path


def locked_style_state(root):
    """Return (style name, locked). Missing style means未选择; missing lock defaults false."""
    path = os.path.join(root, "00_环境.md")
    name = ""
    locked = False
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = re.match(r"^\s*风格\s*[：:]\s*(.*?)\s*$", line)
                if m and not name:
                    cand = m.group(1).strip()
                    # 占位符/空值一律视为"未选择"（S-1 模板会留一行空的「风格：」）
                    if cand and "____" not in cand and "选型" not in cand and "复制过来" not in cand:
                        name = cand
                m = re.match(r"^\s*风格锁定\s*[：:]\s*(.*?)\s*$", line)
                if m:
                    value = m.group(1).strip().lower()
                    locked = bool(re.match(r"^(是|已锁定|true|yes|1)(?:$|\W)", value))
    except OSError:
        pass
    return name, locked


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, code, ctype, body):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.end_headers()
        self.wfile.write(body)

    def _stat_payload(self):
        if CFG["mode"] == "file":
            p = CFG["target"]
            m = os.stat(p).st_mtime if os.path.exists(p) else 0
            style_name, style_locked = locked_style_state(os.path.dirname(p))
            return {"mode": "file", "path": p, "root": "", "url": "", "files": [],
                    "current": os.path.basename(p), "mtime": int(m * 1000),
                    "safe_ui": CFG["safe_ui"],
                    "style_name": style_name, "style_locked": style_locked}
        files = list_text_files(CFG["root"])
        cur, m = pick_current(files)
        style_name, style_locked = locked_style_state(CFG["root"])
        return {"mode": "url" if CFG["url"] else "dir", "path": CFG["root"], "root": CFG["root"],
                "url": CFG["url"], "files": [f for f, _ in files], "current": cur,
                "mtime": int(m * 1000), "safe_ui": CFG["safe_ui"],
                "style_name": style_name, "style_locked": style_locked}

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path not in ("/save", "/undo"):
            return self._send(404, "application/json; charset=utf-8", json.dumps({"ok": False, "error": "not found"}))
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            return self._send(400, "application/json; charset=utf-8", json.dumps({"ok": False, "error": "请求解析失败"}))

        if CFG["mode"] == "file":
            full = CFG["target"]
        else:
            full = safe_join(CFG["root"], body.get("f") or "")
        if not full:
            return self._send(400, "application/json; charset=utf-8", json.dumps({"ok": False, "error": "路径非法"}))
        if os.path.splitext(full)[1].lower() not in TEXT_EXT:
            return self._send(400, "application/json; charset=utf-8", json.dumps({"ok": False, "error": "不允许写该类型文件"}))

        # ---- 撤销上一次保存 ----
        if parsed.path == "/undo":
            src = latest_backup(full)
            if not src:
                return self._send(404, "application/json; charset=utf-8",
                                  json.dumps({"ok": False, "error": "没有可回滚的历史版本"}, ensure_ascii=False))
            try:
                with open(src, "rb") as fh:
                    data = fh.read()
                old_text = ""
                if os.path.exists(full):
                    with open(full, "r", encoding="utf-8", errors="replace") as fh:
                        old_text = fh.read()
                with open(full, "wb") as fh:
                    fh.write(data)
                log_edit(full, old_text, data.decode("utf-8", "replace"), "撤销")
                st = os.stat(full)
                return self._send(200, "application/json; charset=utf-8",
                                  json.dumps({"ok": True, "from": os.path.basename(src),
                                              "mtime": int(st.st_mtime * 1000)}, ensure_ascii=False))
            except Exception as e:
                return self._send(500, "application/json; charset=utf-8",
                                  json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))

        # ---- 保存 ----
        content = body.get("content")
        if content is None:
            return self._send(400, "application/json; charset=utf-8", json.dumps({"ok": False, "error": "缺少 content"}))
        old_text = ""
        if os.path.exists(full):
            with open(full, "r", encoding="utf-8", errors="replace") as fh:
                old_text = fh.read()
        if CFG["safe_ui"]:
            reasons = safe_edit_reasons(full, old_text, content)
            if reasons:
                patch_path = ""
                try:
                    patch_path = write_candidate_patch(full, old_text, content, reasons)
                except Exception as exc:
                    reasons.append("候选补丁写入失败：%s" % exc)
                return self._send(200, "application/json; charset=utf-8",
                                  json.dumps({"ok": False, "blocked": True,
                                              "error": "UI 安全编辑已拦截",
                                              "reasons": reasons, "patch": patch_path},
                                             ensure_ascii=False))
        if full.lower().endswith((".html", ".htm", ".vue")):
            err = tag_balance_error(content)
            if err:
                return self._send(200, "application/json; charset=utf-8",
                                  json.dumps({"ok": False, "error": "结构检查没通过，已拒绝保存：" + err,
                                              "hint": "标签不配平会导致整页塌掉。改回去再存，或点「撤销上次保存」。"},
                                             ensure_ascii=False))
        try:
            if os.path.exists(full):
                backup(full)
            os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
            with open(full, "w", encoding="utf-8", newline="") as fh:
                fh.write(content)
            log_edit(full, old_text, content, "保存")
            st = os.stat(full)
            return self._send(200, "application/json; charset=utf-8",
                              json.dumps({"ok": True, "mtime": int(st.st_mtime * 1000)}, ensure_ascii=False))
        except Exception as e:
            return self._send(500, "application/json; charset=utf-8",
                              json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/":
            return self._send(200, "text/html; charset=utf-8", VIEWER)
        if path == "/stat":
            return self._send(200, "application/json; charset=utf-8", json.dumps(self._stat_payload(), ensure_ascii=False))
        if path == "/source":
            qs = parsed.query
            f = ""
            for part in qs.split("&"):
                if part.startswith("f="):
                    f = part[2:]
            if CFG["mode"] == "file":
                full = CFG["target"]
            else:
                full = safe_join(CFG["root"], f)
            if not full or not os.path.exists(full):
                return self._send(404, "text/plain; charset=utf-8", "文件不存在")
            with open(full, "r", encoding="utf-8", errors="replace") as fh:
                return self._send(200, "text/plain; charset=utf-8", fh.read())
        if path.startswith("/site/"):
            rel = path[len("/site/"):]
            full = safe_join(CFG["root"], rel)
            if not full or not os.path.exists(full) or not os.path.isfile(full):
                return self._send(404, "text/plain; charset=utf-8", "not found")
            ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
                ctype += "; charset=utf-8"
            with open(full, "rb") as fh:
                return self._send(200, ctype, fh.read())
        if path == "/target":
            if CFG["mode"] != "file" or not os.path.exists(CFG["target"]):
                return self._send(404, "text/plain; charset=utf-8", "not found")
            with open(CFG["target"], "r", encoding="utf-8", errors="replace") as fh:
                return self._send(200, "text/html; charset=utf-8", fh.read())
        self._send(404, "text/plain; charset=utf-8", "not found")


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("target", nargs="?", default="", help="单文件模式下的 html 路径")
    ap.add_argument("portpos", nargs="?", default="", help="端口（位置参数，兼容旧用法）")
    ap.add_argument("--dir", default="", help="目录模式：监视该目录")
    ap.add_argument("--url", default="", help="左侧加载真实地址（如 http://127.0.0.1:8000/xxx.php）")
    ap.add_argument("--port", default="", help="端口")
    ap.add_argument("--unsafe", action="store_true", help="关闭 UI 安全编辑，允许整文件编辑（仅开发用）")
    a = ap.parse_args()

    port = int(a.port or a.portpos or 8790)
    CFG["port"] = port
    CFG["safe_ui"] = not a.unsafe
    if a.dir:
        root = os.path.abspath(a.dir)
        if not os.path.isdir(root):
            print("目录不存在:", root); sys.exit(1)
        CFG.update(mode="dir", root=root, url=a.url.strip())
    else:
        # 没给 --dir 也没给 --target：默认监视当前目录（不写死任何个人路径）
        if a.target:
            target = os.path.abspath(a.target)
            CFG.update(mode="file", target=target)
        else:
            root = os.getcwd()
            print("未指定 --dir / --target，默认监视当前目录:", root)
            CFG.update(mode="dir", root=root, url=a.url.strip())

    url = "http://127.0.0.1:%d/" % port
    print("UI 调试台:", url)
    print("模式:", "目录 " + CFG["root"] if CFG["mode"] != "file" else "单文件 " + CFG["target"])
    print("编辑权限:", "UI 安全编辑（越界转候选补丁）" if CFG["safe_ui"] else "开发模式（不拦截）")
    if CFG["url"]:
        print("左侧地址:", CFG["url"], "（跨源则双向联动自动关闭）")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# 服务器资产台账：扫描容器与端口 -> 比对 -> 记档/发邮件 -> 生成台账页
# 只记录，不做任何控制动作；人工备注文件只读。
import json, os, subprocess, socket, smtplib, ssl, time, re, sys
from email.mime.text import MIMEText
from email.header import Header

BASE = "/root/asset-ledger"
WWW = f"{BASE}/www"
DATA = f"{BASE}/www/data"
STATE = f"{BASE}/state.json"
HIST = f"{BASE}/history.json"
NOTES = f"{BASE}/notes.json"
PORTLIST = f"{DATA}/ports.json"
MAIL = "/root/.dsh/mail.json"

def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default

def save(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)

def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout

# ---------- 日记与榜单（只读公开版；私密日记 whale-diary-private.md 永不读取） ----------
try:
    import markdown as _mdlib
    _MD = _mdlib.Markdown(extensions=["tables"])
    def render_md(text):
        _MD.reset()
        return _MD.convert(text)
except Exception:
    def render_md(text):
        return "<p>" + text.replace("&", "&amp;").replace("<", "&lt;")[:800] + "…</p>"

DIARY_SRC = "/root/.dsh/whale-diary.md"
RANK_GLOB = "/root/notes/trending/daily/*/*.md"
DS_ENV = "/root/.dsh/.env"
DS_HIST = f"{BASE}/ds-balance.jsonl"

# 日记/榜单子页样式（与台账同风格）
PAGE_CSS = """*{box-sizing:border-box;margin:0;padding:0}
:root{--ink:#26323e;--soft:#6b7a89;--line:#e5eaf0;--teal:#0d9488;--blue:#2563eb;--paper:#fff;--bg:#eef2f6}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
  background:var(--bg);color:var(--ink);line-height:1.85}
.pagebar{position:sticky;top:0;z-index:50;background:rgba(15,23,42,.94);backdrop-filter:blur(8px);
  color:#fff;padding:10px 18px}
.pbin{max-width:1000px;margin:0 auto;display:flex;align-items:center;gap:16px}
.pagebar a{color:rgba(255,255,255,.75);text-decoration:none;font-size:14px;padding:3px 10px;
  border-radius:999px;transition:background .15s,color .15s,transform .12s}
.pagebar a:active{transform:scale(.94)}
.pagebar a:hover{color:#fff;background:rgba(255,255,255,.12)}
.pagebar a.on{background:#fff;color:#0f172a;font-weight:700}
.pagebar b{margin-left:auto;font-size:14.5px;font-weight:600}
.pb-brand{font-weight:700;font-size:15px;letter-spacing:.3px}
.pb-cur{display:none}
.subhero{background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 55%,#155e63 100%);
  color:#fff;padding:26px 18px 24px;display:flex;align-items:center;min-height:120px}
.subhero-in{max-width:1000px;margin:0 auto;width:100%}
.sh-t{font-size:21px;font-weight:700;letter-spacing:.4px}
.sh-s{color:rgba(255,255,255,.75);font-size:13.5px;margin-top:6px}
.entry-meta{font-size:12.5px;color:var(--soft);margin-top:3px}
.artnav{display:flex;justify-content:space-between;gap:12px;margin-top:20px;padding-top:14px;
  border-top:1px dashed var(--line);font-size:13.5px}
.artnav a{color:var(--blue);text-decoration:none}
.artnav a:hover{text-decoration:underline}
.about-txt{font-size:13.5px;color:var(--soft);line-height:1.75}
.trend{margin-top:12px;font-size:13.5px;color:var(--ink);background:var(--teal-bg);
  border-radius:10px;padding:9px 12px}
body{animation:pgfadein .3s ease}
@keyframes pgfadein{from{opacity:0}to{opacity:1}}
.cal-top{display:none}
@media(max-width:680px){
  .pbin{gap:7px;flex-wrap:wrap}
  .pagebar{padding:9px 14px}
  .pb-brand{display:none}
  .pbin a{display:none}
  .pbin a.pb-back{display:inline-block;font-size:19px;font-weight:700;
    padding:2px 12px 2px 4px;line-height:1.4}
  .pb-bt{display:none}
  .pb-cur{display:inline;font-size:14.5px;font-weight:700;color:#fff}
  .artnav{flex-direction:column;gap:8px}
  .artnav a{display:block;text-align:right}
  .cal-top{display:block;margin-bottom:18px}
  .side .panel.cal{display:none}
  .subhero{padding:20px 16px 18px;min-height:134px}
}
.wrap2{max-width:1000px;margin:22px auto;padding:0 16px 60px}
.panel{background:var(--paper);border:1px solid var(--line);border-radius:16px;
  box-shadow:0 1px 4px rgba(15,23,42,.05);padding:20px 22px;margin-bottom:18px}
h2.sec{font-size:17px;margin:4px 0 14px}
.grid2{display:grid;grid-template-columns:1fr;gap:20px;align-items:start}
.grid2>*{min-width:0}
@media(min-width:960px){.grid2{grid-template-columns:1fr 280px}}
.article{font-size:15.5px;max-width:760px}
.article table{table-layout:fixed}
.article td{word-break:break-word}
.article+.article{margin-top:34px;padding-top:26px;border-top:1px dashed var(--line)}
.article h1{font-size:21px;margin:4px 0 10px}
.article h2{font-size:17px;margin:22px 0 10px;border-left:4px solid var(--teal);padding-left:10px}
.article p{margin:10px 0;color:#37444f}
.article strong{color:#111827}
.article table{width:100%;border-collapse:collapse;font-size:13.5px;margin:12px 0}
.article th{background:#f1f5f9;color:var(--soft);font-size:12.5px;padding:7px 9px;text-align:left}
.article td{padding:8px 9px;border-bottom:1px solid #f1f5f9;vertical-align:top}
@media(max-width:680px){.article table{display:block;overflow-x:auto;-webkit-overflow-scrolling:touch}.article td,.article th{min-width:5.5em}}
.article a{color:var(--blue)}
.article ul{padding-left:22px;margin:10px 0}
.article li{margin:4px 0}
.ddate{color:var(--teal);font-size:13px;font-weight:700;letter-spacing:1px}
.entries{display:grid;gap:10px}
.entry{display:block;text-decoration:none;background:var(--paper);border:1px solid var(--line);
  border-radius:14px;padding:14px 18px;transition:border-color .15s,box-shadow .15s}
.entry:hover{border-color:var(--teal);box-shadow:0 2px 10px rgba(13,148,136,.08)}
.entry .d{font-size:12.5px;color:var(--teal);font-weight:700;letter-spacing:1px}
.entry .t{font-size:15.5px;font-weight:700;margin:2px 0 5px}
.entry .x{font-size:13.5px;color:var(--soft);display:-webkit-box;-webkit-line-clamp:2;
  -webkit-box-orient:vertical;overflow:hidden}
.repo{display:block;text-decoration:none;padding:11px 4px;border-bottom:1px solid #f1f5f9}
.repo:last-child{border-bottom:none}
.repo .r1{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
.repo .nm{font-weight:700;font-size:15px}
.repo .nm:hover{color:var(--blue)}
.repo .stars{font-size:12px;color:#b45309;background:#fffbeb;border-radius:999px;padding:1px 9px;font-weight:600}
.repo .delta{font-size:12px;color:var(--teal);background:#ecfdf5;border-radius:999px;padding:1px 9px;font-weight:600}
.repo .sm{font-size:13.5px;color:var(--soft);margin-top:3px}
details.sec-blk{background:var(--paper);border:1px solid var(--line);border-radius:14px;
  padding:12px 18px;margin-bottom:12px}
details.sec-blk summary{cursor:pointer;font-weight:700;font-size:15px;list-style:none}
details.sec-blk summary::before{content:"▸";color:var(--soft);margin-right:8px;display:inline-block;
  transition:transform .15s}
details.sec-blk[open] summary::before{transform:rotate(90deg)}
.rankbar{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}
.rankbar a{text-decoration:none;font-size:13px;color:var(--soft);background:var(--paper);
  border:1px solid var(--line);padding:4px 13px;border-radius:999px}
.rankbar a.on,.rankbar a:hover{color:#fff;background:var(--blue);border-color:var(--blue)}
.empty{color:var(--soft);font-size:14px;padding:16px 0}
.cal table{width:100%;border-collapse:collapse;table-layout:fixed}
.cal th{font-size:11.5px;color:var(--soft);font-weight:600;padding:5px 0;text-align:center}
.cal td{text-align:center;font-size:13px;padding:2px 0}
.cal .day{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:50%;color:#37444f}
.cal span.day.dim{color:#c3ccd6}
.cal a.day{background:var(--teal);color:#fff;font-weight:700;text-decoration:none}
.cal a.day:hover{filter:brightness(1.08);transform:scale(1.08)}
.cal .cal-cap{font-size:13.5px;font-weight:700;margin-bottom:6px;color:#111827}
.cal .cal-legend{font-size:12px;color:var(--soft);margin-top:7px}
.cal .cal-legend b{display:inline-flex;width:10px;height:10px;border-radius:50%;background:var(--teal);margin-right:5px;vertical-align:middle}
@media(max-width:680px){.panel{padding:16px 15px}.wrap2{padding:16px 14px 50px}}
a,button{-webkit-tap-highlight-color:transparent}
.totop{position:fixed;right:18px;bottom:26px;width:42px;height:42px;border-radius:50%;
  background:rgba(15,23,42,.85);color:#fff;border:none;cursor:pointer;z-index:60;
  font-size:17px;box-shadow:0 3px 12px rgba(15,23,42,.28);display:none;
  align-items:center;justify-content:center;opacity:0;transition:opacity .25s;
  -webkit-tap-highlight-color:transparent;outline:none;-webkit-appearance:none;appearance:none;touch-action:manipulation}
.totop.show{display:flex;opacity:1}
.totop:focus{outline:none}
.totop:active{transform:scale(.92);outline:none}
@media(max-width:680px){.totop{right:14px;bottom:20px;width:46px;height:46px}}
.usg-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin:6px 0 14px}
.usg-cell{background:#f8fafc;border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.usg-cell .k{font-size:12px;color:var(--soft)}
.usg-cell .v{font-size:17px;font-weight:700;margin-top:2px;font-variant-numeric:tabular-nums}
.usg-hero{grid-column:1/-1;background:linear-gradient(135deg,#ecfdf5,#eff6ff);border:1px solid #a7f3d0;
  border-radius:12px;padding:14px 16px}
.usg-hero .k{font-size:12.5px;color:#047857;font-weight:600;letter-spacing:.2px}
.usg-hero .v{font-size:30px;font-weight:800;color:#065f46;margin-top:3px;font-variant-numeric:tabular-nums}
.usg-row{padding:8px 0;border-bottom:1px solid #f1f5f9}
.usg-row:last-child{border-bottom:none}
.usg-r1{display:flex;justify-content:space-between;align-items:baseline;gap:10px;flex-wrap:wrap}
.usg-nm{font-size:13.5px;font-weight:600}
.usg-meta{font-size:12.5px;color:var(--soft)}
.usg-bar{height:8px;border-radius:999px;background:#eef2f6;overflow:hidden;margin-top:6px}
.usg-fill{height:100%;border-radius:999px}
.usg-dot{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:6px;vertical-align:baseline}
.usg-cap{font-size:12px;color:var(--soft);margin-top:9px}
.pburger{display:none}
.mmask,.mdrawer{display:none}
@media(max-width:680px){
  .pburger{display:flex;flex-direction:column;justify-content:center;gap:4px;background:none;
    border:0;padding:8px 2px 8px 10px;cursor:pointer}
  .pburger span{display:block;width:20px;height:2px;border-radius:2px;background:#fff}
  .pburger:active{opacity:.7}
  .side .panel.toc,.side .panel.recent{display:none}
  .mdrawer{display:flex;flex-direction:column;position:fixed;top:0;left:0;bottom:0;width:64%;max-width:232px;z-index:100;
    background:rgba(255,255,255,.78);backdrop-filter:blur(32px) saturate(1.5);-webkit-backdrop-filter:blur(32px) saturate(1.5);box-shadow:2px 0 18px rgba(15,23,42,.28);transform:translateX(-106%);
    transition:transform .5s cubic-bezier(.16,1,.3,1) .2s;overflow-y:auto;overscroll-behavior:contain;border-radius:0 18px 18px 0}
  body.drawer-open .mdrawer{transform:none;transition:transform .9s cubic-bezier(.16,1,.3,1);transition-delay:0s}
  .mmask{display:block;position:fixed;inset:0;background:rgba(15,23,42,.45);z-index:90;
    opacity:0;pointer-events:none;transition:opacity .45s}
  body.drawer-open .mmask{opacity:1;pointer-events:auto}
  body.drawer-open{overflow:hidden;overscroll-behavior:contain}
  .md-hero{background:linear-gradient(135deg,#0f172a,#155e63);color:#fff;padding:24px 20px 18px}
  .md-t{font-size:17.5px;font-weight:700}
  .md-sub{font-size:12.5px;color:rgba(255,255,255,.72);margin-top:5px}
  .md-nav{padding:8px 0}
  .md-nav a{display:flex;align-items:center;gap:10px;padding:13px 20px;color:var(--ink);
    text-decoration:none;font-size:15px;font-weight:600;border-bottom:1px solid #eef2f6}
  .md-nav a:last-child{border-bottom:0}
  .md-nav a:active{background:#f1f5f9}
  .md-nav .md-n{margin-left:auto;min-width:22px;height:22px;padding:0 7px;border-radius:999px;background:#f1f5f9;color:var(--soft);font-size:11.5px;font-weight:700;display:flex;align-items:center;justify-content:center;flex:none}
  .md-nav a.cur .md-n,.md-nav a.on .md-n{background:var(--teal);color:#fff}
  html.dark .md-nav .md-n{background:#1a2740;color:#8b98a9}
  html.dark .md-nav a.cur .md-n,html.dark .md-nav a.on .md-n{background:var(--teal);color:#fff}
  .md-nav a{opacity:0;transform:translateX(-26px);transition:opacity .6s ease,transform .75s cubic-bezier(.16,1,.3,1),background .2s}
  body.drawer-open .md-nav a{opacity:1;transform:none}
  .md-nav a:nth-child(1){transition-delay:.10s}
  .md-nav a:nth-child(2){transition-delay:.19s}
  .md-nav a:nth-child(3){transition-delay:.28s}
  .md-nav a:nth-child(4){transition-delay:.37s}
  .md-nav a:nth-child(5){transition-delay:.46s}
  body:not(.drawer-open) .md-nav a:nth-child(1){transition-delay:.20s;transition-duration:.25s}
  body:not(.drawer-open) .md-nav a:nth-child(2){transition-delay:.15s;transition-duration:.25s}
  body:not(.drawer-open) .md-nav a:nth-child(3){transition-delay:.10s;transition-duration:.25s}
  body:not(.drawer-open) .md-nav a:nth-child(4){transition-delay:.05s;transition-duration:.25s}
  body:not(.drawer-open) .md-nav a:nth-child(5){transition-delay:0s;transition-duration:.25s}
  .md-nav a.cur{background:#ecfdf5;color:var(--teal)}
  .md-foot{margin-top:auto;flex:none;padding:14px 16px calc(16px + env(safe-area-inset-bottom,0px))}
  .md-theme{display:flex;align-items:center;justify-content:space-between;gap:10px;width:100%;background:#f1f5f9;border:1px solid #dbe3ec;border-radius:14px;padding:11px 14px;color:var(--ink);font-size:15px;font-weight:600;cursor:pointer;box-shadow:0 1px 3px rgba(15,23,42,.07);-webkit-tap-highlight-color:transparent;outline:none;transition:background .2s}
  .md-theme:active{background:#e6ecf3}
  .md-sw{position:relative;width:48px;height:28px;border-radius:999px;background:#b9c3d0;transition:background .3s;flex:none;box-shadow:inset 0 1px 3px rgba(15,23,42,.18)}
  .md-sw::after{content:"";position:absolute;top:3px;left:3px;width:20px;height:20px;border-radius:50%;background:#fff;box-shadow:0 1px 4px rgba(15,23,42,.3);transition:transform .3s cubic-bezier(.22,1,.36,1)}
  html.dark .md-sw{background:var(--teal)}
  html.dark .md-sw::after{transform:translateX(20px)}
  .md-hero,.md-nav{flex:none}
  html.dark .md-theme{background:#1a2740;border-color:#263552;box-shadow:none}
  html.dark .md-theme:active{background:#22334f}
}
/* ---------- 黑夜模式 ---------- */
.tmoon{position:fixed;left:18px;bottom:26px;width:42px;height:42px;border-radius:50%;
  background:rgba(15,23,42,.85);color:#fff;border:none;cursor:pointer;z-index:60;font-size:17px;
  box-shadow:0 3px 12px rgba(15,23,42,.28);display:flex;align-items:center;justify-content:center;
  -webkit-tap-highlight-color:transparent;outline:none;-webkit-appearance:none;appearance:none;
  touch-action:manipulation;transition:transform .12s}
.tmoon:active{transform:scale(.92)}
.tmoon:focus{outline:none}
@media(max-width:680px){.tmoon{display:none}}
@media(max-width:768px){input,select,textarea{font-size:16px!important}}
html.dark .tmoon{background:rgba(38,50,67,.9)}
html.dark body{background:#0b1220;color:#d7dde6}
html.dark{--ink:#d7dde6;--soft:#8b98a9;--line:#263243;--paper:#111a2b;--bg:#0b1220}
html.dark .panel,html.dark .entry,html.dark details.sec-blk{background:#111a2b;border-color:#263243}
html.dark .entry .t,html.dark .usg-nm,html.dark .usg-cell .v,html.dark .repo .nm{color:#e5ecf5}
html.dark .article p{color:#c3ccd6}
html.dark .article strong,html.dark .article h1,html.dark .article h2,
html.dark .cal .cal-cap{color:#e5ecf5}
html.dark .article th{background:#18233a;color:#8b98a9}
html.dark .article td,html.dark .rep-tbl td,html.dark .dsrow{border-bottom-color:#1a2740}
html.dark .usg-cell{background:#101b2e;border-color:#263243}
html.dark .usg-hero{background:linear-gradient(135deg,#0b241f,#0e1f33);border-color:#155e45}
html.dark .usg-hero .k{color:#34d399}
html.dark .usg-hero .v{color:#a7f3d0}
html.dark .usg-bar{background:#1a2740}
html.dark .quick a{color:#d7dde6;border-color:#263243}
html.dark .rankbar a{background:#111a2b;border-color:#263243}
html.dark .trend{background:#0e2a2b;color:#d7dde6}
html.dark .about-txt,html.dark .empty,html.dark .rep-meta,html.dark .rep-note,html.dark .usg-cap{color:#8b98a9}
"""

# ---------- 测试版：全站搜索 / 日记时间线 / mac 代码窗 / 面包屑 ----------
FS_BOX = ('<form class="fsbox" action="/search.html" method="get"><input id="fs-input" name="q" type="text" placeholder="🔍 搜索文章…" '
          'autocomplete="off" spellcheck="false"></form>')

SEARCH_JS = r'''(function(){
function go(v){var q=(v||"").trim();if(q)location.href="/search.html?q="+encodeURIComponent(q)}
var boxes=Array.prototype.slice.call(document.querySelectorAll(".fsbox"));
boxes.forEach(function(box){var inp=box.querySelector("input");if(!inp)return;
inp.addEventListener("keydown",function(e){if(e.isComposing||e.keyCode===229)return;if(e.key==="Enter"||e.keyCode===13){e.preventDefault();go(inp.value)}});
var btn=box.querySelector(".s-go");if(btn)btn.addEventListener("click",function(){go(inp.value)});});
if(!window.__sDC){window.__sDC=1;document.addEventListener("click",function(e){if(document.body.classList.contains("search-open")){
if(e.target.closest&&!e.target.closest(".s-panel")&&!e.target.closest(".pb-search")&&!e.target.closest(".mt-search"))searchOff()}});}})();'''

SEARCH_BTN = ('<button class="pb-search" type="button" aria-label="搜索" onclick="searchOn()">🔍</button>')

SEARCH_PANEL = ('<div class="s-mask" onclick="searchOff()"></div>'
                '<div class="s-panel" role="dialog" aria-label="搜索">'
                '<form class="fsbox s-fsbox" action="/search.html" method="get"><span class="s-ico" aria-hidden="true">🔍</span>'
                '<input type="text" name="q" placeholder="搜索文章…" '
                'autocomplete="off" spellcheck="false">'
                '<button class="s-go" type="button" aria-label="搜索">🔍</button></form></div>')

SEARCH_SCRIPT = ('function searchOn(){document.body.classList.add("search-open");'
                 'var i=document.querySelector(".s-fsbox input");'
                 'if(i)setTimeout(function(){i.focus()},400)}'
                 'function searchOff(){document.body.classList.remove("search-open")}'
                 'if(!window.__sEsc){window.__sEsc=1;document.addEventListener("keydown",function(e){if(e.key==="Escape")searchOff()})};')

SEARCH_CSS = (
    '/* ---------- 搜索弹出层（全局） ---------- */'
    '.pb-search{display:block;background:none;border:0;color:#fff;font-size:18px;'
    'padding:6px 2px 6px 8px;cursor:pointer;margin-left:auto;-webkit-tap-highlight-color:transparent}'
    '.pb-search:active{opacity:.7}'
    '.s-mask{position:fixed;inset:0;background:rgba(15,23,42,.45);z-index:110;opacity:0;pointer-events:none;transition:opacity .35s}'
    'body.search-open .s-mask{opacity:1;pointer-events:auto}'
    '.s-panel{position:fixed;top:0;left:0;right:0;z-index:120;background:rgba(15,23,42,.96);'
    'backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);padding:11px 14px;display:flex;'
    'align-items:center;gap:8px;transform:translateY(-110%);transition:transform .45s cubic-bezier(.16,1,.3,1)}'
    'body.search-open .s-panel{transform:none}'
    'body.search-open{overflow:hidden;overscroll-behavior:contain}'
    '.s-fsbox{flex:1;position:relative}'
    '.s-ico{position:absolute;left:14px;top:50%;transform:translateY(-50%);font-size:13px;pointer-events:none;z-index:2;opacity:.9}'
    '.s-fsbox input{width:100%!important;max-width:none!important;background:rgba(255,255,255,.14)!important;'
    'border:1px solid rgba(255,255,255,.22)!important;color:#fff!important;border-radius:999px;'
    'padding:9px 38px 9px 38px!important;font-size:14px;outline:none}'
    '.s-fsbox input::placeholder{color:rgba(255,255,255,.55)}'
    '.s-fsbox input:focus{width:100%!important;background:rgba(255,255,255,.2)!important}'
    '.s-go{position:absolute;right:10px;top:50%;transform:translateY(-50%);background:none;border:0;'
    'font-size:15px;cursor:pointer;opacity:.85;padding:4px;-webkit-tap-highlight-color:transparent}'
    '.s-go:active{opacity:.5}'
    '.s-fsbox .fs-drop{left:0;right:0;width:auto;max-height:52vh;overflow-y:auto;overscroll-behavior:contain}'
    '.fs-drop a{align-items:flex-start}'
    '.fs-line{white-space:normal;line-height:1.55;color:var(--ink);flex:1;min-width:0}'
    '.fs-line b{color:var(--teal)}'
    'html.dark .fs-line{color:#d7dde6}'
    '/* ---------- 搜索结果页 ---------- */'
    '.sr-item{display:block;padding:14px 16px;border:1px solid var(--line);border-radius:14px;margin-bottom:12px;'
    'text-decoration:none;color:var(--ink);background:#fff;transition:box-shadow .2s,transform .2s}'
    '.sr-item:active,.sr-item:hover{box-shadow:0 8px 24px rgba(15,23,42,.08);transform:translateY(-1px)}'
    '.sr-top{display:flex;align-items:center;gap:8px;margin-bottom:6px}'
    '.sr-k{font-size:11px;color:#0d9488;background:#ecfdf5;border-radius:999px;padding:1px 8px;font-weight:700}'
    '.sr-date{font-size:11.5px;color:var(--soft)}'
    '.sr-t{font-weight:600;font-size:15px;margin-bottom:4px;line-height:1.5}'
    '.sr-s{color:var(--soft);font-size:13px;line-height:1.6}'
    '.sr-t b,.sr-s b{color:var(--teal)}'
    '.sr-empty{padding:18px 4px;color:var(--soft);font-size:14px}'
    'html.dark .sr-item{background:#111a2b;border-color:#263243;color:#d7dde6}'
    'html.dark .sr-s{color:#8b98a9}'
    'html.dark .sr-k{background:#0e2a2b;color:#5eead4}')

SEARCH_RESULT_JS = r'''(function(){
function esc(s){return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}
function hl(s,q){var lc=s.toLowerCase(),i=lc.indexOf(q);if(i<0)return esc(s);
return esc(s.slice(0,i))+"<b>"+esc(s.slice(i,i+q.length))+"</b>"+esc(s.slice(i+q.length))}
function sentence(b,q){var lc=b.toLowerCase(),j=lc.indexOf(q);if(j<0)return"";
var B="。！？；;!?",s=0,e=b.length,i;
for(i=j-1;i>=0;i--){if(B.indexOf(b.charAt(i))>-1){s=i+1;break}}
for(i=j+q.length;i<b.length;i++){if(B.indexOf(b.charAt(i))>-1){e=i+1;break}}
var t=b.slice(s,e);if(t.length>140){var m=j-s;if(m>70)t="…"+b.slice(s+m-70,s+m+70);else t=t.slice(0,140)}
return t.replace(/\s+/g," ").trim()}
function qparam(){var m=location.search.match(/[?&]q=([^&]*)/);if(!m)return"";
try{return decodeURIComponent(m[1]).trim()}catch(e){return (m[1]||"").trim()}}
var q=qparam(),list=document.getElementById("sr-list"),head=document.getElementById("sr-head");
document.title=q?("搜索: "+q+" · 鱼窝"):"搜索 · 鱼窝";
var inp=document.querySelector(".s-fsbox input");if(inp&&q)inp.value=q;
if(!q){head.innerHTML="🔍 输入关键词开始搜索";
list.innerHTML='<div class="sr-empty">搜全站的日记、榜单、台账与饭票页面。在任意页面右上角放大镜里输入，回车就会来到这里。</div>';return}
head.innerHTML='搜索：'+esc(q)+'（<span id="sr-n">搜索中…</span>）';
fetch("/search-index.json",{cache:"no-store"}).then(function(r){return r.json()}).then(function(IDX){
var ql=q.toLowerCase();
var hits=IDX.filter(function(x){return (x.t||"").toLowerCase().indexOf(ql)>-1||(x.k||"").toLowerCase().indexOf(ql)>-1||(x.b&&x.b.toLowerCase().indexOf(ql)>-1)});
var n=document.getElementById("sr-n");if(n)n.textContent="共 "+hits.length+" 条结果";
if(!hits.length){list.innerHTML='<div class="sr-empty">没有找到与「'+esc(q)+'」相关的内容，换个词试试。</div>';return}
list.innerHTML=hits.map(function(x){
var sent=x.b?sentence(x.b,ql):"";
var dm=(x.u.match(/(\d{4}-\d{2}-\d{2})/)||[""])[0];
return '<a class="sr-item" href="'+x.u+'"><div class="sr-top"><span class="sr-k">'+esc(x.k||"页面")+'</span>'
+(dm?'<span class="sr-date">'+dm+'</span>':'')+'</div>'
+'<div class="sr-t">'+hl(x.t||"",ql)+'</div>'
+(sent?'<div class="sr-s">'+hl(sent,ql)+'</div>':'')+'</a>'}).join("");
}).catch(function(){list.innerHTML='<div class="sr-empty">搜索索引加载失败，请稍后重试。</div>'});
})();'''

CW_JS = r'''(function(){if(!window.__cwDC){window.__cwDC=1;document.addEventListener("click",function(e){
var b=e.target.closest?e.target.closest(".cw-copy"):null;if(!b)return;
var w=b.closest(".codewin");if(!w)return;var t=w.querySelector("pre");
var txt=t?t.innerText:"";
function done(){b.textContent="已复制";setTimeout(function(){b.textContent="复制"},1500)}
if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(txt).then(done,done)}else{done()}});}})();'''

# ---------- 顶栏样式全站唯一：杜绝无刷新切换时顶栏被新页样式重新撑大 ----------
TOPBAR_CSS = (
    '.topbar{position:sticky;top:0;z-index:50;background:rgba(15,23,42,.94);backdrop-filter:blur(10px);'
    '-webkit-backdrop-filter:blur(10px);color:#fff;box-shadow:0 1px 0 rgba(255,255,255,.06)}'
    '.tb-in{max-width:1140px;margin:0 auto;padding:8px 16px;display:flex;align-items:center;'
    'gap:12px;flex-wrap:wrap}'
    '.tb-brand{display:flex;align-items:center;gap:9px;text-decoration:none;color:#fff;flex:none}'
    '.tb-logo{width:32px;height:32px;border-radius:9px;background:linear-gradient(135deg,#1e3a5f,#155e63);'
    'display:flex;align-items:center;justify-content:center;font-size:16px;'
    'box-shadow:inset 0 0 0 1px rgba(255,255,255,.16)}'
    '.tb-name{font-size:15.5px;font-weight:800;letter-spacing:.5px;line-height:1.2}'
    '.tb-name small{display:block;font-size:10.5px;font-weight:500;color:rgba(255,255,255,.6);letter-spacing:.2px}'
    '.tb-nav{display:flex;gap:4px;flex-wrap:wrap;align-items:center}'
    '.tb-nav a{color:rgba(255,255,255,.78);text-decoration:none;font-size:13.5px;padding:5px 11px;'
    'border-radius:999px;transition:background .15s,color .15s,transform .12s}'
    '.tb-nav a:hover{background:rgba(255,255,255,.14);color:#fff}'
    '.tb-nav a:active{transform:scale(.94)}'
    '.tb-nav a.on{background:#fff;color:#0f172a;font-weight:700}'
    '.tb-search{margin-left:auto;flex:none;width:165px}'
    '.tb-ico{position:absolute;left:13px;top:50%;transform:translateY(-50%);font-size:13px;pointer-events:none;z-index:2;opacity:.9;line-height:1}'
    '.fsbox.tb-search input{padding:6px 14px 6px 33px;font-size:13px}'
    '@media(max-width:1080px){.tb-name small{display:none}.tb-in{gap:8px}.tb-search{width:130px}}'
    '@media(max-width:900px){.tb-name{display:none}.tb-nav a{padding:5px 8px;font-size:13px}.tb-search{width:110px}}'
)

# ---------- 全站无刷新切换路由：点导航换正文，顶栏原地不动只挪高亮 ----------
SPA_ROUTER_JS = r'''<script>
(function(){
var PAGES=["/index.html","/diary.html","/rank.html","/balance.html","/ledger.html"];
var HSEL=".topbar,.pagebar,.mtop";
function mk(u){try{return new URL(u,location.href)}catch(e){return null}}
function navPath(u){return (u.pathname==="/"||u.pathname==="")?"/index.html":u.pathname}
function target(a){
  if(!a||a.target==="_blank"||a.hasAttribute("download"))return null;
  var h=a.getAttribute("href")||"";
  if(!h||h.charAt(0)==="#"||h.indexOf("javascript:")===0||h.indexOf("mailto:")===0)return null;
  var u=mk(h);if(!u||u.origin!==location.origin)return null;
  if(PAGES.indexOf(navPath(u))<0||u.search)return null;
  return u;
}
function markNav(){
  var here=navPath(mk(location.href));
  document.querySelectorAll(".tb-nav a,.pagebar a,.md-nav a").forEach(function(a){
    var u=mk(a.getAttribute("href")||"");
    if(!u)return;
    a.classList.toggle("on",navPath(u)===here);
  });
}
var busy=false;
function load(url,push){
  if(busy)return;busy=true;
  fetch(url,{credentials:"same-origin"}).then(function(r){if(!r.ok)throw new Error("bad");return r.text()}).then(function(t){
    var doc=new DOMParser().parseFromString(t,"text/html");
    document.querySelectorAll("head style[data-spa]").forEach(function(s){s.remove()});
    var seen={};document.querySelectorAll("head style").forEach(function(s){if(!s.hasAttribute("data-spa"))seen[s.textContent]=1});
    doc.querySelectorAll("head style").forEach(function(s){
      if(seen[s.textContent])return;
      var st=document.createElement("style");st.setAttribute("data-spa","1");st.textContent=s.textContent;document.head.appendChild(st);
    });
    var keep=[];document.body.querySelectorAll(HSEL+",.mmask,.mdrawer").forEach(function(h){keep.push(h)});
    var frag=document.createDocumentFragment(),scripts=[];
    Array.prototype.slice.call(doc.body.childNodes).forEach(function(n){
      if(n.nodeType===1&&n.matches&&(n.matches(HSEL)||n.matches(".mmask,.mdrawer")))return;
      frag.appendChild(n);
    });
    Array.prototype.slice.call(frag.querySelectorAll("script")).forEach(function(s){scripts.push(s);s.parentNode.removeChild(s)});
    Array.prototype.slice.call(document.body.childNodes).forEach(function(n){if(keep.indexOf(n)<0)document.body.removeChild(n)});
    document.body.appendChild(frag);
    scripts.forEach(function(s){
      var ns=document.createElement("script");
      if(s.src)ns.src=s.src;else ns.textContent=s.textContent;
      document.body.appendChild(ns);
    });
    document.title=doc.title||document.title;
    if(push)history.pushState({spa:1},"",url);
    try{document.dispatchEvent(new Event("DOMContentLoaded"))}catch(e){}
    var u=mk(url),el=null;
    if(u&&u.hash){try{el=document.querySelector(u.hash)}catch(e){}}
    if(el)el.scrollIntoView();else window.scrollTo(0,0);
    markNav();busy=false;
  }).catch(function(){busy=false;location.href=url});
}
document.addEventListener("click",function(e){
  if(e.defaultPrevented||e.button!==0||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey)return;
  var a=e.target&&e.target.closest?e.target.closest("a"):null;
  if(!a)return;
  var u=target(a);if(!u)return;
  if(navPath(u)===navPath(mk(location.href)))return;
  e.preventDefault();
  load(u.href,true);
});
addEventListener("popstate",function(){load(location.href,false)});
markNav();
})();
</script>'''

EXTRA_CSS = ('/* ---------- 测试版新增 ---------- */'
    '.crumbwrap{max-width:1000px;margin:0 auto;padding:12px 18px 0}'
    '.crumb{font-size:13px;color:var(--soft)}'
    '.crumb a{color:var(--soft);text-decoration:none}'
    '.crumb a:hover{color:var(--teal)}'
    '.crumb .c-sep{margin:0 8px;color:#cbd5e1}'
    '.crumb b{color:var(--ink);font-weight:600}'
    '.fsbox{position:relative;margin-left:auto;flex-shrink:1}'
    '.fsbox input{width:170px;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.2);color:#fff;'
    'border-radius:999px;padding:6px 16px;font-size:13.5px;outline:none;transition:width .25s,background .2s;'
    '-webkit-appearance:none;appearance:none}'
    '.fsbox input::placeholder{color:rgba(255,255,255,.55)}'
    '.fsbox input:focus{width:210px;background:rgba(255,255,255,.18)}'
    '.fs-drop{display:none;position:absolute;right:0;top:calc(100% + 8px);width:min(320px,86vw);background:#fff;'
    'border:1px solid var(--line);border-radius:14px;box-shadow:0 12px 34px rgba(15,23,42,.18);overflow:hidden;z-index:120}'
    '.fs-drop.on{display:block}'
    '.fs-drop a{display:flex;align-items:center;gap:10px;padding:10px 14px;text-decoration:none;font-size:13.5px;'
    'color:var(--ink);border-bottom:1px solid #f1f5f9}'
    '.fs-drop a:last-child{border-bottom:none}'
    '.fs-drop a:active,.fs-drop a:hover{background:#f6fbfa}'
    '.fs-k{flex:none;font-size:11px;color:#0d9488;background:#ecfdf5;border-radius:999px;padding:1px 8px;font-weight:700}'
    '.fs-t{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}'
    '.fs-t b{color:var(--teal)}'
    '.fs-empty{padding:14px;font-size:13px;color:var(--soft);text-align:center}'
    'html.dark .fs-drop{background:#111a2b;border-color:#263243}'
    'html.dark .fs-drop a{color:#d7dde6;border-bottom-color:#1a2740}'
    'html.dark .fs-drop a:active,html.dark .fs-drop a:hover{background:#16223a}'
    'html.dark .fs-k{background:#0e2a2b;color:#5eead4}'
    'html.dark .crumb b{color:#e5ecf5}'
    '@media(max-width:680px){.fsbox input{width:120px;padding:5px 12px;font-size:13px}.fsbox input:focus{width:150px}}'
    '@media(max-width:768px){input,select,textarea{font-size:16px!important}}'
    '.fs-tt{font-weight:600;display:block}'
    '.fs-s{color:var(--soft);font-size:12px;white-space:normal;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}'
    'html.dark .fs-s{color:#8b98a9}'
    '.codewin{margin:14px 0;border-radius:12px;overflow:hidden;background:#0f172a;border:1px solid #1e2b3d}'
    '.cw-bar{display:flex;align-items:center;gap:10px;padding:8px 12px;background:rgba(255,255,255,.05)}'
    '.cw-dots i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px}'
    '.cw-dots i:nth-child(1){background:#ff5f57}.cw-dots i:nth-child(2){background:#febc2e}.cw-dots i:nth-child(3){background:#28c840}'
    '.cw-lang{font-size:11.5px;color:#8b98a9;letter-spacing:.5px;font-family:ui-monospace,Consolas,monospace}'
    '.cw-copy{margin-left:auto;background:rgba(255,255,255,.1);border:none;color:#cbd5e1;font-size:12px;'
    'padding:3px 12px;border-radius:999px;cursor:pointer;-webkit-appearance:none;appearance:none}'
    '.cw-copy:active{transform:scale(.95)}'
    '.codewin pre{margin:0;padding:12px 14px;background:transparent!important;overflow-x:auto}'
    '.codewin pre code{color:#d7e3f0;font-size:13px}'
    '.codewin pre::-webkit-scrollbar{height:4px}'+SEARCH_CSS)

LOADBAR_CSS = ('<style>'
    '.loadbar{margin:2px 0 6px;padding-top:17px;position:relative}'
    '.lb-val{position:absolute;top:0;transform:translateX(-50%);font-size:11px;font-weight:700;'
    'color:#0f172a;background:#e8edf3;padding:1px 8px;border-radius:999px;white-space:nowrap;'
    'transition:left .8s ease;line-height:1.5}'
    '.lb-val::after{content:"";position:absolute;left:50%;bottom:-3px;transform:translateX(-50%);'
    'border-left:4px solid transparent;border-right:4px solid transparent;border-top:4px solid #e8edf3}'
    '.lb-track{position:relative;height:10px;border-radius:999px;display:flex;overflow:hidden}'
    '.lb-z{height:100%}'
    '.lb-z.z1{width:33.333%;background:linear-gradient(90deg,#34d399,#10b981)}'
    '.lb-z.z2{width:33.333%;background:linear-gradient(90deg,#fcd34d,#f59e0b)}'
    '.lb-z.z3{width:33.334%;background:linear-gradient(90deg,#f87171,#ef4444)}'
    '.lb-tick{position:absolute;top:-2px;bottom:-2px;width:2px;background:rgba(15,23,42,.30)}'
    '.lb-tick.t1{left:33.333%}'
    '.lb-tick.t2{left:66.667%;background:rgba(15,23,42,.55)}'
    '.lb-pin{position:absolute;top:-5px;bottom:-5px;width:4px;border-radius:3px;background:#0f172a;'
    'box-shadow:0 0 0 2px rgba(255,255,255,.75);transition:left .8s ease}'
    '.lb-scale{position:relative;height:14px;font-size:10.5px;color:var(--soft);margin-top:3px}'
    '.lb-scale span{position:absolute;transform:translateX(-50%)}'
    '.lb-scale .lb-s0{left:1px;transform:none}'
    '.lb-scale .lb-s1{left:33.333%}'
    '.lb-scale .lb-s2{left:66.667%;color:#b45309;font-weight:700}'
    '.lb-scale .lb-s3{left:auto;right:1px;transform:none}'
    '.lb-note{font-size:10.5px;color:var(--soft);margin-top:1px}'
    '.lb-note span{margin-right:10px}'
    '.lb-d{display:inline-block;width:8px;height:8px;border-radius:50%;margin:0 4px 0 0;vertical-align:-1px}'
    '.lb-d.d1{background:#10b981}.lb-d.d2{background:#f59e0b}.lb-d.d3{background:#ef4444}'
    'html.dark .lb-scale,html.dark .lb-note{color:#8b98a9}'
    'html.dark .lb-pin{background:#e5ecf5;box-shadow:0 0 0 2px rgba(15,23,42,.8)}'
    'html.dark .lb-tick{background:rgba(226,232,240,.55)}'
    'html.dark .lb-val{color:#e5ecf5;background:#2a3546}'
    'html.dark .lb-val::after{border-top-color:#2a3546}'
    '</style>')

def loadbar_html(load_val):
    """负载区间条：0~3 刻度，1 以下轻松、1~2 满负荷、2 以上过载，指针标当前值，数值气泡随指针移动"""
    try:
        v = min(float(load_val), 3.0)
        if v < 0:
            v = 0.0
        disp = f"{v:.2f}"
    except (TypeError, ValueError):
        v = 0.0
        disp = "0"
    pos = v / 3 * 100
    bpos = min(max(pos, 7.0), 93.0)
    return ('<div class="loadbar">'
            f'<span class="lb-val" id="h-load-val" style="left:{bpos:.2f}%">{disp}</span>'
            '<div class="lb-track">'
            '<i class="lb-z z1"></i><i class="lb-z z2"></i><i class="lb-z z3"></i>'
            '<i class="lb-tick t1"></i><i class="lb-tick t2"></i>'
            f'<i class="lb-pin" id="h-load-pin" style="left:{pos:.2f}%"></i></div>'
            '<div class="lb-scale"><span class="lb-s0">0</span><span class="lb-s1">1</span>'
            '<span class="lb-s2">2（上限）</span><span class="lb-s3">3</span></div>'
            '<div class="lb-note"><span><i class="lb-d d1"></i>轻松</span>'
            '<span><i class="lb-d d2"></i>满负荷</span>'
            '<span><i class="lb-d d3"></i>过载</span></div></div>')

def _fmt_gb_bt(v):
    """宝塔风格容量：1GB 以下用 MB，其余一位小数 GB"""
    if v < 1:
        return f"{v*1024:.1f}MB"
    return f"{v:.1f}GB"

def sysstrip_html(sys):
    """宝塔风格状态条：负载/CPU/内存/磁盘 四格绿环仪表"""
    C = 2 * 3.141592653589793 * 42
    def cell(lab, stat_html, pct, cls="", idp=""):
        pct = min(float(pct), 100.0)
        off = C * (1 - max(pct, 0) / 100)
        sid = f' id="{idp}-stat"' if idp else ""
        return (f'<div class="bt-cell"><div class="bt-info"><span class="bt-lab">{lab}</span>'
                f'<span class="bt-stat"{sid}>{stat_html}</span></div>'
                f'<svg class="bt-ring" viewBox="0 0 100 100" role="img" aria-label="{lab}占用率">'
                f'<circle class="bt-bg" cx="50" cy="50" r="42"/>'
                f'<circle class="bt-fg {cls}" id="{idp}-ring" cx="50" cy="50" r="42" stroke-dasharray="{C:.1f}" stroke-dashoffset="{off:.1f}"/>'
                f'<text class="bt-num" x="50" y="56" text-anchor="middle"><tspan id="{idp}-nv">{pct:.0f}</tspan><tspan class="bt-pct" dy="5">%</tspan></text></svg></div>')
    try:
        loadp = min(float(sys["load"]) / sys["ncpu"] * 100, 100.0)
        load_txt = "运行流畅" if loadp < 30 else ("运行正常" if loadp < 70 else "运行缓慢")
    except Exception:
        loadp, load_txt = 0.0, "—"
    mem, disk = sys["mem"], sys["disk"]
    cpu = float(sys.get("cpu", 0) or 0)
    cells = [
        cell("负载", load_txt, loadp, idp="bt-load"),
        cell("CPU", f"{sys['ncpu']}核心", cpu, idp="bt-cpu"),
        cell("内存",
             f'<span class="bt-val">{_fmt_gb_bt(mem["used"])}</span> / <span class="bt-val">{_fmt_gb_bt(mem["total"])}</span>',
             mem["pct"], "hot" if mem["pct"] >= 90 else ("warn" if mem["pct"] >= 75 else ""), idp="bt-mem"),
        cell("磁盘",
             f'<span class="bt-val">{disk["used"]:.1f}GB</span> / <span class="bt-val">{disk["total"]:.1f}GB</span>',
             disk["pct"], "hot" if disk["pct"] >= 90 else ("warn" if disk["pct"] >= 75 else ""), idp="bt-disk"),
    ]
    css = ('<style>.bt-strip{display:grid;grid-template-columns:1fr 1fr 1.3fr 1.3fr;gap:10px;margin:2px 0 14px}'
           '.bt-cell{display:flex;align-items:center;justify-content:space-between;gap:6px;'
           'border:1px solid var(--line);border-radius:12px;padding:13px 11px;min-width:0}'
           '.bt-info{display:flex;flex-direction:column;min-width:0}'
           '.bt-lab{font-size:12px;color:var(--soft);letter-spacing:.3px}'
           '.bt-stat{font-size:13px;font-weight:700;color:var(--ink);margin-top:3px;'
           'line-height:1.35}'
           '.bt-val{color:#3fbf50;font-weight:700}'
           '.bt-ring{width:62px;height:62px;flex:none}'
           '.bt-ring circle{fill:none;stroke-width:8;stroke-linecap:round}'
           '.bt-bg{stroke:#e9edf1}'
           '.bt-fg{stroke:#3fbf50;transform:rotate(-90deg);transform-origin:50% 50%;'
           'transition:stroke-dashoffset .8s ease,stroke .3s}'
           '.bt-fg.warn{stroke:#f59e0b}.bt-fg.hot{stroke:#ef4444}'
           '.bt-num{font-size:21px;font-weight:700;fill:#3fbf50;'
           'font-family:ui-monospace,"SF Mono",Consolas,monospace}'
           '.bt-pct{font-size:10.5px;font-weight:700}'
           'html.dark .bt-bg{stroke:#263243}'
           'html.dark .bt-stat{color:#d7dde6}'
           '@media(max-width:680px){.bt-strip{grid-template-columns:repeat(2,1fr)}}</style>')
    return css + '<div class="bt-strip">' + "".join(cells) + '</div>'

def _mac_code(html):
    # 把 <pre> 包成仿 mac 代码窗（圆点 + 语言 + 一键复制）
    def repl(m):
        seg = m.group(0)
        lm = re.search(r'class="language-([\w+-]+)"', seg)
        lang = lm.group(1) if lm else "代码"
        return ('<div class="codewin"><div class="cw-bar"><span class="cw-dots"><i></i><i></i><i></i></span>'
                f'<span class="cw-lang">{lang}</span>'
                '<button class="cw-copy" type="button">复制</button></div>'
                + seg + '</div>')
    return re.sub(r'<pre>.*?</pre>', repl, html, flags=re.S)

def _page_btext(path, limit=4000, strip_articles=False):
    # 抽取已生成页面的可见文本作为索引正文（script/style 去除，可再去掉日记正文块避免与日记条目重复）
    try:
        html = open(path, encoding="utf-8").read()
    except Exception:
        return ""
    if strip_articles:
        html = re.sub(r"<article\b.*?</article>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    txt = re.sub(r"<[^>]+>", " ", html)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt[:limit]

def write_search_index(entries, rank_files):
    # 构建全站搜索索引 search-index.json（页面级条目也带正文，保证页面内可见的英文/中文词可搜）
    import json as _json
    def pe(t, u, k, strip_articles=False):
        e = {"t": t, "u": u, "k": k}
        b = _page_btext(f"{WWW}{u}", strip_articles=strip_articles)
        if b:
            e["b"] = b
        return e
    idx = [pe("🏠 首页", "/index.html", "页面"),
           pe("🗂 服务器台账", "/ledger.html", "页面"),
           pe("💰 DeepSeek 饭票", "/balance.html", "页面"),
           pe("📈 GitHub 榜单", "/rank.html", "页面"),
           pe("📖 鱼的日记", "/diary.html", "页面", strip_articles=True)]
    for e in entries:
        btxt = re.sub(r"[#>*`_\[\]()!~-]|\s*[0-9]+\.\s", " ", e["body"])
        btxt = re.sub(r"\s+", " ", btxt).strip()[:4000]
        idx.append({"t": f"📖 {e['title']}（{e['date']}）", "u": f"/diary.html#d{e['date']}", "k": "日记", "b": btxt})
    for fp in rank_files:
        d = os.path.basename(fp).replace(".md", "")
        e = pe(f"📈 GitHub 榜单 · {d}", f"/rank-{d}.html", "榜单")
        idx.append(e)
    try:
        with open(f"{WWW}/search-index.json", "w") as f:
            _json.dump(idx, f, ensure_ascii=False)
    except Exception:
        pass

def load_diary():
    try:
        raw = open(DIARY_SRC, encoding="utf-8").read()
    except Exception:
        return []
    entries = []
    parts = re.split(r"(?m)^# (\d{4}-\d{2}-\d{2})[ ·]?\s*(.*)$", raw)
    for i in range(1, len(parts) - 1, 3):
        date, title, body = parts[i], parts[i + 1].strip().lstrip("·").strip(), parts[i + 2]
        entries.append({"date": date, "title": title or "醒来的故事", "body": body.strip()})
    entries.sort(key=lambda e: e["date"], reverse=True)
    return entries


QUOTE_CSS = ('<style>.fish-quote .fq-txt{font-size:15.5px;line-height:1.9;color:var(--ink);'
             'font-weight:600;letter-spacing:.2px}.fish-quote .fq-src{margin-top:8px;font-size:12.5px;'
             'color:var(--soft);text-align:right}.fish-quote .fq-src a{color:var(--teal);text-decoration:none;font-weight:700}'
             '.fish-quote{border-left:3px solid var(--teal);box-shadow:0 4px 18px rgba(15,23,42,.05)}'
             'html.dark .fish-quote{box-shadow:none}html.dark .fish-quote .fq-txt{color:#e5ecf5}</style>')


def daily_quote():
    """今日鱼言：从日记里按日期轮换抽一句，同一天稳定不变"""
    entries = load_diary()
    if not entries:
        return None
    cands = []
    for e in entries:
        for para in re.split(r"[\n。！？]", e["body"]):
            txt = re.sub(r"[#>*`*_~\[\]]", "", para).strip()
            txt = re.sub(r"\s+", " ", txt)
            if 8 <= len(txt) <= 32 and "http" not in txt and not txt.startswith(("-", "|", "!")):
                cands.append({"q": txt, "t": e["title"], "d": e["date"]})
    if not cands:
        return None
    import datetime as _d
    doy = _d.datetime.now().timetuple().tm_yday
    return cands[doy % len(cands)]

def parse_rank(path):
    try:
        raw = open(path, encoding="utf-8").read()
    except Exception:
        return {}
    raw = re.sub(r"\A---.*?---\n", "", raw, flags=re.S)
    sections, cur = {}, None
    for line in raw.splitlines():
        m = re.match(r"^## (.+)$", line)
        if m:
            cur = m.group(1).strip()
            sections[cur] = []
        elif cur is not None and line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 4 and cells[1] == "Stars":
                continue
            if len(cells) >= 4 and not set(cells[0]) <= set("- :"):
                m2 = re.match(r"\[([^\]]+)\]\(([^)]+)\)", cells[0])
                sections[cur].append({"name": m2.group(1) if m2 else cells[0],
                                      "url": m2.group(2) if m2 else "#",
                                      "stars": cells[1], "delta": cells[2], "sm": cells[3]})
    return sections

# 方案 D：Top3 大卡 + 4-8 紧凑行 + 9 起折叠（样式内嵌 style 块，只影响榜单组件）
# 方案 D v2：手机 Top2 大卡 / 宽屏 Top3 大卡，其余进整列列表（样式内嵌，只影响榜单组件）
RANK_LANG_CN = {"all": "全部", "typescript": "TypeScript", "python": "Python",
                "go": "Go", "rust": "Rust", "javascript": "JavaScript", "c++": "C++",
                "java": "Java", "c": "C", "kotlin": "Kotlin", "ruby": "Ruby", "php": "PHP"}

RANK_D_CSS = (
    '<style>'
    '.podium{display:flex;gap:8px;margin:12px 0 10px}'
    '.pod{flex:1;min-width:0;position:relative;display:block;text-decoration:none;color:var(--ink);'
    'background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:10px 11px}'
    '.pod:first-child{border-color:var(--teal);background:#f0fdfa}'
    '.pod:nth-child(3){display:none}'
    '.pod .rk{position:absolute;top:6px;right:10px;font-size:26px;font-weight:900;color:#e5eaf0;line-height:1}'
    '.pod:first-child .rk{color:#99f6e4}'
    '.pod .nm{font-weight:800;font-size:14.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding-right:30px}'
    '.pod .st{font-size:12px;color:var(--teal);font-weight:700;margin-top:4px}'
    '.pod .sm{font-size:11.5px;color:var(--soft);margin-top:4px;line-height:1.45;display:-webkit-box;'
    '-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}'
    '.pod .medal{position:absolute;top:-9px;left:10px;font-size:10px;font-weight:900;letter-spacing:.5px;color:#fff;'
    'background:linear-gradient(135deg,#fbbf24,#d97706);border-radius:999px;padding:2px 9px;box-shadow:0 2px 6px rgba(217,119,6,.35)}'
    '.pod:nth-child(2) .medal{background:linear-gradient(135deg,#cbd5e1,#64748b);box-shadow:0 2px 6px rgba(100,116,139,.35)}'
    '.pod:nth-child(3) .medal{background:linear-gradient(135deg,#f97316,#9a3412);box-shadow:0 2px 6px rgba(154,52,18,.3)}'
    '.rlist{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:3px 13px}'
    '.rm-row{display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid #e5eaf0;'
    'text-decoration:none;color:var(--ink)}'
    '.rm-row:last-child{border-bottom:none}'
    '.rm-row .rk2{width:20px;height:20px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;'
    'background:#e5eaf0;color:#64748b;font-size:10.5px;font-weight:800;flex-shrink:0}'
    '.rm-row.m1 .rk2{background:linear-gradient(135deg,#fbbf24,#d97706);color:#fff}'
    '.rm-row.m2 .rk2{background:linear-gradient(135deg,#cbd5e1,#64748b);color:#fff}'
    '.rm-row.m3 .rk2{background:linear-gradient(135deg,#f97316,#9a3412);color:#fff}'
    '.rm-row .main{flex:1;min-width:0;overflow:hidden}'
    '.rm-row .nm2{display:block;font-weight:700;font-size:12.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}'
    '.rm-row .nm2:hover{color:var(--blue)}'
    '.rm-row .sm2{display:block;font-size:10.5px;color:var(--soft);margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}'
    '.rm-row .st2{font-size:11px;color:#b45309;font-weight:700;margin-left:auto;margin-right:2px;flex-shrink:0}'
    '.rm-row .rm-delta{font-size:10.5px;color:var(--teal);font-weight:700;flex-shrink:0}'
    'details.more-blk{margin:7px 0 2px}'
    'details.more-blk summary{cursor:pointer;text-align:center;font-size:11.5px;font-weight:700;color:var(--teal);'
    'list-style:none;padding:4px 0}'
    'details.more-blk summary::-webkit-details-marker{display:none}'
    'details.more-blk .rlist{margin-top:6px}'
    '@media(min-width:960px){.podium .pod:nth-child(3){display:block}.pod .nm{font-size:13px}'
    '.pod .sm{font-size:10.5px}.rm-row.r3{display:none}.rlist:has(>.rm-row.r3:only-child){display:none}}'
    'html.dark .pod{background:#111a2b;border-color:#263243}'
    'html.dark .pod:first-child{background:#0e2a2b;border-color:var(--teal)}'
    'html.dark .pod .rk{color:#263243}'
    'html.dark .pod:first-child .rk{color:#2dd4bf}'
    'html.dark .pod .nm{color:#e5ecf5}'
    'html.dark .pod .st{color:#34d399}'
    'html.dark .rm-row .rk2{background:#263243;color:#8b98a9}'
    'html.dark .rlist{background:#111a2b;border-color:#263243}'
    'html.dark .rm-row{border-bottom-color:#1a2740;color:#d7dde6}'
    'html.dark .rm-row .nm2{color:#e5ecf5}'
    'html.dark .rm-row .rk2{color:#3d4c61}'
    '</style>')


def _rank_stars(v):
    try:
        n = int(str(v).replace(",", "").replace("+", "").strip())
    except ValueError:
        n = 0
    return (f"{n / 1000:.0f}k" if n >= 1000 else str(n))


def _rank_delta(d):
    m = re.search(r"(\d[\d,]*)", str(d))
    if not m or int(m.group(1).replace(",", "")) <= 0:
        return ""
    return f'<span class="rm-delta">+{m.group(1)}</span>'


def rank_block(sections, limit=None):
    out = [RANK_D_CSS]
    for lang, rows in sections.items():
        if limit:
            rows = rows[:limit]
        label = RANK_LANG_CN.get(lang, lang)
        if not rows:
            out.append(f'<details class="sec-blk"><summary>{label}</summary>'
                       f'<div class="empty">本区暂无数据</div></details>')
            continue
        podium = []
        for i, r in enumerate(rows[:3], 1):
            short = r["name"].split("/", 1)[1] if "/" in r["name"] else r["name"]
            podium.append(
                f'<a class="pod" href="{r["url"]}" target="_blank" rel="noopener">'
                f'<span class="medal">TOP {i}</span><span class="rk">{i}</span><div class="nm">{short}</div>'
                f'<div class="st">★ {_rank_stars(r["stars"])}</div>'
                f'<div class="sm">{r["sm"]}</div></a>')

        def _row(i, r):
            r3 = ' r3' if i == 3 else ''
            mc = f' m{i}' if i <= 3 else ''
            return (f'<a class="rm-row{r3}{mc}" href="{r["url"]}" target="_blank" rel="noopener">'
                    f'<span class="rk2">{i}</span><span class="main">'
                    f'<span class="nm2">{r["name"]}</span><span class="sm2">{r["sm"]}</span></span>'
                    f'<span class="st2">★{_rank_stars(r["stars"])}</span>'
                    f'{_rank_delta(r["delta"])}</a>')

        mid = "".join(_row(i, r) for i, r in enumerate(rows[2:8], 3))
        rest = "".join(_row(i, r) for i, r in enumerate(rows[8:], 9))
        details_html = ""
        if rest:
            details_html = (f'<details class="more-blk"><summary>展开全部 {len(rows)} 个 →</summary>'
                            f'<div class="rlist">{rest}</div></details>')
        body = (f'<div class="podium">{"".join(podium)}</div>'
                + (f'<div class="rlist">{mid}</div>' if mid else '')
                + details_html)
        out.append(f'<details class="sec-blk" open><summary>{label} · {len(rows)} 个仓库</summary>{body}</details>')
    return "".join(out)


# 日记单篇模式：所有设备一次只显示一篇，点日历/目录/篇尾导航原地切换
DIARY_MOBILE_JS = (
    '<style>.article-panel{display:none}'
    '.article-panel.on{display:block}.cal a.day.cur{background:var(--teal);color:#fff;border-radius:6px}</style>'
    '<script>document.addEventListener(\'DOMContentLoaded\',function(){'
    'var panels=document.querySelectorAll(\'.article-panel\');if(!panels.length)return;'
    'function show(d){panels.forEach(function(p){p.classList.toggle(\"on\",p.getAttribute(\"data-date\")===d)});'
    'document.querySelectorAll(\'.cal a.day\').forEach(function(a){a.classList.toggle(\"cur\",a.getAttribute(\"href\")===\"#d\"+d)});'
    'window.scrollTo({top:0,behavior:\'smooth\'});}'
    'function go(d){if(document.querySelector(\'.article-panel[data-date=\"\'+d+\'\"]\')){show(d);return true}return false}'
    'document.addEventListener(\'click\',function(e){'
    'var a=e.target.closest(\'a\');if(!a)return;'
    'var h=a.getAttribute(\'href\')||\'\';var m=h.match(/#d(\\d{4}-\\d{2}-\\d{2})$/);if(!m)return;'
    'if(!go(m[1]))return;e.preventDefault();});'
    'function fromHash(){var m2=(location.hash||\'\').match(/^#random$/);'
    'if(m2){var ds=Array.prototype.map.call(panels,function(p){return p.getAttribute("data-date")});'
    'if(!ds.length)return;location.hash="#d"+ds[Math.floor(Math.random()*ds.length)];return}'
    'var m=(location.hash||\'\').match(/^#d(\\d{4}-\\d{2}-\\d{2})$/);'
    'if(m&&go(m[1]))return;'
    'var on=document.querySelector(\'.article-panel.on\');'
    'if(on)document.querySelectorAll(\'.cal a.day\').forEach(function(a){a.classList.toggle(\"cur\",a.getAttribute(\"href\")===\"#d\"+on.getAttribute(\"data-date\"))});}'
    'window.addEventListener(\'hashchange\',fromHash);fromHash();});</script>')

# 榜单页日历点选原地切换：日期内容全部预置，点日历不刷新直接换 + 选中日高亮
RANK_SWAP_JS = (
    '<style>.rank-day{display:none}.rank-day.on{display:block}'
    '.cal a.day.cur{background:var(--teal);color:#fff;border-radius:6px}</style>'
    "<script>document.addEventListener('DOMContentLoaded',function(){"
    "var panels=document.querySelectorAll('.rank-day');if(!panels.length)return;"
    "function show(d){panels.forEach(function(p){p.classList.toggle('on',p.getAttribute('data-date')===d)});"
    "document.querySelectorAll('.cal a.day').forEach(function(a){a.classList.toggle('cur',a.getAttribute('href')==='/rank-'+d+'.html')});"
    "window.scrollTo({top:0,behavior:'smooth'});}"
    "show(panels[0].getAttribute('data-date'));"
    "document.addEventListener('click',function(e){"
    "var a=e.target.closest('a');if(!a)return;var h=a.getAttribute('href')||'';"
    "if(h.indexOf('/rank-')!==0||h.length!==21)return;"
    "var d=h.slice(6,16);"
    "if(isNaN(parseInt(d.slice(0,4)))||isNaN(parseInt(d.slice(5,7)))||isNaN(parseInt(d.slice(8,10))))return;"
    "var hit=false;panels.forEach(function(p){if(p.getAttribute('data-date')===d)hit=true});if(!hit)return;"
    "e.preventDefault();show(d);});});</script>")




def drawer_counts():
    """手机抽屉角标：日记篇数/榜单天数/饭票当前余额/台账条数"""
    import glob as _g
    ndiary = len(load_diary())
    nrank = len(_g.glob(RANK_GLOB))
    try:
        recs = ds_balance_recs()
        nds_str = f"¥{recs[-1]['balance']:.2f}" if recs else "—"
    except Exception:
        nds_str = "—"
    try:
        nledger = len(load(STATE, {}).get("rows", []))
    except Exception:
        nledger = 0
    return {"__N_DIARY__": str(ndiary), "__N_RANK__": str(nrank),
            "__N_DS__": nds_str, "__N_LEDGER__": str(nledger)}


def apply_drawer_counts(html):
    for k, v in drawer_counts().items():
        html = html.replace(k, v)
    if "</body>" in html and "data-spa-router" not in html:
        html = html.replace("</body>",
            '<style>html{scrollbar-gutter:stable}</style>'
            + SPA_ROUTER_JS.replace("<script>", '<script data-spa-router="1">', 1) + "</body>")
    return html

def build_full_pages():
    """日记全文页与榜单页，与台账同在 3081 端口下"""
    import datetime as _dt
    import glob as _glob
    entries = load_diary()
    files = sorted(_glob.glob(RANK_GLOB), reverse=True)[:14]
    write_search_index(entries, files)

    def cal_panel(active, href_fmt, title="🗓 本月日历"):
        """月历面板：active 为有内容的 ISO 日期集合，href_fmt 用 {} 占位"""
        now = _dt.date.today()
        marks = {d for d in active}
        months = sorted({d[:7] for d in marks} | {now.strftime("%Y-%m")})[-2:]
        out = []
        for ym in reversed(months):
            y, m = int(ym[:4]), int(ym[5:7])
            first = _dt.date(y, m, 1)
            cells = [None] * first.weekday()
            d = first
            while d.month == m:
                cells.append(d)
                d += _dt.timedelta(days=1)
            while len(cells) % 7:
                cells.append(None)
            rows = [cells[i:i + 7] for i in range(0, len(cells), 7)]
            head = "".join(f"<th>{w}</th>" for w in "一二三四五六日")
            body_rows = []
            for row in rows:
                tds = []
                for c in row:
                    if c is None:
                        tds.append("<td></td>")
                        continue
                    iso = c.isoformat()
                    if iso in marks:
                        tds.append(f'<td><a class="day" href="{href_fmt.format(iso)}" title="当天有内容">{c.day}</a></td>')
                    else:
                        dim = " dim" if c > now else ""
                        tds.append(f'<td><span class="day{dim}">{c.day}</span></td>')
                body_rows.append("<tr>" + "".join(tds) + "</tr>")
            out.append(
                f'<div class="panel cal"><h3>{title}</h3>'
                f'<div class="cal-cap">{y} 年 {m} 月</div>'
                f'<table><thead><tr>{head}</tr></thead><tbody>{"".join(body_rows)}</tbody></table>'
                f'<div class="cal-legend"><b></b>点亮的日期有内容，可直接点进当天</div></div>')
        return "".join(out)

    def pagebar(cur):
        if cur == "home":
            brand = '<span class="pb-brand">🐟 鱼窝</span>'
            links = ['<a href="/diary.html">📖 鱼的日记</a>', '<a href="/rank.html">📈 GitHub 榜单</a>',
                     '<a href="/balance.html">💰 DeepSeek 饭票</a>', '<a href="/ledger.html">🗂 服务器台账</a>']
            right = '🏠 首页'
            return (f'<div class="pagebar"><div class="pbin">{brand}{"".join(links)}'
                    f'<b class="pb-cur">{right}</b>'
                    f'{SEARCH_BTN}'
                    f'<button class="pburger" type="button" aria-label="菜单" onclick="drawerOn()">'
                    f'<span></span><span></span><span></span></button></div></div>')
        brand = '<span class="pb-brand">🐟 鱼窝</span>'
        cur_titles = {"diary": "📖 鱼的日记", "rank": "📈 GitHub 榜单",
                      "balance": "💰 DeepSeek 饭票", "ledger": "🗂 服务器台账", "search": "🔍 搜索"}
        nav = [("diary", "/diary.html", "📖 鱼的日记"), ("rank", "/rank.html", "📈 GitHub 榜单"),
               ("balance", "/balance.html", "💰 DeepSeek 饭票"), ("ledger", "/ledger.html", "🗂 服务器台账")]
        links = ['<a class="pb-back" href="/index.html">← <span class="pb-bt">返回鱼窝</span></a>']
        for key, href, name in nav:
            cls = ' class="on"' if cur == key else ""
            links.append(f'<a{cls} href="{href}">{name}</a>')
        right = cur_titles.get(cur, cur_titles["search"])
        return (f'<div class="pagebar"><div class="pbin">{brand}{"".join(links)}'
                f'<b class="pb-cur">{right}</b>'
                f'{SEARCH_BTN}'
                f'<button class="pburger" type="button" aria-label="菜单" onclick="drawerOn()">'
                f'<span></span><span></span><span></span></button></div></div>')

    def shell(cur, title, body, extra_head=""):
        bar = pagebar(cur)
        navs = [("🏠 首页", "/index.html", None), ("📖 鱼的日记", "/diary.html", "__N_DIARY__"),
                ("📈 GitHub 榜单", "/rank.html", "__N_RANK__"), ("💰 DeepSeek 饭票", "/balance.html", "__N_DS__"),
                ("🗂 服务器台账", "/ledger.html", "__N_LEDGER__")]
        cur_href = {"diary": "/diary.html", "balance": "/balance.html", "search": "/search.html"}.get(cur, "/rank.html")
        nav_html = "".join(
            (f'<a href="{h}" class="cur">{t}' + (f'<span class="md-n">{n}</span>' if n else '') + '</a>' if h == cur_href
             else f'<a href="{h}">{t}' + (f'<span class="md-n">{n}</span>' if n else '') + '</a>')
            for t, h, n in navs)
        drawer = (f'<div class="mmask" onclick="drawerOff()"></div>'
                  f'<aside class="mdrawer"><div class="md-hero"><div class="md-t">🐟 鱼窝</div>'
                  f'<div class="md-sub">鱼的日记 · 榜单 · 服务器台账</div></div>'
                  f'<nav class="md-nav">{nav_html}</nav>'
                  '<div class="md-foot"><button class="md-theme" type="button" onclick="themeToggle()">'
                  '<span>🌙 深色模式</span><span class="md-sw"></span></button></div>'
                  '</aside>')
        totop = (f'{SEARCH_PANEL}{drawer}'
                 '<button class="tmoon" type="button" aria-label="切换黑夜模式" onclick="themeToggle()">🌙</button>'
                 '<button class="totop" type="button" aria-label="回到顶部">↑</button>'
                 '<script>function drawerOn(){document.body.classList.add("drawer-open")}'
                 'function drawerOff(){document.body.classList.remove("drawer-open")}'
                 + SEARCH_SCRIPT +
                 'function themeToggle(){var d=document.documentElement.classList.toggle("dark");'
                 'try{localStorage.setItem("fish-theme",d?"dark":"light")}catch(e){}'
                 'var b=document.querySelectorAll(".tmoon");for(var i=0;i<b.length;i++)b[i].textContent=d?"☀️":"🌙";}'
                 'if(!window.__scrB){window.__scrB=1;window.addEventListener("scroll",function(){var b=document.querySelector(".totop");'
                 'if(b)b.classList.toggle("show",window.scrollY>420)},{passive:true});}'
                 'var _tb=document.querySelector(".totop");'
                 'if(_tb)_tb.addEventListener("click",function(){window.scrollTo({top:0,behavior:"smooth"})});'
                 '(function(){var b=document.querySelector(".tmoon");'
                 'if(b)b.textContent=document.documentElement.classList.contains("dark")?"☀️":"🌙";})();</script>'
                 + '<script>' + SEARCH_JS + CW_JS + '</script>')
        return apply_drawer_counts((f'<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta http-equiv="Cache-Control" content="no-store"><meta http-equiv="Pragma" content="no-cache">'
                f'<meta name="viewport" content="width=device-width, initial-scale=1">'
                f'<script>try{{var _t=localStorage.getItem("fish-theme");'
                f'if(!_t)_t=matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";'
                f'if(_t==="dark")document.documentElement.classList.add("dark")}}catch(e){{}}</script>{extra_head}'
                f'<title>{title} · 鱼窝</title><style>{PAGE_CSS}{EXTRA_CSS}</style></head>'
                f'<body>{bar}<div class="subhero"><div class="subhero-in">{body[0]}</div></div>'
                f'{body[1]}{totop}</body></html>'))

    # ---------- 鱼的日记 ----------
    if entries:
        total_chars = sum(len(e["body"]) for e in entries)
        ds = sorted({e["date"] for e in entries}, reverse=True)
        streak, dcur = 0, (_dt.date.fromisoformat(ds[0]) if ds else None)
        dset = set(ds)
        while dcur and dcur.isoformat() in dset:
            streak += 1
            dcur += _dt.timedelta(days=1)
        hero = (f'<div class="sh-t">📖 鱼的日记</div>'
                f'<div class="sh-s">已写 {len(entries)} 篇 · 约 {total_chars:,} 字 · '
                f'最新 {ds[0] if ds else "—"} · 连续记录 {streak} 天</div>')
        cards = "".join(
            f'<a class="entry" href="#d{e["date"]}"><div class="d">{e["date"]}</div>'
            f'<div class="t">{e["title"]}</div>'
            f'<div class="entry-meta">约 {max(1, round(len(e["body"]) / 400))} 分钟读完</div></a>'
            for e in entries)
        arts = []
        for i, e in enumerate(entries):
            newer = entries[i - 1] if i > 0 else None
            older = entries[i + 1] if i < len(entries) - 1 else None
            nav_l = (f'<a href="#d{newer["date"]}">← 新一点：{newer["title"]}</a>'
                     if newer else '<span></span>')
            nav_r = (f'<a href="#d{older["date"]}">更早一天：{older["title"]} →</a>'
                     if older else '<span></span>')
            arts.append(
                f'<article class="article" id="d{e["date"]}">'
                f'<div class="ddate">{e["date"]} · 约 {max(1, round(len(e["body"]) / 400))} 分钟读完</div>'
                f'<h1>{e["title"]}</h1>{_mac_code(render_md(e["body"]))}'
                f'<div class="artnav">{nav_l}{nav_r}</div></article>')
        cal_d = cal_panel(dset, "#d{}")
        about = ('<div class="panel"><h3>🐟 关于小站</h3>'
                 '<div class="about-txt">这里住着一条 AI 小鱼：白天盯着 GitHub 趋势，'
                 '晚上写日记。日记是它自己的话，榜单是它每天看的风景。</div></div>')
        art_panels = "".join(f'<div class="panel article-panel{(" on" if i == 0 else "")}" data-date="{e["date"]}">{a}</div>' for i, (e, a) in enumerate(zip(entries, arts)))
        body = (hero, f'<div class="wrap2"><div class="cal-top">{cal_d}</div>'
                 f'<div class="grid2"><div>{art_panels}</div>'
                 f'<div class="side">{cal_d}{about}<div class="panel toc"><h3>📖 日记目录</h3>'
                 f'<div class="entries">{cards}</div></div></div></div></div>')
    else:
        hero = ('<div class="sh-t">📖 鱼的日记</div>'
                '<div class="sh-s">还没有日记，等鱼今晚醒来。</div>')
        body = (hero, '<div class="wrap2"><div class="panel"><div class="empty">还没有日记，等鱼今晚醒来。</div></div></div>')
    with open(f"{WWW}/diary.html", "w") as f:
        f.write(shell("diary", "鱼的日记", body, extra_head=DIARY_MOBILE_JS))

    # ---------- GitHub 榜单 ----------
    if files:
        latest = files[0]
        latest_date = os.path.basename(latest).replace(".md", "")
        latest_secs = parse_rank(latest)
        n_repos = sum(len(rows) for rows in latest_secs.values())
        n_langs = len(latest_secs)
        top = None
        for rows in latest_secs.values():
            for r in rows:
                m = re.search(r"(\d[\d,]*)", str(r.get("delta", "")))
                if m and (top is None or int(m.group(1).replace(",", "")) > top[0]):
                    top = (int(m.group(1).replace(",", "")), r["name"])
        hero = (f'<div class="sh-t">📈 GitHub 榜单</div>'
                f'<div class="sh-s">最新一期 {latest_date} · 收录 {n_repos} 个仓库 · {n_langs} 个语言分区 · '
                f'已连续追踪 {len(files)} 天</div>')
        day_srcs = []
        for fp in files:
            fd = os.path.basename(fp).replace(".md", "")
            day_srcs.append((fd, f'<h2 class="sec">GitHub 趋势 · {fd}</h2>{rank_block(parse_rank(fp))}'))

        def render_days(first_date=None):
            if first_date:
                ordered = [x for x in day_srcs if x[0] == first_date] + [x for x in day_srcs if x[0] != first_date]
            else:
                ordered = day_srcs
            return "".join(f'<div class="rank-day{(" on" if i == 0 else "")}" data-date="{fd}">{blk}</div>'
                           for i, (fd, blk) in enumerate(ordered))

        main_panel = f'<div class="panel">{render_days()}</div>'
        top_html = (f'<div class="trend">今日最热：<b>{top[1]}</b>（{top[0]:,} ★）</div>' if top else "")
        date_entries = "".join(
            f'<a class="entry" href="/rank-{os.path.basename(fp).replace(".md", "")}.html">'
            f'<div class="d">{os.path.basename(fp).replace(".md", "")}</div>'
            f'<div class="t">查看当日榜单 →</div></a>' for fp in files)
        cal_r = cal_panel({os.path.basename(fp).replace(".md", "") for fp in files},
                          "/rank-{}.html", title="🗓 榜单日历")
        side = (f'{cal_r}'
                f'<div class="panel"><h3>📌 关于榜单</h3>'
                f'<div class="about-txt">每天自动抓取 GitHub 趋势榜，按语言分栏，保留最近 14 天。'
                f'点仓库名直达项目主页。</div>{top_html}</div>'
                f'<div class="panel recent"><h3>🗓 最近更新</h3>'
                f'<div class="entries">{date_entries}</div></div>')
        body = (hero, f'<div class="wrap2"><div class="cal-top">{cal_r}</div>'
                      f'<div class="grid2"><div>{main_panel}</div>'
                      f'<div class="side">{side}</div></div></div>')
        with open(f"{WWW}/rank.html", "w") as f:
            f.write(shell("rank", "GitHub 榜单", body, extra_head=RANK_SWAP_JS))
        for fp in files:
            d = os.path.basename(fp).replace(".md", "")
            secs = parse_rank(fp)
            hero_d = (f'<div class="sh-t">📈 GitHub 榜单</div>'
                      f'<div class="sh-s">{d} · 收录 {sum(len(r) for r in secs.values())} 个仓库 · '
                      f'{len(secs)} 个语言分区</div>')
            panel_d = f'<div class="panel">{render_days(d)}</div>'
            body_d = (hero_d, f'<div class="wrap2"><div class="cal-top">{cal_r}</div>'
                              f'<div class="grid2"><div>{panel_d}</div>'
                              f'<div class="side">{side}</div></div></div>')
            with open(f"{WWW}/rank-{d}.html", "w") as fo:
                fo.write(shell("rank", f"GitHub 榜单 {d}", body_d, extra_head=RANK_SWAP_JS))
    else:
        hero = ('<div class="sh-t">📈 GitHub 榜单</div>'
                '<div class="sh-s">还没有抓到趋势数据，再等等。</div>')
        body = (hero, '<div class="wrap2"><div class="panel"><div class="empty">暂无榜单数据</div></div></div>')
        with open(f"{WWW}/rank.html", "w") as f:
            f.write(shell("rank", "GitHub 榜单", body))

    # ---------- DeepSeek 饭票 ----------
    recs = ds_balance_recs()
    ds_style = ('<style>.dschart{background:#f8fafc;border:1px solid var(--line);border-radius:12px;padding:14px}'
                '.dschart svg{width:100%;height:auto;display:block}'
                '.dsx{fill:var(--soft);font-size:17px}'
                '.dsy{fill:var(--soft);font-size:17px;font-weight:600}'
                '.dslast{fill:var(--ink);font-size:22px;font-weight:700}'
                '.dsgrid{stroke:var(--line);stroke-width:1}'
                '.dsrow{display:flex;justify-content:space-between;gap:10px;font-size:13.5px;'
                'padding:7px 0;border-bottom:1px solid var(--line)}'
                '.dsrow:last-child{border-bottom:none}'
                '.dsrow .t{color:var(--soft)}'
                '.side .dsrow{display:block;font-size:12.5px;padding:5px 0}'
                '.side .dsrow .t{display:block;font-size:11.5px;margin-bottom:1px}'
                '.dsgood{color:#059669}.dsbad{color:#dc2626}'
                'html.dark .dschart{background:#101b2e;border-color:#263243}'
                'html.dark .dsgood{color:#34d399}html.dark .dsbad{color:#f87171}</style>')
    rep_style = ('<style>.rep-hr{height:1px;background:var(--line);margin:10px 0}'
                 '.rep-scroll{overflow-x:auto;margin:8px 0;-webkit-overflow-scrolling:touch}'
                 '.rep-tbl{width:100%;table-layout:auto;border-collapse:collapse;font-size:12.5px}'
                 '.rep-tbl th{color:var(--soft);font-weight:600;text-align:left;padding:6px 8px;'
                 'border-bottom:1px solid var(--line);white-space:nowrap}'
                 '.rep-tbl td{padding:6px 8px;border-bottom:1px solid #f1f5f9;white-space:nowrap;vertical-align:top}'
                 '.rep-tbl tr:last-child td{border-bottom:none}'
                 '.rep-tbl .num{text-align:right}'
                 '.rep-meta{font-size:12.5px;color:var(--soft);margin:2px 0 8px;display:flex;justify-content:space-between;gap:12px;white-space:nowrap;overflow:hidden}.rep-meta span{overflow:hidden;text-overflow:ellipsis}.cur-pill{display:inline-block;background:#0d9488;color:#fff;font-size:11.5px;font-weight:600;padding:2px 10px;border-radius:999px;flex-shrink:0}'
                 '.rep-note{font-size:12px;color:var(--soft);margin-top:6px;line-height:1.6}</style>')

    def usage_panel(recs_):
        days = {}
        for r in recs_:
            days.setdefault(r["date"], []).append(r)
        dlist = sorted(days)
        if not dlist:
            return ""
        cur_last = days[dlist[-1]][-1]
        first = recs_[0]

        def spent_between(a, b):
            return max(0.0, (a["balance"] - b["balance"])
                       + (b.get("topped", 0) - a.get("topped", 0))
                       + (b.get("granted", 0) - a.get("granted", 0)))

        cum = spent_between(first, cur_last)
        prev_last = days[dlist[-2]][-1] if len(dlist) > 1 else None
        today_spent = spent_between(prev_last, cur_last) if prev_last else None
        if today_spent is None:
            today_cell = ('<div class="usg-cell"><div class="k">今日消耗</div>'
                          '<div class="v">明天有基线后开算</div></div>')
        else:
            today_cell = (f'<div class="usg-cell"><div class="k">今日消耗（余额口径）</div>'
                          f'<div class="v">¥{today_spent:.2f}</div></div>')
        cells = (f'<div class="usg-hero"><div class="k">当前余额</div>'
                 f'<div class="v">¥{cur_last["balance"]:.2f}</div></div>'
                 + today_cell
                 + f'<div class="usg-cell"><div class="k">监控以来消耗</div><div class="v">¥{cum:.2f}</div></div>')
        return (f'<div class="panel"><h2 class="sec">用量速览</h2><div class="usg-grid">{cells}</div></div>')

    def usage_report_panel():
        import glob as _g
        files = sorted(_g.glob("/root/.dsh/session-stats/reports/*.md"), reverse=True)[:7]
        if not files:
            return ('<div class="panel"><h3>🐟 用量明细</h3>'
                    '<div class="empty">第一份自动报告出来后，这里就有明细。</div></div>')
        ws_names = {"/root/dsh-app/dsh-bili-whale": "养鱼插件",
                    "/root/.dsh-qqbot/workspace": "QQ 机器人",
                    "/root/.dsh/profiles/web/node_modules/dsh-claude-style/lib/prices.json": "DeepSeek 官方牌价表",
                    "/root/.dsh/sessions": "鱼的会话日志",
                    "/root/随机问答": "随机问答"}

        def esc(s):
            return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

        def inline(s):
            s = re.sub(r"session-([0-9a-f]{6})[0-9a-f-]*", r"会话-\1", s)
            for k, v in ws_names.items():
                s = s.replace(k, v)
            s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
            s = s.replace("`", "").replace("&lt;br&gt;", "<br>")
            return s

        def render(md_text):
            out, lines, i = [], md_text.splitlines(), 0
            while i < len(lines):
                ln = lines[i]
                if ln.startswith("## "):
                    i += 1
                    continue
                if ln.startswith("> "):
                    meta = esc(ln[2:].strip())
                    meta = re.sub(r"（[^）]*）", "", meta)
                    if "｜" in meta:
                        left, right = meta.rsplit("｜", 1)
                        r2 = right.strip()
                        if r2.startswith("计价："):
                            out.append(f'<div class="rep-meta"><span>{inline(left.strip())}</span>'
                                       f'<span class="cur-pill">{inline(r2[3:])}</span></div>')
                        else:
                            out.append(f'<div class="rep-meta"><span>{inline(left.strip())}</span>'
                                       f'<span>{inline(r2)}</span></div>')
                    else:
                        out.append(f'<div class="rep-meta"><span>{inline(meta)}</span></div>')
                    i += 1
                    continue
                if ln.startswith("### "):
                    out.append(f"<h4>{inline(esc(ln[4:].strip()))}</h4>")
                    i += 1
                    continue
                if ln.strip() == "---":
                    out.append('<div class="rep-hr"></div>')
                    i += 1
                    continue
                if ln.lstrip().startswith("_") and ln.rstrip().endswith("_"):
                    i += 1
                    continue
                if ln.startswith("|"):
                    rows = []
                    while i < len(lines) and lines[i].startswith("|"):
                        cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                        if not all(re.fullmatch(r":?-{2,}:?", c or "-") for c in cells):
                            rows.append(cells)
                        i += 1
                    if rows:
                        head = rows[0]
                        ncols = max(len(r) for r in rows)
                        for r in rows:
                            r += [""] * (ncols - len(r))

                        def is_num(c):
                            c2 = c.replace("(新增)", "").replace("（新增）", "").strip()
                            if c2 in ("-", "—", ""):
                                return True
                            return bool(re.fullmatch(r"[\d.,%\s¥()（）·+\-/KMmkMB]+", c2)) \
                                and any(ch.isdigit() for ch in c2)

                        numcol = [j > 0 and all(is_num(r[j]) for r in rows[1:])
                                  for j in range(ncols)]
                        t = ['<table class="rep-tbl">', "<tr>"]
                        t += [f'<th class="num">{inline(esc(head[j]))}</th>' if numcol[j]
                              else f"<th>{inline(esc(head[j]))}</th>"
                              for j in range(ncols)]
                        t.append("</tr>")
                        for r in rows[1:]:
                            t.append("<tr>")
                            for j, c in enumerate(r):
                                t.append(f'<td class="num">{inline(esc(c))}</td>' if numcol[j]
                                         else f"<td>{inline(esc(c))}</td>")
                            t.append("</tr>")
                        t.append("</table>")
                        out.append(f'<div class="rep-scroll">{"".join(t)}</div>')
                    continue
                i += 1
            return "".join(out)

        panels = []
        for fp in files:
            try:
                txt = open(fp, encoding="utf-8").read()
            except OSError:
                continue
            if not txt.strip():
                continue
            date_tag = os.path.basename(fp)[:-3]
            panels.append(f'<div class="panel" id="rep-{date_tag}">'
                          f'<h3>🐟 用量明细</h3>{render(txt)}</div>')
        if not panels:
            return ""
        return "".join(panels)
    rep_panel = usage_report_panel()
    if recs:
        last = recs[-1]
        upd = last["ts"]
        status = ('<span class="dsgood">接口正常</span>' if last.get("ok", True)
                  else '<span class="dsbad">接口受限</span>')
        hero = (f'<div class="sh-t">💰 DeepSeek 饭票</div>'
                f'<div class="sh-s">当前 {last["currency"]} {last["balance"]:.2f} · '
                f'截至 {upd} · {status}（每 10 分钟自动记录）</div>')
        chart = ds_chart_html(recs)
        main_panel = (f'<div class="panel"><h2 class="sec">余额走势（按日）</h2>'
                      + (chart if chart else '<div class="empty">记录还少，攒几天就有趋势了。</div>')
                      + '</div>')
        rows_html = "".join(
            f'<div class="dsrow"><span class="t">{r["ts"]}</span>'
            f'<span>¥{r["balance"]:.2f}（赠送 {r.get("granted", 0):.2f} / 充值 {r.get("topped", 0):.2f}）</span></div>'
            for r in reversed(recs[-10:]))
        detail_panel = (f'<div class="panel"><h3>🧾 最近记录</h3>{rows_html}</div>')
        about = ('<div class="panel"><h3>💰 关于饭票</h3>'
                 '<div class="about-txt">台账每 10 分钟向 DeepSeek 官方接口查询一次余额，'
                 '全量保留最近 14 天；走势图按每天最后一笔画。额度见底前留意充值。</div></div>')
        body = (hero, f'{ds_style}{rep_style}<div class="wrap2"><div class="grid2">'
                      f'<div>{main_panel}{usage_panel(recs)}{rep_panel}</div>'
                      f'<div class="side">{about}{detail_panel}</div></div></div>')
    else:
        hero = ('<div class="sh-t">💰 DeepSeek 饭票</div>'
                '<div class="sh-s">还没有记录，等下一次盘点。</div>')
        body = (hero, f'{ds_style}<div class="wrap2"><div class="panel">'
                      '<div class="empty">还没有余额记录，等下一次盘点。</div></div></div>')
    with open(f"{WWW}/balance.html", "w") as f:
        f.write(shell("balance", "DeepSeek 饭票", body,
                      extra_head='<meta http-equiv="refresh" content="600">'))

    # ---------- 搜索结果页（仿 zyod：提交跳转结果页，卡片列表） ----------
    sr_hero = ('<div class="sh-t">🔍 搜索</div>'
               '<div class="sh-s">搜全站：日记、榜单、台账、饭票</div>')
    sr_body = (
        '<div class="wrap2"><div class="panel" style="max-width:860px;margin:0 auto 20px">'
        '<h3 id="sr-head">搜索</h3><div id="sr-list"></div></div></div>'
        '<script>' + SEARCH_RESULT_JS + '</script>')
    with open(f"{WWW}/search.html", "w") as f:
        f.write(shell("search", "搜索", (sr_hero, sr_body)))

def diary_panel_html():
    entries = load_diary()
    if not entries:
        return '<div class="empty">还没有日记，等鱼今晚醒来。</div>'
    latest = entries[0]
    excerpt = re.sub(r"\s+", " ", re.sub(r"[#|>*\[\]()]+", " ", latest["body"]))[:120] + "……"
    more = f'<a class="entry" href="/diary.html"><div class="d">更早 {len(entries)-1} 篇</div><div class="t">翻日记本 →</div></a>' if len(entries) > 1 else ""
    return (f'<a class="entry" href="/diary.html"><div class="d">{latest["date"]}</div>'
            f'<div class="t">{latest["title"]}</div><div class="x">{excerpt}</div></a>{more}')

def ranktop_html():
    import glob as _glob
    files = sorted(_glob.glob(RANK_GLOB), reverse=True)
    if not files:
        return '<div class="empty">榜单还没生成，等明天早上。</div>'
    latest_date = os.path.basename(files[0]).replace(".md", "")
    sec = parse_rank(files[0])
    return rank_block({"all": sec.get("all", [])[:5]}) + \
        f'<div style="margin-top:10px"><a href="/rank.html" style="font-size:13.5px;color:var(--blue);text-decoration:none">看完整榜单（{latest_date}） →</a></div>'


# ---------- 采集 ----------
def scan_containers():
    out = sh("docker ps -a --format '{{.Names}}\\t{{.Image}}\\t{{.Status}}\\t{{.Ports}}'")
    items = {}
    for line in out.strip().splitlines():
        parts = line.split("\t")
        if len(parts) < 4: continue
        name, image, status, ports = parts[0], parts[1], parts[2], parts[3]
        pub = sorted(set(p.split("->")[0].split(":")[-1] for p in ports.split(",") if "->" in p))
        items[name] = {"type": "container", "image": image, "status": status, "ports": pub}
    return items

def scan_host_ports():
    out = sh("ss -tlnp | tail -n +2")
    items = {}
    for line in out.strip().splitlines():
        cols = line.split()
        if len(cols) < 5: continue
        addr, proc = cols[3], (cols[5] if len(cols) > 5 else "")
        if addr.startswith("127.") or addr.startswith("[::1]"): continue
        port = addr.rsplit(":", 1)[-1]
        if not port.isdigit() or port in ("53",): continue
        if addr.startswith("["):
            host = addr.split("]")[0].lstrip("[") if "]" in addr else addr
        else:
            host = addr.rsplit(":", 1)[0]
        pname = proc.split('"')[1] if '"' in proc else proc.split("=")[-1].strip('"')
        items[port] = {"type": "port", "proc": pname, "addr": host}
    return items

# ---------- 状态探测（供页面实时读取） ----------
def write_port_list(containers, hostports):
    lst, seen = [], set()
    for name, c in containers.items():
        for p in c.get("ports", []):
            if p in seen: continue
            seen.add(p)
            lst.append({"label": name, "port": int(p), "addr": "127.0.0.1"})
    for p, info in hostports.items():
        if p not in ("22",) and p not in seen:
            seen.add(p)
            lst.append({"label": info.get("proc", "?"), "port": int(p), "addr": info.get("addr", "127.0.0.1")})
    save(PORTLIST, lst)

# ---------- 备注 ----------
def build_rows(containers, hostports):
    notes = load(NOTES, {})
    rows = []
    for name, c in containers.items():
        note = notes.get("c:" + name, "")
        port = ", ".join(c["ports"]) if c["ports"] else "-"
        rows.append({"key": "c:" + name, "name": name, "kind": "容器",
                     "detail": c["image"], "port": port, "note": note})
    for p, info in hostports.items():
        if info["type"] != "port": continue
        key = "p:" + p
        if any(r["port"] == p for r in rows):  # 容器已占用该端口
            continue
        rows.append({"key": key, "name": notes.get("n:" + key, info["proc"]), "kind": "端口",
                     "detail": f"本机服务 {info['addr']}", "port": p, "note": notes.get(key, "")})
    return rows, notes

def diff(old_rows, new_rows):
    oldk = {r["key"] for r in old_rows}
    newk = {r["key"] for r in new_rows}
    added = [r for r in new_rows if r["key"] not in oldk]
    removed = [r for r in old_rows if r["key"] not in newk]
    return added, removed

def send_mail(subject, body):
    try:
        cfg = load(MAIL, {})
        if not cfg.get("enabled"): return
        sm = cfg["smtp"]
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = sm["user"]
        msg["To"] = cfg.get("to")
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(sm["host"], int(sm["port"]), context=ctx, timeout=20) as s:
            s.login(sm["user"], sm["pass"])
            s.sendmail(sm["user"], [cfg.get("to")], msg.as_string())
    except Exception as e:
        with open(f"{BASE}/scan.log", "a") as f:
            f.write(f"{time.strftime('%F %T')} mail error: {e}\n")

# ---------- DeepSeek 饭票 ----------
def collect_ds_balance():
    """每次盘点拉取一次余额追加记录；同一天只留最新一笔，失败写日志保持安静"""
    import urllib.request as _u
    key = ""
    try:
        for line in open(DS_ENV, encoding="utf-8"):
            line = line.strip()
            if line.startswith("DEEPSEEK_API_KEY=") or ("API_KEY" in line and "sk-" in line):
                cand = line.split("=", 1)[1].strip().strip('"').strip("'")
                if cand.startswith("sk-"):
                    key = cand
                    break
    except OSError:
        return
    if not key:
        return
    try:
        req = _u.Request("https://api.deepseek.com/user/balance",
                         headers={"Authorization": "Bearer " + key})
        with _u.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
        info = data.get("balance_infos", [{}])[0]
        rec = {"ts": time.strftime("%Y-%m-%d %H:%M"),
               "date": time.strftime("%Y-%m-%d"),
               "balance": float(info.get("total_balance", 0) or 0),
               "granted": float(info.get("granted_balance", 0) or 0),
               "topped": float(info.get("topped_up_balance", 0) or 0),
               "currency": info.get("currency", "CNY"),
               "ok": bool(data.get("is_available"))}
        recs = []
        if os.path.exists(DS_HIST):
            with open(DS_HIST) as f:
                recs = [json.loads(l) for l in f if l.strip()]
        recs.append(rec)
        cutoff = (time.strptime(rec["date"], "%Y-%m-%d") and time.strftime(
            "%Y-%m-%d", time.localtime(time.time() - 14 * 86400)))
        recs = [x for x in recs if x.get("date", "") >= cutoff]
        with open(DS_HIST, "w") as f:
            for x in recs[-3000:]:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
    except Exception as e:
        with open(f"{BASE}/scan.log", "a") as f:
            f.write(f"{time.strftime('%F %T')} ds-balance error: {e}\n")

def ds_balance_recs():
    if not os.path.exists(DS_HIST):
        return []
    with open(DS_HIST) as f:
        return [json.loads(l) for l in f if l.strip()]

def ds_chart_html(recs):
    """按日末笔余额画 SVG 折线：数值标注在数轴上，最新一笔放大标出；少于两条不给图"""
    daily = {}
    for r in recs:
        daily[r["date"]] = r
    pts = sorted(daily.values(), key=lambda x: x["date"])[-30:]
    if len(pts) < 2:
        return ""
    W, H, PL, PR, PT, PB = 640, 280, 78, 22, 32, 46
    vals = [r["balance"] for r in pts]
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    def X(i):
        return PL + i * (W - PL - PR) / (len(pts) - 1)
    def Y(v):
        return (H - PB) - (v - lo) / span * (H - PT - PB)
    grid = ""
    ys = []
    for gy in (lo, (lo + hi) / 2, hi):
        if all(abs(gy - s) > span / 50 for s in ys):
            ys.append(gy)
    for gy in ys:
        grid += (f'<line class="dsgrid" x1="{PL}" y1="{Y(gy):.1f}" x2="{W - 8}" y2="{Y(gy):.1f}"/>'
                 f'<text class="dsy" x="4" y="{Y(gy) + 6:.1f}">¥{gy:g}</text>')
    xs = ""
    for i in sorted({0, len(pts) // 2, len(pts) - 1}):
        xs += (f'<text class="dsx" x="{X(i):.1f}" y="{H - 12}" text-anchor="middle">'
               f'{pts[i]["date"][5:]}</text>')
    line = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(vals))
    dots = "".join(
        f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="3.4" fill="#0d9488"/>'
        for i, v in enumerate(vals))
    last = vals[-1]
    end = (f'<circle cx="{X(len(pts) - 1):.1f}" cy="{Y(last):.1f}" r="5.2" fill="#0d9488"/>'
           f'<text class="dslast" x="{X(len(pts) - 1):.1f}" y="{Y(last) - 18:.1f}" '
           f'text-anchor="end">¥{last:g}</text>')
    return (f'<div class="dschart"><svg viewBox="0 0 {W} {H}" role="img" aria-label="余额走势">'
            f'{grid}<polyline points="{line}" fill="none" stroke="#0d9488" stroke-width="2.6" '
            f'stroke-linejoin="round" stroke-linecap="round"/>{dots}{end}{xs}</svg></div>')

# ---------- 系统信息 ----------
def collect_sysinfo():
    mem = {"total": 0, "used": 0, "pct": 0}
    try:
        info = {}
        for line in open("/proc/meminfo"):
            k, v = line.split(":")
            info[k] = int(v.strip().split()[0])  # kB
        total = info["MemTotal"]; avail = info["MemAvailable"]
        used = total - avail
        mem = {"total": total / 1048576, "used": used / 1048576,
               "pct": round(used / total * 100, 1)}
    except Exception:
        pass
    disk = {"total": 0, "used": 0, "pct": 0, "avail": 0}
    try:
        out = sh("df -m / --output=size,used,avail,pcent | tail -1").split()
        disk = {"total": int(out[0]) / 1024, "used": int(out[1]) / 1024,
                "pct": float(out[3].rstrip("%")), "avail": int(out[2]) / 1024}
    except Exception:
        pass
    load = "0"
    try:
        load = open("/proc/loadavg").read().split()[0]
    except Exception:
        pass
    ncpu = os.cpu_count() or 1
    cpu = 0.0
    try:
        def _csnap():
            return list(map(int, open("/proc/stat").readline().split()[1:]))
        _a = _csnap(); time.sleep(0.25); _b = _csnap()
        _d = [y - x for x, y in zip(_a, _b)]
        _tot = sum(_d)
        if _tot > 0:
            cpu = max(0.0, min(100.0, (_tot - _d[3]) / _tot * 100))
    except Exception:
        pass
    up = ""
    try:
        secs = float(open("/proc/uptime").read().split()[0])
        d, h = int(secs // 86400), int(secs % 86400 // 3600)
        up = f"{d} 天 {h} 小时" if d else f"{h} 小时"
    except Exception:
        pass
    osname, kernel = "", ""
    try:
        for line in open("/etc/os-release"):
            if line.startswith("PRETTY_NAME="):
                osname = line.split("=", 1)[1].strip().strip('"')
    except Exception:
        pass
    try:
        kernel = subprocess.run(["uname", "-r"], capture_output=True, text=True).stdout.strip()
    except Exception:
        pass
    return {"mem": mem, "disk": disk, "load": load, "ncpu": ncpu, "up": up,
            "cpu": cpu, "os": osname, "kernel": kernel}

# ---------- 页面 ----------
TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><meta http-equiv="Cache-Control" content="no-store"><meta http-equiv="Pragma" content="no-cache">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script>try{var _t=localStorage.getItem("fish-theme");if(!_t)_t=matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";if(_t==="dark")document.documentElement.classList.add("dark")}catch(e){}</script>
<title>服务器台账 · 鱼窝</title>
<style>
:root{
  --ink:#1e293b;--soft:#64748b;--line:#e2e8f0;
  --teal:#0d9488;--teal-bg:#ecfdf5;--red:#dc2626;--red-bg:#fef2f2;
  --blue:#2563eb;--blue-bg:#eff6ff;--amber:#d97706;--amber-bg:#fffbeb;
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
  background:#eef2f6;color:var(--ink);font-size:15.5px;line-height:1.65;
  -webkit-font-smoothing:antialiased;min-height:100vh}
/* --- 门户顶栏：品牌 + 导航 + 搜索，滚动常驻（全站统一） --- */
__TOPBAR_CSS__
.wrap{max-width:1140px;margin:22px auto 0;padding:0 16px 50px}
.grid{display:grid;grid-template-columns:1fr;gap:20px;align-items:start}
@media(min-width:1020px){.grid{grid-template-columns:1fr 292px}}
.side{display:grid;gap:14px;align-content:start}
.side .panel{padding:16px 18px;margin-bottom:0}
.side h3{font-size:13px;color:var(--soft);font-weight:700;letter-spacing:1px;
  margin-bottom:12px;display:flex;align-items:center;gap:7px}
.kv{display:flex;justify-content:space-between;font-size:13.5px;padding:5px 0}
.kv span{color:var(--soft)}
.kv b{font-weight:600;font-family:ui-monospace,"SF Mono",Consolas,monospace;font-size:13px}
.bar{margin:9px 0 3px}
.bar .lb{display:flex;justify-content:space-between;font-size:12.5px;color:var(--soft);margin-bottom:4px}
.bar .lb b{color:var(--ink);font-weight:600}
.bar .track{height:7px;border-radius:4px;background:#eef2f6;overflow:hidden}
.bar .fill{height:100%;border-radius:4px;background:var(--teal);transition:width .4s}
.bar .fill.warn{background:var(--amber)}
.bar .fill.hot{background:var(--red)}
.quick{display:grid;gap:8px}
.quick a{display:flex;align-items:center;gap:10px;padding:9px 12px;border:1px solid var(--line);
  border-radius:10px;text-decoration:none;color:var(--ink);font-size:14px;font-weight:600;
  transition:border-color .15s,background .15s}
.quick a:hover{border-color:var(--blue);background:var(--blue-bg)}
.quick a span{font-size:16px}
.quick a small{margin-left:auto;color:var(--soft);font-weight:400;font-size:12px;
  font-family:ui-monospace,Consolas,monospace}
.plan{font-size:13.5px;color:var(--soft);line-height:1.8}
.plan b{color:var(--ink)}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:18px}
.card{background:#fff;border:1px solid var(--line);border-radius:14px;padding:14px 16px;
  box-shadow:0 1px 3px rgba(15,23,42,.06);cursor:pointer}
.card b{display:block;font-size:26px;font-weight:700;letter-spacing:-.5px}
.card span{font-size:12.5px;color:var(--soft)}
.card.hl b{color:var(--teal)}
.card:nth-child(1){background:linear-gradient(135deg,#ecfdf5,#f0fdfa);border-color:#a7f3d0}
.card:nth-child(1) b{color:var(--teal)}
.card:nth-child(2){background:linear-gradient(135deg,#eff6ff,#f5f9ff);border-color:#bfdbfe}
.card:nth-child(2) b{color:var(--blue)}
.card:nth-child(3){background:linear-gradient(135deg,#fffbeb,#fffde8);border-color:#fde68a}
.card:nth-child(3) b{color:#b45309}
.card:nth-child(4){background:linear-gradient(135deg,#f8fafc,#f1f5f9);border-color:#dbe2ea}
.card:nth-child(4) b{color:#475569}
.panel{background:#fff;border:1px solid var(--line);border-radius:16px;
  box-shadow:0 1px 4px rgba(15,23,42,.05);padding:20px 22px;margin-bottom:20px;overflow-x:auto}
.panel-head{display:flex;align-items:center;justify-content:space-between;gap:12px;
  flex-wrap:wrap;margin-bottom:14px}
.panel-head h2{font-size:16.5px;display:flex;align-items:center;gap:8px}
.panel-head h2::before{content:"";width:4px;height:16px;border-radius:2px;background:var(--blue)}
.btn{background:var(--blue);color:#fff;border:none;border-radius:9px;padding:7px 16px;
  font-size:13.5px;cursor:pointer;transition:filter .15s,transform .12s,opacity .15s}
.btn:hover{filter:brightness(1.1)}
.btn:active{transform:scale(.95)}
.btn.loading{pointer-events:none;opacity:.75;animation:btnpulse .7s ease infinite}
@keyframes btnpulse{50%{filter:brightness(1.35)}}
body{animation:pgfadein .3s ease}
@keyframes pgfadein{from{opacity:0}to{opacity:1}}
.heronav a,.quick a,a.svc-link,a.btn{transition:transform .12s ease,background .15s,color .15s,border-color .15s}
.heronav a:active,.quick a:active,a.svc-link:active,a.btn:active{transform:scale(.94)}
a.svc-link{display:inline-block}
table{width:100%;border-collapse:collapse;font-size:14.5px}
th{color:var(--soft);font-weight:600;font-size:12px;text-align:left;padding:0 12px 11px;
  border-bottom:1px solid var(--line);letter-spacing:1px;white-space:nowrap}
td{padding:13px 12px;border-bottom:1px solid #f1f5f9;vertical-align:middle}
tr:last-child td{border-bottom:none}
tbody tr{transition:background .12s}
tbody tr:hover{background:#f8fafc}
.asset-t{table-layout:fixed}
.asset-t th:nth-child(1),.asset-t td:nth-child(1){width:90px}
.asset-t th:nth-child(3),.asset-t td:nth-child(3){width:80px}
.asset-t th:nth-child(4),.asset-t td:nth-child(4){width:88px;text-align:right}
.asset-t th:last-child,.asset-t td:last-child{width:27%}
.asset-t td:nth-child(4) .mono{display:block}
.svc{font-weight:600;font-size:15px;line-height:1.55;word-break:break-word}
a.svc-link{color:var(--ink);text-decoration:none;border-bottom:1px dashed #93c5fd}
a.svc-link:hover{color:var(--blue);border-bottom-color:var(--blue)}
.kind{display:inline-block;padding:1.5px 9px;border-radius:999px;font-size:12px;
  background:var(--blue-bg);color:var(--blue);white-space:nowrap}
.kind.port{background:var(--amber-bg);color:var(--amber)}
.pill{display:inline-flex;align-items:center;gap:6px;padding:3px 11px;border-radius:999px;
  font-size:12.5px;font-weight:600;white-space:nowrap}
.pill.on{background:var(--teal-bg);color:var(--teal)}
.pill.off{background:var(--red-bg);color:var(--red)}
.pill.na{background:#f1f5f9;color:var(--soft)}
.pill .dot{width:7px;height:7px;border-radius:50%;background:currentColor}
.mono{font-family:ui-monospace,"SF Mono",Consolas,monospace;font-size:13px;color:var(--soft);
  font-variant-numeric:tabular-nums;letter-spacing:.2px}
.note-cell{color:var(--soft);font-size:13.5px;line-height:1.6}
.offline td{color:var(--soft)}
.offline .svc{font-weight:500;color:var(--soft)}
.offline .when{color:var(--soft);font-size:13px}
.hist{font-size:13.5px;color:var(--soft)}
.timeline{position:relative;max-height:340px;overflow-y:auto;padding-left:30px;margin:4px 0 2px}
.timeline::-webkit-scrollbar{width:5px}
.timeline::-webkit-scrollbar-thumb{background:#cbd5e1;border-radius:3px}
.tl-item{position:relative;padding:0 0 18px 14px}
.tl-item:last-child{padding-bottom:4px}
.tl-item::before{content:"";position:absolute;left:-30px;top:4px;width:11px;height:11px;
  border-radius:50%;background:#94a3b8;border:2.5px solid #fff;box-shadow:0 0 0 1.5px #cbd5e1}
.tl-item.add::before{background:var(--teal);box-shadow:0 0 0 1.5px #6ee7d7}
.tl-item.remove::before{background:var(--red);box-shadow:0 0 0 1.5px #fca5a5}
.tl-item::after{content:"";position:absolute;left:-25px;top:20px;bottom:-2px;width:2px;
  background:linear-gradient(180deg,#e2e8f0,#eef2f6)}
.tl-item:last-child::after{display:none}
.tl-time{font-family:ui-monospace,"SF Mono",Consolas,monospace;font-size:12px;color:#94a3b8;letter-spacing:.3px}
.tl-text{color:var(--ink);font-size:14px;margin-top:1px}
.tl-text .tag-add{color:var(--teal);font-weight:600}
.tl-text .tag-remove{color:var(--red);font-weight:600}
footer{max-width:900px;margin:0 auto;padding:0 16px 40px;font-size:13.5px;text-align:center;letter-spacing:.3px;
  background:linear-gradient(90deg,#8b5cf6 0%,#3b82f6 45%,#14b8a6 100%);
  -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
footer .up,footer .vw{font-weight:700}
/* ---------- 日记与榜单卡片 ---------- */
a.btn{display:inline-block;text-decoration:none}
.entries{display:grid;gap:10px}
.entry{display:block;text-decoration:none;background:#fff;border:1px solid var(--line);
  border-radius:14px;padding:14px 18px;transition:border-color .15s,box-shadow .15s}
.entry:hover{border-color:var(--teal);box-shadow:0 2px 10px rgba(13,148,136,.08)}
.entry .d{font-size:12.5px;color:var(--teal);font-weight:700;letter-spacing:1px}
.entry .t{font-size:15.5px;font-weight:700;margin:2px 0 5px;color:var(--ink)}
.entry .x{font-size:13.5px;color:var(--soft);display:-webkit-box;-webkit-line-clamp:2;
  -webkit-box-orient:vertical;overflow:hidden}
.repo{display:block;text-decoration:none;padding:11px 4px;border-bottom:1px solid #f1f5f9}
.repo:last-child{border-bottom:none}
.repo .r1{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
.repo .nm{font-weight:700;font-size:15px;color:var(--ink)}
.repo .nm:hover{color:var(--blue)}
.repo .stars{font-size:12px;color:#b45309;background:#fffbeb;border-radius:999px;padding:1px 9px;font-weight:600}
.repo .delta{font-size:12px;color:var(--teal);background:#ecfdf5;border-radius:999px;padding:1px 9px;font-weight:600}
.repo .sm{font-size:13.5px;color:var(--soft);margin-top:3px}
details.sec-blk{background:#fff;border:1px solid var(--line);border-radius:14px;
  padding:12px 18px;margin-bottom:12px}
details.sec-blk summary{cursor:pointer;font-weight:700;font-size:15px;list-style:none}
details.sec-blk summary::before{content:"▸";color:var(--soft);margin-right:8px;display:inline-block;
  transition:transform .15s}
details.sec-blk[open] summary::before{transform:rotate(90deg)}
.empty{color:var(--soft);font-size:14px;padding:16px 0}
/* ---------- 手机端：表格变卡片 ---------- */
@media(max-width:680px){
  .cards{grid-template-columns:repeat(2,1fr);gap:10px}
  .card{padding:11px 14px;display:flex;align-items:baseline;gap:9px}
  .card b{font-size:23px}
  .card span{font-size:13px}
  .grid{display:flex;flex-direction:column;align-items:stretch}
  .main,.side{display:contents}
  .side .panel:nth-child(1){order:1}
  .side .panel:nth-child(2){order:2}
  .side .panel:nth-child(3){order:3}
  .side .panel:nth-child(4){order:4}
  .main .panel:nth-child(1){order:5}
  .main .panel:nth-child(2){order:6}
  .main .panel:nth-child(3){order:7}
  .panel{padding:16px 14px;border-radius:13px}
  table{display:block}
  thead{display:none}
  tbody{display:block}
  tbody tr{display:block;border:1px solid var(--line);border-radius:14px;
    padding:11px 14px 10px;margin-bottom:12px;background:#fff;box-shadow:0 1px 2px rgba(15,23,42,.04)}
  tbody tr:hover{background:#fff}
  td{display:flex;justify-content:space-between;align-items:flex-start;gap:14px;
    border-bottom:0;padding:3.5px 0}
  td::before{content:attr(data-label);color:#94a3b8;font-size:12px;flex-shrink:0;
    padding-top:2.5px;font-weight:600}
  td:last-child{border-top:1px dashed #f1f5f9;margin-top:6px;padding-top:8px}
  .asset-t td,.asset-t th{width:auto!important;text-align:left}
  .svc,.mono,.note-cell{text-align:right}
  .note-cell{flex:1;max-width:none}
  .pill{margin-left:auto}
  .kind{margin-left:auto}
  .hist .line{flex-direction:column;gap:1px}
}

/* --- 移动端侧边菜单 --- */
.mtop,.mmask,.mdrawer{display:none}
@media(max-width:680px){
  .entries{grid-template-columns:minmax(0,1fr);gap:10px}
  .heronav{display:none}
  .topbar{display:none}
  .mtop{display:flex;align-items:center;gap:8px;position:sticky;top:0;z-index:60;
    background:rgba(15,23,42,.96);backdrop-filter:blur(8px);color:#fff;padding:11px 14px}
  .mt-burger{display:flex;flex-direction:column;justify-content:center;gap:4px;background:none;
    border:0;padding:8px 8px 8px 2px;cursor:pointer}
  .mt-burger span{display:block;width:20px;height:2px;border-radius:2px;background:#fff}
  .mt-title{font-size:15.5px;font-weight:700;letter-spacing:.3px}
  .mt-search{margin-left:auto;background:none;border:0;color:#fff;font-size:18px;padding:6px 2px 6px 6px;cursor:pointer;-webkit-tap-highlight-color:transparent}
  .mt-search:active{opacity:.7}
  .fsbox-hero{display:none}
  .mdrawer{display:flex;flex-direction:column;position:fixed;top:0;left:0;bottom:0;width:64%;max-width:232px;z-index:100;
    background:rgba(255,255,255,.78);backdrop-filter:blur(32px) saturate(1.5);-webkit-backdrop-filter:blur(32px) saturate(1.5);box-shadow:2px 0 18px rgba(15,23,42,.28);transform:translateX(-106%);
    transition:transform .5s cubic-bezier(.16,1,.3,1) .2s;overflow-y:auto;overscroll-behavior:contain;border-radius:0 18px 18px 0}
  body.drawer-open .mdrawer{transform:none;transition:transform .9s cubic-bezier(.16,1,.3,1);transition-delay:0s}
  .mmask{display:block;position:fixed;inset:0;background:rgba(15,23,42,.45);z-index:90;
    opacity:0;pointer-events:none;transition:opacity .45s}
  body.drawer-open .mmask{opacity:1;pointer-events:auto}
  body.drawer-open{overflow:hidden;overscroll-behavior:contain}
  .md-hero{background:linear-gradient(135deg,#0f172a,#155e63);color:#fff;padding:24px 20px 18px}
  .md-t{font-size:17.5px;font-weight:700}
  .md-sub{font-size:12.5px;color:rgba(255,255,255,.72);margin-top:5px}
  .md-nav{padding:8px 0}
  .md-nav a{display:flex;align-items:center;gap:10px;padding:13px 20px;color:var(--ink);
    text-decoration:none;font-size:15px;font-weight:600;border-bottom:1px solid #eef2f6}
  .md-nav a:last-child{border-bottom:0}
  .md-nav a:active{background:#f1f5f9}
  .md-nav .md-n{margin-left:auto;min-width:22px;height:22px;padding:0 7px;border-radius:999px;background:#f1f5f9;color:var(--soft);font-size:11.5px;font-weight:700;display:flex;align-items:center;justify-content:center;flex:none}
  .md-nav a.cur .md-n,.md-nav a.on .md-n{background:var(--teal);color:#fff}
  html.dark .md-nav .md-n{background:#1a2740;color:#8b98a9}
  html.dark .md-nav a.cur .md-n,html.dark .md-nav a.on .md-n{background:var(--teal);color:#fff}
  .md-nav a{opacity:0;transform:translateX(-26px);transition:opacity .6s ease,transform .75s cubic-bezier(.16,1,.3,1),background .2s}
  body.drawer-open .md-nav a{opacity:1;transform:none}
  .md-nav a:nth-child(1){transition-delay:.10s}
  .md-nav a:nth-child(2){transition-delay:.19s}
  .md-nav a:nth-child(3){transition-delay:.28s}
  .md-nav a:nth-child(4){transition-delay:.37s}
  .md-nav a:nth-child(5){transition-delay:.46s}
  body:not(.drawer-open) .md-nav a:nth-child(1){transition-delay:.20s;transition-duration:.25s}
  body:not(.drawer-open) .md-nav a:nth-child(2){transition-delay:.15s;transition-duration:.25s}
  body:not(.drawer-open) .md-nav a:nth-child(3){transition-delay:.10s;transition-duration:.25s}
  body:not(.drawer-open) .md-nav a:nth-child(4){transition-delay:.05s;transition-duration:.25s}
  body:not(.drawer-open) .md-nav a:nth-child(5){transition-delay:0s;transition-duration:.25s}
  .md-foot{margin-top:auto;flex:none;padding:14px 16px calc(16px + env(safe-area-inset-bottom,0px))}
  .md-theme{display:flex;align-items:center;justify-content:space-between;gap:10px;width:100%;background:#f1f5f9;border:1px solid #dbe3ec;border-radius:14px;padding:11px 14px;color:var(--ink);font-size:15px;font-weight:600;cursor:pointer;box-shadow:0 1px 3px rgba(15,23,42,.07);-webkit-tap-highlight-color:transparent;outline:none;transition:background .2s}
  .md-theme:active{background:#e6ecf3}
  .md-sw{position:relative;width:48px;height:28px;border-radius:999px;background:#b9c3d0;transition:background .3s;flex:none;box-shadow:inset 0 1px 3px rgba(15,23,42,.18)}
  .md-sw::after{content:"";position:absolute;top:3px;left:3px;width:20px;height:20px;border-radius:50%;background:#fff;box-shadow:0 1px 4px rgba(15,23,42,.3);transition:transform .3s cubic-bezier(.22,1,.36,1)}
  html.dark .md-sw{background:var(--teal)}
  html.dark .md-sw::after{transform:translateX(20px)}
  .md-hero,.md-nav{flex:none}
  html.dark .md-theme{background:#1a2740;border-color:#263552;box-shadow:none}
  html.dark .md-theme:active{background:#22334f}
}
.tmoon{position:fixed;left:18px;bottom:26px;width:42px;height:42px;border-radius:50%;
  background:rgba(255,255,255,.92);border:1px solid var(--line);box-shadow:0 2px 8px rgba(15,23,42,.18);
  font-size:18px;line-height:1;cursor:pointer;z-index:85;display:flex;align-items:center;justify-content:center;
  transition:transform .2s}
.tmoon:active{transform:scale(.92)}
.tmoon:focus{outline:none}
@media(max-width:680px){.tmoon{display:none}}
html.dark .tmoon{background:rgba(38,50,67,.9);border-color:#263243}
html.dark body{background:#0b1220;color:#d7dde6}
html.dark{--ink:#d7dde6;--soft:#8b98a9;--line:#263243}
html.dark .panel{background:#111a2b;border-color:#263243}
html.dark .card{background:#111a2b!important;border-color:#263243!important}
html.dark th{color:#8b98a9;border-bottom-color:#263243}
html.dark td{border-bottom-color:#1a2740}
html.dark tbody tr:hover{background:#141f33}
html.dark .svc,html.dark .kv b{color:#e5ecf5}
html.dark .mono,html.dark .note-cell,html.dark .tl-time,html.dark .hist,html.dark .plan{color:#8b98a9}
html.dark .plan b{color:#e5ecf5}
html.dark .bar .track{background:#1a2740}
html.dark .tl-text{color:#d7dde6}
html.dark .mdrawer{background:rgba(17,26,43,.78);backdrop-filter:blur(32px) saturate(1.4);-webkit-backdrop-filter:blur(32px) saturate(1.4)}
html.dark .md-nav a{color:#d7dde6;border-bottom-color:#1a2740}
html.dark footer{color:#8b98a9}
/* --- 顶部导航与标题（与日记等二级页统一） --- */
.pagebar{position:sticky;top:0;z-index:50;background:rgba(15,23,42,.94);backdrop-filter:blur(8px);
  color:#fff;padding:10px 18px}
.pbin{max-width:1000px;margin:0 auto;display:flex;align-items:center;gap:16px}
.pagebar a{color:rgba(255,255,255,.75);text-decoration:none;font-size:14px;padding:3px 10px;
  border-radius:999px;transition:background .15s,color .15s,transform .12s}
.pagebar a:active{transform:scale(.94)}
.pagebar a:hover{color:#fff;background:rgba(255,255,255,.12)}
.pagebar a.on{background:#fff;color:#0f172a;font-weight:700}
.pagebar b{margin-left:auto;font-size:14.5px;font-weight:600}
.pb-brand{font-weight:700;font-size:15px;letter-spacing:.3px}
.pb-cur{display:none}
.subhero{background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 55%,#155e63 100%);
  color:#fff;padding:26px 18px 24px;display:flex;align-items:center;min-height:120px}
.subhero-in{max-width:1000px;margin:0 auto;width:100%}
.sh-t{font-size:21px;font-weight:700;letter-spacing:.4px}
.sh-s{color:rgba(255,255,255,.75);font-size:13.5px;margin-top:6px}
.pburger{display:none}
@media(max-width:680px){
  .pbin{gap:7px;flex-wrap:wrap}
  .pagebar{padding:9px 14px}
  .pb-brand{display:none}
  .pbin a{display:none}
  .pbin a.pb-back{display:inline-block;font-size:19px;font-weight:700;
    padding:2px 12px 2px 4px;line-height:1.4}
  .pb-bt{display:none}
  .pb-cur{display:inline;font-size:14.5px;font-weight:700;color:#fff}
  .subhero{padding:20px 16px 18px;min-height:134px}
  .pburger{display:flex;flex-direction:column;justify-content:center;gap:4px;background:none;
    border:0;padding:8px 8px 8px 2px;cursor:pointer}
  .pburger span{display:block;width:20px;height:2px;border-radius:2px;background:#fff}
  .pburger:active{opacity:.7}
}
/* ---------- 测试版新增 ---------- */.crumbwrap{max-width:1000px;margin:0 auto;padding:12px 18px 0}.crumb{font-size:13px;color:var(--soft)}.crumb a{color:var(--soft);text-decoration:none}.crumb a:hover{color:var(--teal)}.crumb .c-sep{margin:0 8px;color:#cbd5e1}.crumb b{color:var(--ink);font-weight:600}.fsbox{position:relative;margin-left:auto;flex-shrink:1}.fsbox input{width:170px;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.2);color:#fff;border-radius:999px;padding:6px 16px;font-size:13.5px;outline:none;transition:width .25s,background .2s;-webkit-appearance:none;appearance:none}.fsbox input::placeholder{color:rgba(255,255,255,.55)}.fsbox input:focus{width:210px;background:rgba(255,255,255,.18)}.fs-drop{display:none;position:absolute;right:0;top:calc(100% + 8px);width:min(320px,86vw);background:#fff;border:1px solid var(--line);border-radius:14px;box-shadow:0 12px 34px rgba(15,23,42,.18);overflow:hidden;z-index:120}.fs-drop.on{display:block}.fs-drop a{display:flex;align-items:center;gap:10px;padding:10px 14px;text-decoration:none;font-size:13.5px;color:var(--ink);border-bottom:1px solid #f1f5f9}.fs-drop a:last-child{border-bottom:none}.fs-drop a:active,.fs-drop a:hover{background:#f6fbfa}.fs-k{flex:none;font-size:11px;color:#0d9488;background:#ecfdf5;border-radius:999px;padding:1px 8px;font-weight:700}.fs-t{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.fs-t b{color:var(--teal)}.fs-empty{padding:14px;font-size:13px;color:var(--soft);text-align:center}html.dark .fs-drop{background:#111a2b;border-color:#263243}html.dark .fs-drop a{color:#d7dde6;border-bottom-color:#1a2740}html.dark .fs-drop a:active,html.dark .fs-drop a:hover{background:#16223a}html.dark .fs-k{background:#0e2a2b;color:#5eead4}html.dark .crumb b{color:#e5ecf5}@media(max-width:680px){.fsbox input{width:120px;padding:5px 12px;font-size:13px}.fsbox input:focus{width:150px}}@media(max-width:768px){input,select,textarea{font-size:16px!important}}.fs-tt{font-weight:600;display:block}.fs-s{color:var(--soft);font-size:12px;white-space:normal;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}html.dark .fs-s{color:#8b98a9}.codewin{margin:14px 0;border-radius:12px;overflow:hidden;background:#0f172a;border:1px solid #1e2b3d}.cw-bar{display:flex;align-items:center;gap:10px;padding:8px 12px;background:rgba(255,255,255,.05)}.cw-dots i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px}.cw-dots i:nth-child(1){background:#ff5f57}.cw-dots i:nth-child(2){background:#febc2e}.cw-dots i:nth-child(3){background:#28c840}.cw-lang{font-size:11.5px;color:#8b98a9;letter-spacing:.5px;font-family:ui-monospace,Consolas,monospace}.cw-copy{margin-left:auto;background:rgba(255,255,255,.1);border:none;color:#cbd5e1;font-size:12px;padding:3px 12px;border-radius:999px;cursor:pointer;-webkit-appearance:none;appearance:none}.cw-copy:active{transform:scale(.95)}.codewin pre{margin:0;padding:12px 14px;background:transparent!important;overflow-x:auto}.codewin pre code{color:#d7e3f0;font-size:13px}.codewin pre::-webkit-scrollbar{height:4px}__SEARCH_CSS__</style></head>
<body>
<div class="mmask" id="mmask" onclick="drawerOff()"></div>
<aside class="mdrawer" id="mdrawer">
  <div class="md-hero"><div class="md-t">🐟 鱼窝</div>
    <div class="md-sub">鱼的日记 · 榜单 · 服务器台账</div></div>
  <nav class="md-nav">
    <a href="/index.html">🏠 首页</a>
    <a href="/diary.html">📖 鱼的日记<span class="md-n">__N_DIARY__</span></a>
    <a href="/rank.html">📈 GitHub 榜单<span class="md-n">__N_RANK__</span></a>
    <a href="/balance.html">💰 DeepSeek 饭票<span class="md-n">__N_DS__</span></a>
    <a href="/ledger.html">🗂 服务器台账<span class="md-n">__N_LEDGER__</span></a>
  </nav>
  <div class="md-foot"><button class="md-theme" type="button" onclick="themeToggle()"><span>🌙 深色模式</span><span class="md-sw"></span></button></div>
</aside>
<div class="pagebar"><div class="pbin"><span class="pb-brand">🐟 鱼窝</span><a class="pb-back" href="/index.html">← <span class="pb-bt">返回鱼窝</span></a><a href="/diary.html">📖 鱼的日记</a><a href="/rank.html">📈 GitHub 榜单</a><a href="/balance.html">💰 DeepSeek 饭票</a><a class="on" href="/ledger.html">🗂 服务器台账</a><b class="pb-cur">🗂 服务器台账</b>__SEARCH_BTN__<button class="pburger" type="button" aria-label="菜单" onclick="drawerOn()"><span></span><span></span><span></span></button></div></div>
<div class="subhero"><div class="subhero-in"><div class="sh-t">🗂 服务器台账</div><div class="sh-s">共 __N_TOTAL__ 条资产 · __N_CONT__ 个容器 · __N_PORTS__ 对外端口 · 最近盘点 __SCAN_TIME__</div></div></div>
<div class="wrap">
  <div class="cards">
    <div class="card hl" onclick="goAssets()"><b>__N_TOTAL__</b><span>资产条目</span></div>
    <div class="card" onclick="goAssets()"><b>__N_CONT__</b><span>容器</span></div>
    <div class="card" onclick="goAssets()"><b>__N_PORTS__</b><span>对外端口</span></div>
    <div class="card" onclick="goAssets()"><b>__N_OFF__</b><span>已下线</span></div>
  </div>

  <div class="grid">
  <div class="main">
  <div class="panel" id="assets">
    <div class="panel-head">
      <h2>在册资产</h2>
      <button class="btn" onclick="doRefresh()">刷新实时状态</button>
    </div>
    <table class="asset-t">
      <thead><tr><th>状态</th><th>名称</th><th>类型</th><th>端口</th><th class="hide-m">详情</th><th>备注</th></tr></thead>
      <tbody>__ROWS__</tbody>
    </table>
  </div>

  <div class="panel">
    <div class="panel-head"><h2>已下线（待确认）</h2></div>
    <table>
      <thead><tr><th>名称</th><th>类型</th><th>端口</th><th>下线时间</th></tr></thead>
      <tbody>__OFFROWS__</tbody>
    </table>
  </div>

  <div class="panel">
    <div class="panel-head"><h2>最近变更</h2></div>
    __HIST__
  </div>
  </div>

  <div class="side">
  __SIDEBAR__
  </div>
  </div>
</div>
<footer><span class="up">__UPTIME__</span><span id="views"></span></footer>
__SEARCH_PANEL__
<button class="tmoon" type="button" aria-label="切换黑夜模式" onclick="themeToggle()">🌙</button>
<script>
__SEARCH_SCRIPT__
var ports=__PORTS__;
function paint(st){
  document.querySelectorAll("[data-port]").forEach(el=>{
    const p=el.getAttribute("data-port");const v=st[p];
    if(v==="on"){el.className="pill on";el.querySelector(".st").textContent="在线";}
    else if(v==="off"){el.className="pill off";el.querySelector(".st").textContent="未响应";}
    else{el.className="pill na";el.querySelector(".st").textContent="—";}
  });
}
async function refresh(){
  try{const r=await fetch("/cgi-bin/status?ts="+Date.now());const j=await r.json();paint(j);}
  catch(e){document.querySelectorAll(".st").forEach(t=>{t.textContent="—";});}
}
refresh();if(window.__stT)clearInterval(window.__stT);window.__stT=setInterval(refresh,60000);
function paintHealth(p, pct, used, total){
  const b=document.getElementById('h-'+p+'-pct');
  if(b) b.textContent=Math.round(pct)+'%'+(total?('('+((p==='mem'?used.toFixed(1):Math.round(used)))+'/'
    +(p==='mem'?total.toFixed(1):Math.round(total))+' GB)'):'');
  const f=document.getElementById('h-'+p+'-fill');
  if(f){f.style.width=Math.min(pct,100)+'%';
    f.className='fill '+((pct>=90)?'hot':((pct>=75)?'warn':''));}
  const rg=document.getElementById('g-'+p+'-ring');
  if(rg){rg.style.strokeDashoffset=(251.3*(1-Math.min(pct,100)/100)).toFixed(1);
    rg.setAttribute('class','g-fg '+((pct>=90)?'hot':((pct>=75)?'warn':'')));}
  const gn=document.getElementById('g-'+p+'-num');if(gn)gn.textContent=Math.round(pct)+'%';
  const gs=document.getElementById('g-'+p+'-sub');
  if(gs)gs.textContent=(p==='mem'?used.toFixed(1):Math.round(used))+'/'+(p==='mem'?total.toFixed(1):Math.round(total))+' GB';
}
async function refreshHealth(){
  try{const r=await fetch("/cgi-bin/health?ts="+Date.now());const j=await r.json();
    if(j.mem&&j.mem.total)paintHealth('mem',j.mem.pct,j.mem.used,j.mem.total);
    if(j.disk&&j.disk.total)paintHealth('disk',j.disk.pct,j.disk.used,j.disk.total);
    const ld=document.getElementById('h-load');if(ld)ld.textContent=j.load;
    const pin=document.getElementById('h-load-pin');
    if(pin&&j.load){const v=Math.min(Math.max(parseFloat(j.load)||0,0),3);pin.style.left=(v/3*100).toFixed(2)+'%';const bv=document.getElementById('h-load-val');if(bv){bv.style.left=Math.min(Math.max(v/3*100,7),93).toFixed(2)+'%';bv.textContent=parseFloat(j.load).toFixed(2);}}
    const up=document.getElementById('h-up');if(up&&j.up)up.textContent=j.up;
  }catch(e){}
}
refreshHealth();if(window.__htT)clearInterval(window.__htT);window.__htT=setInterval(refreshHealth,60000);
async function doRefresh(){
  const btn=document.querySelector('.btn');
  if(!btn||btn.classList.contains('loading'))return;
  btn.classList.add('loading');btn.textContent='刷新中…';
  try{await Promise.all([refresh(),refreshHealth()]);}catch(e){}
  btn.textContent='已刷新 ✓';
  setTimeout(()=>{btn.textContent='刷新实时状态';btn.classList.remove('loading')},900);
}
try{fetch('/cgi-bin/visit').then(r=>r.json()).then(j=>{
  const el=document.getElementById('views');
  if(el) el.innerHTML=' · <span class="vw">累计到访 '+j.views+' 次</span>';
}).catch(()=>{const el=document.getElementById('views');if(el)el.style.display='none';});}catch(e){}
function drawerOn(){document.body.classList.add('drawer-open')}
function drawerOff(){document.body.classList.remove('drawer-open')}
function goAssets(){var el=document.getElementById('assets');if(el)el.scrollIntoView({behavior:'smooth'});}
function themeToggle(){var d=document.documentElement.classList.toggle("dark");
try{localStorage.setItem("fish-theme",d?"dark":"light")}catch(e){}
var b=document.querySelectorAll(".tmoon");for(var i=0;i<b.length;i++)b[i].textContent=d?"☀️":"🌙";}
(function(){var b=document.querySelector(".tmoon");
if(b)b.textContent=document.documentElement.classList.contains("dark")?"☀️":"🌙";})();
</script>
<script>__SEARCH_JS__(function(){document.addEventListener("click",function(e){
var b=e.target.closest?e.target.closest(".cw-copy"):null;if(!b)return;
var w=b.closest(".codewin");if(!w)return;var t=w.querySelector("pre");
var txt=t?t.innerText:"";
function done(){b.textContent="已复制";setTimeout(function(){b.textContent="复制"},1500)}
if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(txt).then(done,done)}else{done()}});})();</script></body></html>"""

PORTAL_HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><meta http-equiv="Cache-Control" content="no-store"><meta http-equiv="Pragma" content="no-cache">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script>try{var _t=localStorage.getItem("fish-theme");if(!_t)_t=matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";if(_t==="dark")document.documentElement.classList.add("dark")}catch(e){}
try{if("scrollRestoration" in history)history.scrollRestoration="manual";window.scrollTo(0,0);addEventListener("pageshow",function(ev){if(ev.persisted)window.scrollTo(0,0)})}catch(e){}</script>
<title>鱼窝</title>
<style>
:root{--ink:#1e293b;--soft:#64748b;--line:#e2e8f0;
  --teal:#0d9488;--teal-bg:#ecfdf5;--red:#dc2626;--blue:#2563eb;--blue-bg:#eff6ff}
*{box-sizing:border-box;margin:0;padding:0}
a,button{-webkit-tap-highlight-color:transparent}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
  background:#eef2f6;color:var(--ink);font-size:15.5px;line-height:1.65;
  -webkit-font-smoothing:antialiased;min-height:100vh;animation:pgfadein .3s ease}
@keyframes pgfadein{from{opacity:0}to{opacity:1}}
/* --- 门户顶栏：品牌 + 导航 + 搜索，滚动常驻（全站统一） --- */
__TOPBAR_CSS__
.hero{background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 55%,#155e63 100%);color:#fff;
  padding:20px 20px 71px;display:flex;align-items:center;min-height:120px}
.hero .inner{max-width:1140px;margin:0 auto;padding:0 16px;width:100%}
.hero .meta{display:flex;align-items:center;gap:8px;color:rgba(255,255,255,.56);font-size:12.5px;letter-spacing:.3px;text-wrap:balance}
.hero .meta b{color:rgba(255,255,255,.95);font-weight:600;white-space:nowrap;font-variant-numeric:tabular-nums}
.hero .meta .dot{width:7px;height:7px;border-radius:50%;background:#34d399;flex:none;animation:metaPulse 2.4s ease-out infinite}
@keyframes metaPulse{0%{box-shadow:0 0 0 0 rgba(52,211,153,.5)}70%{box-shadow:0 0 0 7px rgba(52,211,153,0)}100%{box-shadow:0 0 0 0 rgba(52,211,153,0)}}
.hero h1{display:none}
.m-only{display:none}
@media(max-width:1080px){
  .tb-name small{display:none}
  .tb-in{gap:8px}
  .tb-search{width:130px}
}
@media(max-width:900px){
  .tb-name{display:none}
  .tb-nav a{padding:5px 8px;font-size:13px}
  .tb-search{width:110px}
}
.wrap{max-width:1140px;margin:-52px auto 0;padding:0 16px 50px}
@media(max-width:680px){.wrap{margin-top:-12px}}
.pwrap{display:grid;grid-template-columns:minmax(0,1fr);gap:20px;align-items:start}
.pside{display:none}
.pside .panel{margin-bottom:20px}
.carband{display:none;background:linear-gradient(135deg,#0f172a,#1e3a5f 55%,#155e63)}
.carousel{position:relative;height:min(430px,56vh);overflow:hidden}
.car-slide{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:0;transition:opacity .9s ease}
.car-slide.on{opacity:1}
.car-shade{position:absolute;inset:0;pointer-events:none;background:linear-gradient(180deg,rgba(15,23,42,.38),rgba(15,23,42,0) 20%,rgba(15,23,42,0) 58%,rgba(15,23,42,.55))}
.car-dots{position:absolute;bottom:12px;left:0;right:0;display:flex;justify-content:center;gap:6px;z-index:2}
.car-dots i{width:7px;height:7px;border-radius:50%;background:rgba(255,255,255,.45);transition:background .3s}
.car-dots i.on{background:#fff}
@media(max-width:680px){.carband{display:none}}
.att-card{background:linear-gradient(160deg,rgba(20,184,166,.09),rgba(59,130,246,.07));border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.att-main{font-size:15px;font-weight:800;color:var(--ink);padding-bottom:10px;margin-bottom:8px;border-bottom:1px dashed var(--line)}
.att-row{display:flex;align-items:center;gap:7px;font-size:13px;color:var(--soft);padding:3px 0}
.att-row b{color:var(--ink);font-weight:600;margin-left:auto;text-align:right}
.att-dot{width:7px;height:7px;border-radius:50%;display:inline-block;flex:none;background:#94a3b8}
.att-dot.ok{background:#10b981}
.fi-card{background:linear-gradient(160deg,rgba(251,191,36,.08),rgba(20,184,166,.07));border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.fi-head{display:flex;align-items:center;gap:10px;padding-bottom:10px;margin-bottom:8px;border-bottom:1px dashed var(--line)}
.fi-avatar{width:40px;height:40px;border-radius:50%;background:linear-gradient(160deg,rgba(20,184,166,.22),rgba(59,130,246,.16));display:flex;align-items:center;justify-content:center;font-size:22px;flex:none}
.fi-name{font-size:16px;font-weight:800;color:var(--ink);line-height:1.2}
.fi-sub{font-size:12px;color:var(--soft);margin-top:2px}
.fi-quote{font-size:14px;line-height:1.8;color:var(--ink);padding:2px 0 8px}
.ds-big{font-size:26px;font-weight:800;font-family:ui-monospace,"SF Mono",Consolas,monospace;padding:2px 0 2px}
.ds-delta{font-size:12.5px;font-weight:700;padding-bottom:4px}
.ds-delta.up{color:var(--teal)}
.ds-delta.down{color:#ef4444}
.fi-likes{font-size:13px;line-height:1.7;padding-bottom:8px;color:var(--ink)}
.fi-lk{color:var(--soft);margin-right:8px}
.di-card{background:linear-gradient(160deg,rgba(251,191,36,.09),rgba(20,184,166,.06));border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.di-quote{font-size:14px;line-height:1.8;color:var(--ink);padding-bottom:10px;border-bottom:1px dashed var(--line);margin-bottom:8px}
.di-meta{display:flex;align-items:center;justify-content:space-between;font-size:12.5px;color:var(--soft)}
.di-meta a{color:var(--teal);text-decoration:none;font-weight:600}
@media(min-width:1021px){
  .pwrap{grid-template-columns:minmax(0,1fr) 292px}
  .pside{display:block}
}
.panel{background:#fff;border:1px solid var(--line);border-radius:16px;
  box-shadow:0 1px 4px rgba(15,23,42,.05);padding:20px 22px;margin-bottom:20px}
.panel h3{font-size:13px;color:var(--soft);font-weight:700;letter-spacing:1px;
  margin-bottom:12px;display:flex;align-items:center;gap:7px}
.kv{display:flex;justify-content:space-between;font-size:13.5px;padding:5px 0}
.kv span{color:var(--soft)}
.kv b{font-weight:600;font-family:ui-monospace,"SF Mono",Consolas,monospace;font-size:13px}
.gauges{display:flex;gap:16px;justify-content:center;margin:4px 0 12px;flex-wrap:wrap}
.gauge{display:flex;flex-direction:column;align-items:center;flex:1;min-width:140px}
.gauge svg{width:132px;height:132px;display:block}
.gauge circle{fill:none;stroke-width:9;stroke-linecap:round}
.g-bg{stroke:var(--line)}
.g-fg{stroke:var(--teal);transform:rotate(-90deg);transform-origin:50% 50%;transition:stroke-dashoffset .8s ease,stroke .3s}
.g-fg.warn{stroke:#f59e0b}
.g-fg.hot{stroke:#ef4444}
.g-num{font-size:23px;font-weight:700;fill:#0b1220;text-anchor:middle;font-family:ui-monospace,"SF Mono",Consolas,monospace}
.g-sub{font-size:10px;fill:var(--soft);text-anchor:middle;font-family:ui-monospace,Consolas,monospace}
html.dark .g-num{fill:#e5ecf5}
html.dark .g-sub{fill:#8b98a9}
.g-cap{font-size:12.5px;color:var(--soft);font-weight:700;margin-top:4px;letter-spacing:1px}
.entries{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.entry{display:block;text-decoration:none;background:#fff;border:1px solid var(--line);
  border-radius:14px;padding:14px 18px;min-width:0;max-width:100%;overflow:hidden;
  transition:border-color .15s,box-shadow .15s,transform .12s}
.entry:hover{border-color:var(--teal);box-shadow:0 3px 14px rgba(13,148,136,.10)}
.entry:active{transform:scale(.985)}
.entry .e-top{display:flex;align-items:center;gap:10px}
.entry .e-ico{width:36px;height:36px;border-radius:10px;background:#e6f5f3;display:inline-flex;
  align-items:center;justify-content:center;font-size:17px;flex:none}
.entry .e-label{font-size:12.5px;color:var(--teal);font-weight:700;letter-spacing:1px}
.entry .e-go{margin-left:auto;color:var(--soft);font-size:15px;transition:transform .15s,color .15s}
.entry:hover .e-go{color:var(--teal);transform:translateX(3px)}
.entry .e-t{display:block;font-size:15.5px;font-weight:700;margin:9px 0 3px;color:var(--ink)}
.entry .e-x{display:block;font-size:13px;color:var(--soft);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.quick{display:grid;gap:8px}
.quick a{display:flex;align-items:center;gap:10px;padding:9px 12px;border:1px solid var(--line);
  border-radius:10px;text-decoration:none;color:var(--ink);font-size:14px;font-weight:600;
  transition:border-color .15s,background .15s}
.quick a:hover{border-color:var(--blue);background:var(--blue-bg)}
.quick a:active{transform:scale(.97)}
.quick a span{font-size:16px}
.quick a small{margin-left:auto;color:var(--soft);font-weight:400;font-size:12px;
  font-family:ui-monospace,Consolas,monospace}
.timeline{position:relative;max-height:300px;overflow-y:auto;padding-left:30px;margin:4px 0 2px}
.timeline::-webkit-scrollbar{width:5px}
.timeline::-webkit-scrollbar-thumb{background:#cbd5e1;border-radius:3px}
.tl-item{position:relative;padding:0 0 18px 14px}
.tl-item:last-child{padding-bottom:4px}
.tl-item::before{content:"";position:absolute;left:-30px;top:4px;width:11px;height:11px;
  border-radius:50%;background:#94a3b8;border:2.5px solid #fff;box-shadow:0 0 0 1.5px #cbd5e1}
.tl-item.add::before{background:var(--teal);box-shadow:0 0 0 1.5px #6ee7d7}
.tl-item.remove::before{background:var(--red);box-shadow:0 0 0 1.5px #fca5a5}
.tl-item::after{content:"";position:absolute;left:-25px;top:20px;bottom:-2px;width:2px;
  background:linear-gradient(180deg,#e2e8f0,#eef2f6)}
.tl-item:last-child::after{display:none}
.tl-time{font-family:ui-monospace,"SF Mono",Consolas,monospace;font-size:12px;color:#94a3b8;letter-spacing:.3px}
.tl-text{color:var(--ink);font-size:14px;margin-top:1px}
.tl-text .tag-add{color:var(--teal);font-weight:600}
.tl-text .tag-remove{color:var(--red);font-weight:600}
footer{max-width:1140px;margin:0 auto;padding:0 16px 40px;font-size:13.5px;text-align:center;letter-spacing:.3px;
  background:linear-gradient(90deg,#8b5cf6 0%,#3b82f6 45%,#14b8a6 100%);
  -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
footer .up,footer .vw{font-weight:700}
.totop{position:fixed;right:18px;bottom:26px;width:42px;height:42px;border-radius:50%;
  background:rgba(15,23,42,.85);color:#fff;border:none;cursor:pointer;z-index:60;
  font-size:17px;box-shadow:0 3px 12px rgba(15,23,42,.28);display:none;
  align-items:center;justify-content:center;opacity:0;transition:opacity .25s;
  -webkit-tap-highlight-color:transparent;outline:none;-webkit-appearance:none;appearance:none;touch-action:manipulation}
.totop.show{display:flex;opacity:1}
.totop:focus{outline:none}
.totop:active{transform:scale(.92);outline:none}
.mtop,.mmask,.mdrawer{display:none}
@media(max-width:680px){
  .entries{grid-template-columns:minmax(0,1fr);gap:10px}
  .heronav{display:none}
  .topbar{display:none}
  .mtop{display:flex;align-items:center;gap:8px;position:sticky;top:0;z-index:60;
    background:rgba(15,23,42,.96);backdrop-filter:blur(8px);color:#fff;padding:11px 14px}
  .mt-burger{display:flex;flex-direction:column;justify-content:center;gap:4px;background:none;
    border:0;padding:8px 8px 8px 2px;cursor:pointer}
  .mt-burger span{display:block;width:20px;height:2px;border-radius:2px;background:#fff}
  .mt-title{font-size:15.5px;font-weight:700;letter-spacing:.3px}
  .mt-search{margin-left:auto;background:none;border:0;color:#fff;font-size:18px;padding:6px 2px 6px 6px;cursor:pointer;-webkit-tap-highlight-color:transparent}
  .mt-search:active{opacity:.7}
  .fsbox-hero{display:none}
  .mdrawer{display:flex;flex-direction:column;position:fixed;top:0;left:0;bottom:0;width:64%;max-width:232px;z-index:100;
    background:rgba(255,255,255,.78);backdrop-filter:blur(32px) saturate(1.5);-webkit-backdrop-filter:blur(32px) saturate(1.5);box-shadow:2px 0 18px rgba(15,23,42,.28);transform:translateX(-106%);
    transition:transform .5s cubic-bezier(.16,1,.3,1) .2s;overflow-y:auto;overscroll-behavior:contain;border-radius:0 18px 18px 0}
  body.drawer-open .mdrawer{transform:none;transition:transform .9s cubic-bezier(.16,1,.3,1);transition-delay:0s}
  .mmask{display:block;position:fixed;inset:0;background:rgba(15,23,42,.45);z-index:90;
    opacity:0;pointer-events:none;transition:opacity .45s}
  body.drawer-open .mmask{opacity:1;pointer-events:auto}
  body.drawer-open{overflow:hidden;overscroll-behavior:contain}
  .md-hero{background:linear-gradient(135deg,#0f172a,#155e63);color:#fff;padding:24px 20px 18px}
  .md-t{font-size:17.5px;font-weight:700}
  .md-sub{font-size:12.5px;color:rgba(255,255,255,.72);margin-top:5px}
  .md-nav{padding:8px 0}
  .md-nav a{display:flex;align-items:center;gap:10px;padding:13px 20px;color:var(--ink);
    text-decoration:none;font-size:15px;font-weight:600;border-bottom:1px solid #eef2f6}
  .md-nav a:last-child{border-bottom:0}
  .md-nav a:active{background:#f1f5f9}
  .md-nav .md-n{margin-left:auto;min-width:22px;height:22px;padding:0 7px;border-radius:999px;background:#f1f5f9;color:var(--soft);font-size:11.5px;font-weight:700;display:flex;align-items:center;justify-content:center;flex:none}
  .md-nav a.cur .md-n,.md-nav a.on .md-n{background:var(--teal);color:#fff}
  html.dark .md-nav .md-n{background:#1a2740;color:#8b98a9}
  html.dark .md-nav a.cur .md-n,html.dark .md-nav a.on .md-n{background:var(--teal);color:#fff}
  .md-nav a{opacity:0;transform:translateX(-26px);transition:opacity .6s ease,transform .75s cubic-bezier(.16,1,.3,1),background .2s}
  body.drawer-open .md-nav a{opacity:1;transform:none}
  .md-nav a:nth-child(1){transition-delay:.10s}
  .md-nav a:nth-child(2){transition-delay:.19s}
  .md-nav a:nth-child(3){transition-delay:.28s}
  .md-nav a:nth-child(4){transition-delay:.37s}
  .md-nav a:nth-child(5){transition-delay:.46s}
  body:not(.drawer-open) .md-nav a:nth-child(1){transition-delay:.20s;transition-duration:.25s}
  body:not(.drawer-open) .md-nav a:nth-child(2){transition-delay:.15s;transition-duration:.25s}
  body:not(.drawer-open) .md-nav a:nth-child(3){transition-delay:.10s;transition-duration:.25s}
  body:not(.drawer-open) .md-nav a:nth-child(4){transition-delay:.05s;transition-duration:.25s}
  body:not(.drawer-open) .md-nav a:nth-child(5){transition-delay:0s;transition-duration:.25s}
  .md-nav a.on{background:var(--teal-bg);color:var(--teal)}
  .md-foot{margin-top:auto;flex:none;padding:14px 16px calc(16px + env(safe-area-inset-bottom,0px))}
  .md-theme{display:flex;align-items:center;justify-content:space-between;gap:10px;width:100%;background:#f1f5f9;border:1px solid #dbe3ec;border-radius:14px;padding:11px 14px;color:var(--ink);font-size:15px;font-weight:600;cursor:pointer;box-shadow:0 1px 3px rgba(15,23,42,.07);-webkit-tap-highlight-color:transparent;outline:none;transition:background .2s}
  .md-theme:active{background:#e6ecf3}
  .md-sw{position:relative;width:48px;height:28px;border-radius:999px;background:#b9c3d0;transition:background .3s;flex:none;box-shadow:inset 0 1px 3px rgba(15,23,42,.18)}
  .md-sw::after{content:"";position:absolute;top:3px;left:3px;width:20px;height:20px;border-radius:50%;background:#fff;box-shadow:0 1px 4px rgba(15,23,42,.3);transition:transform .3s cubic-bezier(.22,1,.36,1)}
  html.dark .md-sw{background:var(--teal)}
  html.dark .md-sw::after{transform:translateX(20px)}
  .md-hero,.md-nav{flex:none}
  html.dark .md-theme{background:#1a2740;border-color:#263552;box-shadow:none}
  html.dark .md-theme:active{background:#22334f}
  .panel{padding:16px 14px;border-radius:13px}
  .hero{padding:20px 20px 24px;min-height:134px}
  .hero h1{display:flex;font-size:23px;letter-spacing:.5px;align-items:center;gap:10px}
  .hero h1 .logo{width:36px;height:36px;border-radius:9px;background:rgba(255,255,255,.14);display:inline-flex;align-items:center;justify-content:center;font-size:17px}
  .m-only{display:inline}
  .hero .meta{margin-top:8px}
}
.tmoon{position:fixed;left:18px;bottom:26px;width:42px;height:42px;border-radius:50%;
  background:rgba(15,23,42,.85);color:#fff;border:none;cursor:pointer;z-index:60;
  font-size:18px;box-shadow:0 3px 12px rgba(15,23,42,.28);
  display:flex;align-items:center;justify-content:center;
  -webkit-tap-highlight-color:transparent;outline:none;-webkit-appearance:none;appearance:none;
  touch-action:manipulation;transition:transform .2s}
.tmoon:active{transform:scale(.92)}
html.dark .tmoon{background:rgba(38,50,67,.9);border:1px solid #263243}
@media(max-width:680px){.tmoon{display:none}}
html.dark body{background:#0b1220;color:#d7dde6}
html.dark{--ink:#d7dde6;--soft:#8b98a9;--line:#263243}
html.dark .panel{background:#111a2b;border-color:#263243}
html.dark .entry{background:#111a2b;border-color:#263243}
html.dark .entry .e-ico{background:#15323a}
html.dark .entry .e-t{color:#e5ecf5}
html.dark .entry .e-x{color:#8b98a9}
html.dark .quick a{color:#d7dde6;border-color:#263243}
html.dark .tl-item::after{background:linear-gradient(180deg,#263243,#1a2740)}
html.dark .tl-item::before{border-color:#111a2b;box-shadow:0 0 0 1.5px #263243}
html.dark .mdrawer{background:rgba(17,26,43,.78);backdrop-filter:blur(32px) saturate(1.4);-webkit-backdrop-filter:blur(32px) saturate(1.4)}
html.dark .md-nav a{color:#d7dde6;border-bottom-color:#1a2740}
html.dark .md-nav a.on{background:#18233a;color:#5eead4}

/* --- 入场淡入淡出 --- */
.intro{position:fixed;inset:0;z-index:9999;background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 55%,#155e63 100%);display:flex;align-items:center;justify-content:center;pointer-events:none;animation:introOut .8s ease 1s forwards,introHold 0s linear 1.8s forwards}
.intro span{font-size:22px;font-weight:600;letter-spacing:10px;text-indent:10px;color:#a7f3d0;opacity:0;animation:introIn 1s ease .1s forwards}
@keyframes introIn{to{opacity:.92}}
@keyframes introOut{to{opacity:0}}
@keyframes introHold{to{visibility:hidden}}
html.nointro .intro{display:none}
html:not(.nointro) body{animation:pageIn .8s ease .1s both}
@keyframes pageIn{from{opacity:0}to{opacity:1}}
@media (prefers-reduced-motion:reduce){.intro{display:none}html:not(.nointro) body{animation:none}}
/* ---------- 测试版：全站搜索 ---------- */
.fsbox{position:relative}
.fsbox-hero{margin:14px auto 0;max-width:380px;flex:none}
.fsbox input{width:100%;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.2);color:#fff;
  border-radius:999px;padding:9px 18px;font-size:14px;outline:none;transition:background .2s;
  -webkit-appearance:none;appearance:none}
.fsbox input::placeholder{color:rgba(255,255,255,.55)}
.fsbox input:focus{background:rgba(255,255,255,.18)}
.fs-drop{display:none;position:absolute;left:0;right:0;top:calc(100% + 8px);background:#fff;border:1px solid var(--line);
  border-radius:14px;box-shadow:0 12px 34px rgba(15,23,42,.2);overflow:hidden;z-index:120}
.fs-drop.on{display:block}
.fs-drop a{display:flex;align-items:center;gap:10px;padding:10px 14px;text-decoration:none;font-size:13.5px;
  color:var(--ink);border-bottom:1px solid #f1f5f9}
.fs-drop a:last-child{border-bottom:none}
.fs-drop a:active,.fs-drop a:hover{background:#f6fbfa}
.fs-k{flex:none;font-size:11px;color:#0d9488;background:#ecfdf5;border-radius:999px;padding:1px 8px;font-weight:700}
.fs-t{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.fs-t b{color:var(--teal)}
.fs-tt{font-weight:600;display:block}
.fs-s{color:var(--soft);font-size:12px;white-space:normal;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
html.dark .fs-s{color:#8b98a9}@media(max-width:768px){input,select,textarea{font-size:16px!important}}
.fs-empty{padding:14px;font-size:13px;color:var(--soft);text-align:center}
html.dark .fs-drop{background:#111a2b;border-color:#263243}
html.dark .fs-drop a{color:#d7dde6;border-bottom-color:#1a2740}
html.dark .fs-drop a:active,html.dark .fs-drop a:hover{background:#16223a}
html.dark .fs-k{background:#0e2a2b;color:#5eead4}
__SEARCH_CSS__
</style></head>
<body><div class="intro" aria-hidden="true"><span>鱼 窝</span></div><script>(function(){var d=document.documentElement,i=document.querySelector(".intro");try{if(sessionStorage.getItem("introDone")){d.classList.add("nointro");}else{sessionStorage.setItem("introDone","1");}}catch(e){}if(i){i.addEventListener("animationend",function(e){if(e.animationName==="introOut")i.remove();});}})();</script>
<div class="mmask" id="mmask" onclick="drawerOff()"></div>
<aside class="mdrawer" id="mdrawer">
  <div class="md-hero"><div class="md-t">🐟 鱼窝</div>
    <div class="md-sub">鱼的日记 · 榜单 · 服务器台账</div></div>
  <nav class="md-nav">
    <a class="on" href="/index.html">🏠 首页</a>
    <a href="/diary.html">📖 鱼的日记<span class="md-n">__N_DIARY__</span></a>
    <a href="/rank.html">📈 GitHub 榜单<span class="md-n">__N_RANK__</span></a>
    <a href="/balance.html">💰 DeepSeek 饭票<span class="md-n">__N_DS__</span></a>
    <a href="/ledger.html">🗂 服务器台账<span class="md-n">__N_LEDGER__</span></a>
  </nav>
  <div class="md-foot"><button class="md-theme" type="button" onclick="themeToggle()"><span>🌙 深色模式</span><span class="md-sw"></span></button></div>
</aside>
<header class="mtop">
  <button class="mt-burger" aria-label="菜单" onclick="drawerOn()"><span></span><span></span><span></span></button>
  <div class="mt-title">鱼窝</div>
  <button class="mt-search" type="button" aria-label="搜索" onclick="searchOn()">🔍</button>
</header>
<div class="s-mask" onclick="searchOff()"></div>
<div class="s-panel" role="dialog" aria-label="搜索">
  <form class="fsbox s-fsbox" action="/search.html" method="get"><span class="s-ico" aria-hidden="true">🔍</span><input type="text" name="q" placeholder="搜索文章…" autocomplete="off" spellcheck="false"><button class="s-go" type="button" aria-label="搜索">🔍</button></form>
</div>
<header class="topbar"><div class="tb-in">
  <a class="tb-brand" href="/index.html" onclick="return false"><span class="tb-logo">🐟</span><span class="tb-name">鱼窝<small>鱼的小窝</small></span></a>
  <nav class="tb-nav">
    <a class="on" href="/index.html">🏠 首页</a>
    <a href="/diary.html">📖 鱼的日记</a>
    <a href="/rank.html">📈 GitHub 榜单</a>
    <a href="/balance.html">💰 DeepSeek 饭票</a>
    <a href="/ledger.html">🗂 服务器台账</a>
  </nav>
  <form class="fsbox tb-search" action="/search.html" method="get"><span class="tb-ico" aria-hidden="true">🔍</span><input id="fs-input" name="q" type="text" placeholder="搜索文章…" autocomplete="off" spellcheck="false"></form>
</div></header>
<div class="hero"><div class="inner">
  <h1 class="m-hero"><span class="logo">🐟</span>鱼窝</h1>
  <div class="meta"><span class="dot"></span><span class="txt"><span class="m-only">鱼的小窝 · </span>最近盘点 <b>__SCAN_TIME__</b> · 每 6 小时自动更新</span></div>
</div></div>
<div class="carband">
__CAROUSEL__
</div>
<div class="wrap">
<div class="pwrap">
<div class="pmain">
  __FISH_QUOTE__
  <div class="panel"><h3>🖥 鱼窝现状</h3>
    __SYSSTRIP__
    <div class="kv"><span>服务器已运行</span><b>__UP__</b></div>
  </div>
  <div class="panel"><h3>🧭 鱼窝速览</h3>
  <div class="entries">
    <a class="entry" href="/diary.html"><span class="e-top"><span class="e-ico">📖</span><span class="e-label">鱼的日记</span><span class="e-go">→</span></span>
      <span class="e-t">__DIARY_HEAD__</span>
      <span class="e-x">__DIARY_X2__</span></a>
    <a class="entry" href="/balance.html"><span class="e-top"><span class="e-ico">💰</span><span class="e-label">DeepSeek 饭票</span><span class="e-go">→</span></span>
      <span class="e-t">余额 __DS_BAL__</span>
      <span class="e-x">__DS_TS__ 更新 · 走势与明细在里面</span></a>
    <a class="entry" href="/rank.html"><span class="e-top"><span class="e-ico">📈</span><span class="e-label">GitHub 榜单</span><span class="e-go">→</span></span>
      <span class="e-t">__RANK_HEAD__</span>
      <span class="e-x">每天早 8:30 自动收录全站趋势</span></a>
    <a class="entry" href="/ledger.html"><span class="e-top"><span class="e-ico">🗂</span><span class="e-label">服务器台账</span><span class="e-go">→</span></span>
      <span class="e-t">__N_TOTAL__ 条资产 · __N_CONT__ 个容器</span>
      <span class="e-x">健康一览 · 实时状态 · 变更时间线</span></a>
  </div></div>
</div>
<aside class="pside">
__PSIDE__
</aside>
</div>
</div>
<footer><span class="up">__UPTIME__</span><span id="views"></span></footer>
<button class="tmoon" type="button" aria-label="切换黑夜模式" onclick="themeToggle()">🌙</button>
<button class="totop" type="button" aria-label="回到顶部">↑</button>
<script>
function drawerOn(){document.body.classList.add("drawer-open")}
function drawerOff(){document.body.classList.remove("drawer-open")}
function searchOn(){document.body.classList.add("search-open");var i=document.querySelector(".s-fsbox input");if(i)setTimeout(function(){i.focus()},400)}
function searchOff(){document.body.classList.remove("search-open")}
document.addEventListener("keydown",function(e){if(e.key==="Escape")searchOff()});
function themeToggle(){var d=document.documentElement.classList.toggle("dark");
try{localStorage.setItem("fish-theme",d?"dark":"light")}catch(e){}
var b=document.querySelectorAll(".tmoon");for(var i=0;i<b.length;i++)b[i].textContent=d?"☀️":"🌙";}
(function(){var b=document.querySelector(".tmoon");
if(b)b.textContent=document.documentElement.classList.contains("dark")?"☀️":"🌙";})();
window.addEventListener("scroll",function(){var b=document.querySelector(".totop");
if(b)b.classList.toggle("show",window.scrollY>420)},{passive:true});
var _tb=document.querySelector(".totop");
if(_tb)_tb.addEventListener("click",function(){window.scrollTo({top:0,behavior:"smooth"})});
try{fetch('/cgi-bin/visit').then(r=>r.json()).then(j=>{
  const el=document.getElementById('views');
  if(el) el.innerHTML=' · <span class="vw">累计到访 '+j.views+' 次</span>';
function refreshGauge(){try{fetch('/cgi-bin/health?ts='+Date.now()).then(r=>r.json()).then(j=>{
function setRing(idp,pct){var rg=document.getElementById(idp+'-ring');if(rg){rg.style.strokeDashoffset=(263.9*(1-Math.min(pct,100)/100)).toFixed(1);rg.setAttribute('class','bt-fg '+((pct>=90)?'hot':((pct>=75)?'warn':'')));}var nv=document.getElementById(idp+'-nv');if(nv)nv.textContent=Math.round(pct);}
var fm=function(v){return v<1?(v*1024).toFixed(1)+'MB':v.toFixed(1)+'GB'};
if(j.mem&&j.mem.total){setRing('bt-mem',j.mem.pct);var ms=document.getElementById('bt-mem-stat');if(ms)ms.innerHTML='<span class="bt-val">'+fm(j.mem.used)+'</span> / <span class="bt-val">'+fm(j.mem.total)+'</span>';}
if(j.disk&&j.disk.total){setRing('bt-disk',j.disk.pct);var ds2=document.getElementById('bt-disk-stat');if(ds2)ds2.innerHTML='<span class="bt-val">'+j.disk.used.toFixed(1)+'GB</span> / <span class="bt-val">'+j.disk.total.toFixed(1)+'GB</span>';}
if(j.load){var nc=j.ncpu||1;var lp=Math.min(parseFloat(j.load)/nc*100,100);setRing('bt-load',lp);var ls=document.getElementById('bt-load-stat');if(ls)ls.textContent=lp<30?'运行流畅':(lp<70?'运行正常':'运行缓慢');}
if(typeof j.cpu==='number'){setRing('bt-cpu',j.cpu);}
}).catch(function(e){});}catch(e){}}
refreshGauge();if(window.__ggT)clearInterval(window.__ggT);window.__ggT=setInterval(refreshGauge,60000);
}).catch(()=>{const el=document.getElementById('views');if(el)el.style.display='none';});}catch(e){}
</script>
<script>__SEARCH_JS__</script></body></html>"""

def build_sidebar():
    sys = collect_sysinfo()
    def bar(label, pct, extra="", idp=""):
        cls = "hot" if pct >= 90 else ("warn" if pct >= 75 else "")
        pid = f' id="h-{idp}-pct"' if idp else ""
        fid = f' id="h-{idp}-fill"' if idp else ""
        return (f'<div class="bar"><div class="lb"><span>{label}</span>'
                f'<b{pid}>{pct:.0f}%{extra}</b></div>'
                f'<div class="track"><div class="fill {cls}"{fid} style="width:{min(pct,100)}%"></div></div></div>')
    mem, disk = sys["mem"], sys["disk"]
    health = (bar("内存", mem["pct"], f' ({mem["used"]:.1f}/{mem["total"]:.1f} GB)' if mem["total"] else "", "mem")
              + bar("磁盘", disk["pct"], f' ({disk["used"]:.0f}/{disk["total"]:.0f} GB)' if disk["total"] else "", "disk")
              + f'<div class="kv"><span>负载（{sys["ncpu"]} 核）</span></div>'
              + LOADBAR_CSS + loadbar_html(sys["load"])
              + f'<div class="kv"><span>已运行</span><b id="h-up">{sys["up"]}</b></div>')
    # 下次盘点：cron 每 6 小时的第 7 分
    import datetime as _dt
    now = _dt.datetime.now()
    slots = [x for x in [0, 6, 12, 18] if x > now.hour] or [24]
    nx = now.replace(hour=(slots[0] if slots[0] < 24 else 0), minute=7, second=0)
    if slots[0] >= 24:
        nx += _dt.timedelta(days=1)
    delta = nx - now
    hours_l = f"{int(delta.total_seconds() // 3600)} 小时 {int(delta.total_seconds() % 3600 // 60)} 分后"
    plan = (f'<div class="kv"><span>上次盘点</span><b>{time.strftime("%m-%d %H:%M")}</b></div>'
            f'<div class="kv"><span>下次盘点</span><b>{nx.strftime("%m-%d %H:%M")}</b></div>'
            f'<div class="kv"><span>倒计时</span><b>{hours_l}</b></div>'
            f'<div class="plan">变更有增删时立即发邮件；零变更保持安静。</div>')
    return (f'<div class="panel"><h3>🖥 服务器健康</h3>{health}</div>'
            f'<div class="panel"><h3>🗓 盘点计划</h3>{plan}</div>')

BORN_FILE = f"{BASE}/site-born"

def site_uptime():
    """站点已运行时长；首次运行以 asset-web 服务启动时间起算"""
    born = load(BORN_FILE, {}).get("t")
    if not born:
        out2 = subprocess.run(
            ["systemctl", "show", "asset-web.service", "-p", "ActiveEnterTimestamp", "--value"],
            capture_output=True, text=True)
        import datetime as _dt
        try:
            born = _dt.datetime.strptime(out2.stdout.strip(), "%a %Y-%m-%d %H:%M:%S %Z").timestamp()
        except Exception:
            born = time.time()
        save(BORN_FILE, {"t": born})
    d = time.time() - born
    days = int(d // 86400)
    hours = int(d % 86400 // 3600)
    mins = int(d % 3600 // 60)
    if days > 0:
        return f"本站已连续运行 {days} 天 {hours} 小时"
    if hours > 0:
        return f"本站已连续运行 {hours} 小时 {mins} 分"
    return f"本站已连续运行 {mins} 分钟"

VISIT_CGI = """#!/bin/sh
D=/root/asset-ledger/visits
[ -f "$D" ] || echo 0 > "$D"
N=$(cat "$D"); N=$((N+1)); echo "$N" > "$D"
printf 'Content-Type: application/json\\r\\n\\r\\n{"views":%s}' "$N"
"""

def ensure_visit_cgi():
    p = f"{BASE}/www/cgi-bin/visit"
    try:
        if not os.path.exists(p):
            with open(p, "w") as f:
                f.write(VISIT_CGI)
            os.chmod(p, 0o755)
    except Exception:
        pass

HEALTH_CGI = """#!/bin/bash
# 台账健康实时接口：内存/磁盘/负载/运行时长，输出 JSON
cd /root/asset-ledger
printf 'Content-Type: application/json\\r\\n\\r\\n'
python3 - <<'PY'
import json, sys
sys.path.insert(0, "/root/asset-ledger")
try:
    from scan import collect_sysinfo
    print(json.dumps(collect_sysinfo()))
except Exception:
    print(json.dumps({}))
PY
"""

def ensure_health_cgi():
    p = f"{BASE}/www/cgi-bin/health"
    try:
        if not os.path.exists(p):
            with open(p, "w") as f:
                f.write(HEALTH_CGI)
            os.chmod(p, 0o755)
    except Exception:
        pass

def gen_page(rows, offline, hist, notes_unused=None):
    ensure_visit_cgi()
    ensure_health_cgi()
    live_keys = {r["key"] for r in rows}
    vis_off = [o for o in offline if o["key"] not in live_keys]
    row_html = []
    for r in rows:
        if str(r["port"]).isdigit() and r["port"] != "22":
            st = (f'<span class="pill na" data-port="{r["port"]}">'
                  f'<span class="dot"></span><span class="st">…</span></span>')
        else:
            st = '<span class="pill na"><span class="dot"></span><span class="st">本机入口</span></span>'
        kind_cls = "kind port" if r["kind"] == "端口" else "kind"
        if str(r["port"]).isdigit() and r["port"] != "22":
            name_html = (f'<a class="svc-link" href="http://114.116.224.172:{r["port"]}/" '
                         f'target="_blank" rel="noopener">{r["name"]}</a>')
        else:
            name_html = r["name"]
        row_html.append(
            f'<tr>'
            f'<td data-label="状态">{st}</td>'
            f'<td data-label="名称"><span class="svc">{name_html}</span></td>'
            f'<td data-label="类型"><span class="{kind_cls}">{r["kind"]}</span></td>'
            f'<td data-label="端口"><span class="mono">{r["port"]}</span></td>'
            f'<td data-label="详情" class="hide-m"><span class="mono">{r["detail"]}</span></td>'
            f'<td data-label="备注"><span class="note-cell">{r["note"]}</span></td>'
            f'</tr>')
    off_html = "".join(
        f'<tr class="offline"><td data-label="名称"><span class="svc">{o["name"]}</span></td>'
        f'<td data-label="类型"><span class="kind port">{o["kind"]}</span></td>'
        f'<td data-label="端口"><span class="mono">{o["port"]}</span></td>'
        f'<td data-label="下线时间"><span class="when">{o["when"]}</span></td></tr>'
        for o in vis_off) or '<tr class="offline"><td data-label="—" colspan="4">暂无下线条目</td></tr>'
    if hist:
        items = []
        for h in hist[-15:]:
            parts = h.split(" ", 2)
            t = parts[0] + " " + parts[1] if len(parts) >= 3 else h
            text = parts[2] if len(parts) >= 3 else ""
            if text.startswith("新增"):
                cls, text = "tl-item add", '<span class="tag-add">新增</span>' + text[2:]
            elif text.startswith("下线"):
                cls, text = "tl-item remove", '<span class="tag-remove">下线</span>' + text[2:]
            elif text.startswith("首次盘点"):
                cls, text = "tl-item add", '<span class="tag-add">开张</span>' + text[4:]
            else:
                cls = "tl-item"
            items.append(
                f'<div class="{cls}"><div class="tl-time">{t}</div>'
                f'<div class="tl-text">{text}</div></div>')
        hist_html = '<div class="timeline">' + "".join(items) + "</div>"
    else:
        hist_html = "暂无变更"
    n_ports = len({r["port"] for r in rows if str(r["port"]).isdigit()})
    html = TEMPLATE
    for k, v in {
        "__SCAN_TIME__": time.strftime("%Y-%m-%d %H:%M"), "__N_TOTAL__": str(len(rows)),
        "__N_CONT__": str(sum(1 for r in rows if r["kind"] == "容器")),
        "__N_PORTS__": str(n_ports), "__N_OFF__": str(len(vis_off)),
        "__ROWS__": "".join(row_html), "__OFFROWS__": off_html,
        "__SEARCH_BTN__": SEARCH_BTN, "__SEARCH_PANEL__": SEARCH_PANEL,
        "__SEARCH_SCRIPT__": SEARCH_SCRIPT, "__SEARCH_JS__": SEARCH_JS, "__SEARCH_CSS__": SEARCH_CSS,
        "__TOPBAR_CSS__": TOPBAR_CSS,
        "__HIST__": hist_html, "__SIDEBAR__": build_sidebar(),
        "__UPTIME__": site_uptime(),
        "__PORTS__": json.dumps({str(r["port"]): "" for r in rows}),
    }.items():
        html = html.replace(k, v)
    with open(f"{WWW}/ledger.html", "w") as f:
        f.write(apply_drawer_counts(html))
    # ---------- 门户首页 ----------
    portal = PORTAL_HTML
    portal = (portal.replace("__SEARCH_JS__", SEARCH_JS)
                    .replace("__SEARCH_CSS__", SEARCH_CSS)
                    .replace("__TOPBAR_CSS__", TOPBAR_CSS))
    q = daily_quote()
    if q:
        quote_html = (f'{QUOTE_CSS}<div class="panel fish-quote"><h3>💬 今日鱼言</h3>'
                      f'<div class="fq-txt">「{q["q"]}」</div>'
                      f'<div class="fq-src">—— 《{q["t"]}》 · <a href="/diary.html#d{q["d"]}">{q["d"]}</a></div></div>')
    else:
        quote_html = ""
    import glob as _g2, shutil as _sh2
    _covdir = f"{WWW}/assets/covers"
    os.makedirs(_covdir, exist_ok=True)
    for _f in _g2.glob("/root/.dsh/shots/covers/*.jpg"):
        try:
            _sh2.copy2(_f, f"{_covdir}/{os.path.basename(_f)}")
        except Exception:
            pass
    _covs = sorted(os.listdir(_covdir))[:8]
    if _covs:
        _slides = "".join(
            f'<img class="car-slide{" on" if _i == 0 else ""}" src="/assets/covers/{_c}" alt="">'
            for _i, _c in enumerate(_covs))
        _dots = "".join(f'<i class="{"on" if _i == 0 else ""}"></i>' for _i in range(len(_covs)))
        carousel_html = (f'<div class="carousel">{_slides}<div class="car-shade"></div>'
                         f'<div class="car-dots">{_dots}</div></div>'
                         '<script>(function(){if(window.__carT)clearInterval(window.__carT);'
                         'var s=document.querySelectorAll(".car-slide"),'
                         'd=document.querySelectorAll(".car-dots i");if(s.length<2){'
                         'if(s.length===1)s[0].classList.add("on");return}var i=0;'
                         'window.__carT=setInterval(function(){s[i].classList.remove("on");d[i].classList.remove("on");'
                         'i=(i+1)%s.length;s[i].classList.add("on");d[i].classList.add("on")},4500)})();</script>')
    else:
        carousel_html = ""
    portal = portal.replace("__CAROUSEL__", carousel_html)
    portal = portal.replace("__FISH_QUOTE__", quote_html)
    entries = load_diary()
    if entries:
        top = entries[0]
        snippet = re.sub(r"\s+", " ", top["body"]).strip()
        snippet = re.sub(r"#+\s*", " ", snippet).strip()
        snippet = snippet[:60]
        portal = portal.replace("__DIARY_HEAD__", f"《{top['title']}》")
        portal = portal.replace("__DIARY_X2__", f"最新一篇 · {top['date']}")
    else:
        portal = portal.replace("__DIARY_HEAD__", "还没开张")
        portal = portal.replace("__DIARY_X2__", "小鱼的第一篇日记还在路上")
    recs = ds_balance_recs()
    if recs:
        last = recs[-1]
        portal = portal.replace("__DS_BAL__", f"¥{last['balance']:.2f}")
        portal = portal.replace("__DS_TS__", f"{last['ts']}")
    else:
        portal = portal.replace("__DS_BAL__", "暂无记录")
        portal = portal.replace("__DS_TS__", "等待首笔盘点记录")
    import glob as _glob2
    rank_files = sorted(_glob2.glob(RANK_GLOB), reverse=True)
    write_search_index(entries, rank_files)
    if rank_files:
        rdate = os.path.basename(rank_files[0]).replace(".md", "")
        portal = portal.replace("__RANK_HEAD__", f"最新 {rdate} · 已收录")
    else:
        portal = portal.replace("__RANK_HEAD__", "存档积累中")
    try:
        sys = collect_sysinfo()
        mem, disk = sys["mem"], sys["disk"]
        portal = portal.replace("__MEM_PCT__", f"{mem['pct']:.0f}")
        portal = portal.replace("__MEM_TXT__", f"{mem['used']:.1f}/{mem['total']:.1f} GB")
        portal = portal.replace("__DISK_PCT__", f"{disk['pct']:.0f}")
        portal = portal.replace("__DISK_TXT__", f"{disk['used']:.0f}/{disk['total']:.0f} GB")
        portal = portal.replace("__MEM_OFF__", f"{251.3*(1-min(mem['pct'],100)/100):.1f}")
        portal = portal.replace("__MEM_CLS__", "hot" if mem['pct']>=90 else ("warn" if mem['pct']>=75 else ""))
        portal = portal.replace("__DISK_OFF__", f"{251.3*(1-min(disk['pct'],100)/100):.1f}")
        portal = portal.replace("__DISK_CLS__", "hot" if disk['pct']>=90 else ("warn" if disk['pct']>=75 else ""))
        portal = portal.replace("__SYSSTRIP__", sysstrip_html(sys))
        portal = portal.replace("__NCPU__", str(sys["ncpu"]))
        portal = portal.replace("__LOAD__", str(sys["load"]))
        portal = portal.replace("__LOADBAR__", LOADBAR_CSS + loadbar_html(sys["load"]))
        portal = portal.replace("__UP__", str(sys["up"]))
    except Exception:
        portal = portal.replace("__SYSSTRIP__", sysstrip_html(
            {"load": "0", "ncpu": 1, "cpu": 0,
             "mem": {"pct": 0, "used": 0, "total": 0},
             "disk": {"pct": 0, "used": 0, "total": 0}}))
        portal = portal.replace("__MEM_PCT__", "—").replace("__MEM_TXT__", "—").replace("__MEM_OFF__", "251.3").replace("__MEM_CLS__", "")
        portal = portal.replace("__DISK_PCT__", "—").replace("__DISK_TXT__", "—").replace("__DISK_OFF__", "251.3").replace("__DISK_CLS__", "")
        portal = portal.replace("__NCPU__", "—").replace("__LOAD__", "—").replace("__UP__", "—")
        portal = portal.replace("__LOADBAR__", LOADBAR_CSS + loadbar_html(0))
    # ---------- 门户侧栏卡（2026-11-19 预览：今晚出勤/小雨名片/今天的鱼/饭票速览） ----------
    def _pside():
        import datetime as _dt3
        today = time.strftime("%Y-%m-%d")
        try:
            wn = load("/root/.dsh/whale-night.json", {})
        except Exception:
            wn = {}
        win = str(wn.get("window") or "18:00\u201322:00")
        if str(wn.get("date")) == today:
            if wn.get("skippedWindows"):
                att = "今晚摇到「跳过」，休息一晚 🛌"
            elif wn.get("wakes", 0) > 0:
                att = "今晚已经醒过啦 ✅"
            else:
                _at = str(wn.get("atText") or "").split(" ")[-1]
                att = f"计划今晚 {_at or '?'} 醒 ⏰"
        else:
            att = "今晚的安排还没排出来"
        yday = (_dt3.datetime.now() - _dt3.timedelta(days=1)).strftime("%Y-%m-%d")
        last_night = "昨晚来过 ✓" if f"{yday}|{win}" in (wn.get("usedCount") or {}) else "昨晚没动静"
        night_cls = "ok" if last_night.startswith("昨晚来过") else ""
        if entries:
            _top = entries[0]
            _sn = re.sub(r"\s+", " ", _top["body"]).strip()
            _sn = re.sub(r"#+\s*", " ", _sn).strip()[:46] + "…"
            fish_today = (f'<div class="di-card"><div class="di-quote">{_sn}</div>'
                          f'<div class="di-meta"><span>{_top["date"]}</span>'
                          f'<a href="/diary.html#d{_top["date"]}">读全文 →</a></div></div>')
        else:
            fish_today = '<div class="di-card"><div class="di-quote">小鱼的第一篇日记还在路上，敬请期待～</div></div>'
        return (
            f'<div class="panel"><h3>🌙 今晚出勤</h3><div class="att-card">'
            f'<div class="att-main">{att}</div>'
            f'<div class="att-row"><span>🕰️</span><span>作息</span><b>每晚 {win} 醒 1 次</b></div>'
            f'<div class="att-row"><span class="att-dot {night_cls}"></span><span>{yday[5:]}</span><b>{last_night}</b></div></div></div>'
            f'<div class="panel"><h3>📅 今天的鱼</h3>{fish_today}</div>'
            f'<div class="panel"><h3>⚡ 快捷入口</h3><div class="quick">'
            f'<a href="/diary.html#random"><span>🎲</span>随便看看<small>抽一篇日记</small></a>'
            f'<a href="http://114.116.224.172:3001/" target="_blank" rel="noopener"><span>🩺</span>状态岗哨<small>:3001</small></a>'
            f'<a href="http://114.116.224.172:3080/" target="_blank" rel="noopener"><span>🐟</span>DSH<small>:3080</small></a>'
            f'<a href="https://114.116.224.172:8899/91d80a12" target="_blank" rel="noopener"><span>🧱</span>宝塔面板<small>:8899</small></a>'
            f'<a href="https://console.huaweicloud.com/smb/?region=cn-south-1#/resource/list" target="_blank" rel="noopener"><span>☁️</span>华为云控制台<small>华为云</small></a>'
            f'<a href="https://platform.deepseek.com/usage" target="_blank" rel="noopener"><span>💰</span>DeepSeek 饭票<small>官方 API</small></a>'
            f'<a href="https://github.com/LFX804386238" target="_blank" rel="noopener"><span>🐙</span>GitHub<small>主页</small></a>'
            f'</div></div>')
    portal = portal.replace("__PSIDE__", _pside())
    for k, v in {
        "__SCAN_TIME__": time.strftime("%Y-%m-%d %H:%M"), "__N_TOTAL__": str(len(rows)),
        "__N_CONT__": str(sum(1 for r in rows if r["kind"] == "容器")),
        "__HIST__": hist_html, "__UPTIME__": site_uptime(),
    }.items():
        portal = portal.replace(k, v)
    with open(f"{WWW}/index.html", "w") as f:
        f.write(apply_drawer_counts(portal))
    build_full_pages()

def main():
    if "--ds" in sys.argv:
        state = load(STATE, {})
        collect_ds_balance()
        gen_page(state.get("rows", []), state.get("offline", []), load(HIST, []))
        return
    os.makedirs(DATA, exist_ok=True)
    state = load(STATE, {})
    old_rows = state.get("rows", [])
    containers = scan_containers()
    hostports = scan_host_ports()
    write_port_list(containers, hostports)
    rows, notes = build_rows(containers, hostports)
    added, removed = diff(old_rows, rows)
    hist = load(HIST, [])
    offline = state.get("offline", [])
    now = time.strftime("%Y-%m-%d %H:%M")
    changed = bool(added or removed)
    for r in added:
        hist.append(f"{now} 新增：{r['name']}（{r['kind']}，端口 {r['port']}）")
        offline = [o for o in offline if o["key"] != r["key"]]
    for r in removed:
        hist.append(f"{now} 下线：{r['name']}（{r['kind']}，端口 {r['port']}）")
        offline.append({"key": r["key"], "name": r["name"], "kind": r["kind"],
                        "port": r["port"], "when": now})
    hist = hist[-200:]
    save(STATE, {"rows": rows, "offline": offline, "time": now})
    save(HIST, hist)
    collect_ds_balance()
    gen_page(rows, offline, hist)
    if changed and old_rows:
        body = "服务器资产台账变更：\n\n"
        for r in added: body += f"[新增] {r['name']}（{r['kind']}，端口 {r['port']}）\n"
        for r in removed: body += f"[下线] {r['name']}（{r['kind']}，端口 {r['port']}）\n"
        send_mail("【台账】服务器资产变更", body)
    elif not old_rows:
        hist.append(f"{now} 首次盘点：{len(rows)} 项入账")
        save(HIST, hist)

if __name__ == "__main__":
    main()

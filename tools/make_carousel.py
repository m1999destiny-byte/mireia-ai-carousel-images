#!/usr/bin/env python3
"""Render a 6-slide Instagram carousel (1080x1350 PNG) from a JSON spec.
Usage: python3 make_carousel.py spec.json outdir
spec = {"theme": "news"|"tips", "slides": [ {...}, ... ]}
slide types:
  cover:     {"type":"cover","kicker":"2026.10.17 AIニュース","title":"改行は\\nで","sub":"3分でわかる"}
  statement: {"type":"statement","heading":"ひとことで言うと？","text":"本文","note":"小さな注記(任意)"}
  cards:     {"type":"cards","heading":"何がすごいの？","items":[{"title":"..","body":".."}, ...(2-4個)],"note":"出典注記(任意)"}
  steps:     {"type":"steps","heading":"やり方","items":[{"title":"..","body":".."}, ...(2-4個)],"note":"(任意)"}
  cta:       {"type":"cta","heading":"まとめ","points":["..",".."],"cta":"保存＆フォローで…"}
"""
import json, sys, html, os
from playwright.sync_api import sync_playwright

THEMES = {
    "news": {"accent": "#2f6bff", "accent2": "#7aa7ff", "bg1": "#e9f1ff", "bg2": "#ffffff", "ink": "#071949", "label": "AI NEWS"},
    "tips": {"accent": "#0aa88c", "accent2": "#6fd6c0", "bg1": "#e6f7f2", "bg2": "#ffffff", "ink": "#06332c", "label": "AI TIPS"},
}

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1080px;height:1350px;overflow:hidden}
body{word-break:auto-phrase;line-break:strict;font-family:'Noto Sans CJK JP','Noto Sans JP',sans-serif;color:var(--ink);
 background:linear-gradient(165deg,var(--bg1) 0%,var(--bg2) 62%);position:relative}
.deco1{position:absolute;right:-180px;top:-180px;width:520px;height:520px;border-radius:50%;
 background:radial-gradient(circle,var(--accent2) 0%,rgba(255,255,255,0) 70%);opacity:.55}
.deco2{position:absolute;left:-200px;bottom:-200px;width:560px;height:560px;border-radius:50%;
 background:radial-gradient(circle,var(--accent2) 0%,rgba(255,255,255,0) 70%);opacity:.4}
.wrap{position:absolute;inset:0;padding:88px 84px 96px 84px;display:flex;flex-direction:column}
.top{display:flex;justify-content:space-between;align-items:center;font-weight:700;font-size:30px;color:var(--accent);letter-spacing:.08em}
.pill{background:var(--accent);color:#fff;border-radius:999px;padding:10px 26px;font-size:28px;font-weight:700}
.pager{color:var(--ink);opacity:.45;font-size:28px;font-weight:700}
.main{flex:1;display:flex;flex-direction:column;justify-content:center;min-height:0}
.fit{overflow:hidden}
h1{font-weight:900;line-height:1.28;letter-spacing:-.01em}
h2{font-weight:900;font-size:68px;line-height:1.25;margin-bottom:44px}
h2:after{content:"";display:block;width:110px;height:10px;border-radius:6px;background:var(--accent);margin-top:22px}
.sub{font-size:44px;font-weight:700;opacity:.8;margin-top:36px;line-height:1.5}
.lead{font-size:58px;font-weight:800;line-height:1.55}
.note{font-size:28px;line-height:1.55;opacity:.62;margin-top:30px}
.cards{display:flex;flex-direction:column;gap:28px;flex:1;min-height:0}
.card{background:#fff;border-radius:34px;padding:34px 40px;box-shadow:0 14px 40px rgba(20,50,120,.12);display:flex;gap:32px;align-items:center;flex:1;min-height:0}
.badge{flex:none;width:92px;height:92px;border-radius:50%;background:var(--accent);color:#fff;font-weight:900;font-size:50px;display:flex;align-items:center;justify-content:center}
.ct{flex:1;min-width:0;height:100%;display:flex;flex-direction:column;justify-content:center}
.ct .t{font-weight:900;font-size:46px;line-height:1.3}
.ct .b{font-size:36px;line-height:1.5;margin-top:10px;opacity:.82}
.points{display:flex;flex-direction:column;gap:26px}
.pt{display:flex;gap:26px;align-items:flex-start;font-size:56px;font-weight:700;line-height:1.5}
.pt .dot{flex:none;width:26px;height:26px;border-radius:50%;background:var(--accent);margin-top:26px}
.cta{margin-top:44px;background:var(--accent);color:#fff;border-radius:30px;padding:36px 44px;font-size:46px;font-weight:900;line-height:1.45;text-align:center}
.foot{margin-top:30px;text-align:center;font-size:30px;font-weight:700;color:var(--ink);opacity:.55}
"""

FIT_JS = """
() => {
  document.querySelectorAll('[data-fit]').forEach(el => {
    let fs = parseFloat(getComputedStyle(el).fontSize);
    let n = 0;
    while ((el.scrollHeight > el.clientHeight + 1 || el.scrollWidth > el.clientWidth + 1) && fs > 22 && n < 120) {
      fs -= 2; el.style.fontSize = fs + 'px'; n++;
    }
  });
}
"""

def e(s):
    return html.escape(s or "").replace("\n", "<br>")

def slide_html(sl, idx, total, theme):
    t = THEMES[theme]
    typ = sl["type"]
    body = ""
    if typ == "cover":
        body = f"""<div class="main">
          <div style="font-size:38px;font-weight:800;color:var(--accent);margin-bottom:34px">{e(sl.get('kicker'))}</div>
          <h1 class="fit" data-fit style="font-size:124px;height:520px;display:block;white-space:nowrap">{e(sl['title'])}</h1>
          <div class="sub">{e(sl.get('sub'))}</div></div>
          <div class="foot">保存して後で読もう ▸ スワイプで解説</div>"""
    elif typ == "statement":
        body = f"""<div class="main"><h2>{e(sl['heading'])}</h2>
          <div class="fit" data-fit style="font-size:68px;font-weight:800;line-height:1.55;height:680px;display:flex;align-items:center"><div>{e(sl['text'])}</div></div>
          {('<div class="note">'+e(sl['note'])+'</div>') if sl.get('note') else ''}</div>"""
    elif typ in ("cards", "steps"):
        items = sl["items"]
        cards = ""
        for i, it in enumerate(items, 1):
            cards += f"""<div class="card"><div class="badge">{i}</div>
              <div class="ct fit" data-fit><div class="t">{e(it['title'])}</div><div class="b">{e(it.get('body'))}</div></div></div>"""
        body = f"""<div class="main" style="justify-content:flex-start;padding-top:40px"><h2>{e(sl['heading'])}</h2>
          <div class="cards">{cards}</div>
          {('<div class="note">'+e(sl['note'])+'</div>') if sl.get('note') else ''}</div>"""
    elif typ == "cta":
        pts = "".join(f'<div class="pt"><div class="dot"></div><div>{e(p)}</div></div>' for p in sl["points"])
        body = f"""<div class="main"><h2>{e(sl['heading'])}</h2>
          <div class="points fit" data-fit style="height:560px;justify-content:center">{pts}</div>
          <div class="cta">{e(sl['cta'])}</div></div>"""
    top = f"""<div class="top"><div class="pill">{t['label']}</div><div class="pager">{idx}/{total}</div></div>"""
    style = f"--accent:{t['accent']};--accent2:{t['accent2']};--bg1:{t['bg1']};--bg2:{t['bg2']};--ink:{t['ink']}"
    return f"""<!doctype html><html lang="ja"><head><meta charset="utf-8"><style>{CSS}</style></head>
    <body style="{style}"><div class="deco1"></div><div class="deco2"></div>
    <div class="wrap">{top if typ!='cover' else top}{body}</div></body></html>"""

def main():
    spec = json.load(open(sys.argv[1], encoding="utf-8"))
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    theme = spec.get("theme", "news")
    slides = spec["slides"]
    assert 2 <= len(slides) <= 10
    with sync_playwright() as p:
        exe = os.environ.get("CHROMIUM_PATH")
        b = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
        for i, sl in enumerate(slides, 1):
            pg.set_content(slide_html(sl, i, len(slides), theme))
            pg.evaluate("document.fonts.ready")
            pg.evaluate(FIT_JS)
            pg.screenshot(path=os.path.join(out, f"slide-{i}.png"))
            print("rendered", i)
        b.close()

if __name__ == "__main__":
    main()

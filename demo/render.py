"""Turn emulator transcripts (demo/out/*.json) into Telegram-style chat pages.

Run after the scenarios: python demo/render.py  ->  demo/out/<bot>-<chat>.html
Then demo/screenshot.mjs renders them to PNG.
"""

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font:15px/1.35 -apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,"Noto Color Emoji",sans-serif;
 background:#0e1621;color:#fff;width:420px}
.top{position:sticky;top:0;z-index:2;background:#17212b;padding:10px 14px;display:flex;align-items:center;gap:12px;
 border-bottom:1px solid #0b1118}
.ava{width:40px;height:40px;border-radius:50%;background:linear-gradient(135deg,#5eb5f7,#3a6fd8);display:grid;
 place-items:center;font-weight:600;font-size:17px}
.name{font-weight:600}.sub{color:#6d7f8f;font-size:13px}
.chat{padding:12px 10px 16px;background:#0e1621;display:flex;flex-direction:column;gap:6px;min-height:200px}
.row{display:flex;flex-direction:column;max-width:86%}
.row.user{align-self:flex-end;align-items:flex-end}.row.bot{align-self:flex-start}
.b{padding:7px 11px 8px;border-radius:14px;white-space:pre-wrap;word-wrap:break-word}
.bot .b{background:#182533;border-bottom-left-radius:4px}
.user .b{background:#2b5278;border-bottom-right-radius:4px}
.b b{font-weight:600}.b i{color:#a9c2d8}
.kb{display:grid;gap:4px;margin-top:4px;width:100%}
.kb .r{display:flex;gap:4px}
.kb span{flex:1;text-align:center;background:rgba(36,52,70,.92);border-radius:8px;padding:8px 6px;font-size:14px;
 color:#e8f1fa;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rkb{background:#17212b;padding:6px;display:grid;gap:6px;border-top:1px solid #0b1118}
.rkb .r{display:flex;gap:6px}
.rkb span{flex:1;text-align:center;background:#232e3c;border-radius:8px;padding:11px 6px;font-size:14px}
"""


def page(title: str, subtitle: str, bubbles: list[dict], reply_kb: list[list[str]]) -> str:
    rows = []
    for b in bubbles:
        kb = ""
        if b["inline"]:
            kb = '<div class="kb">' + "".join(
                '<div class="r">' + "".join(f"<span>{t}</span>" for t in r) + "</div>" for r in b["inline"]
            ) + "</div>"
        rows.append(f'<div class="row {b["side"]}"><div class="b">{b["html"]}</div>{kb}</div>')
    rkb = ""
    if reply_kb:
        rkb = '<div class="rkb">' + "".join(
            '<div class="r">' + "".join(f"<span>{t}</span>" for t in r) + "</div>" for r in reply_kb
        ) + "</div>"
    initials = "".join(w[0] for w in title.split()[:2]).upper()
    return (f'<!doctype html><meta charset="utf-8"><style>{CSS}</style>'
            f'<div class="top"><div class="ava">{initials}</div><div><div class="name">{title}</div>'
            f'<div class="sub">{subtitle}</div></div></div>'
            f'<div class="chat">{"".join(rows)}</div>{rkb}')


def main() -> None:
    for f in sorted(OUT.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        for i, fr in enumerate(data["frames"], 1):
            name = f"{data['bot']}-{i}-{fr['name']}.html"
            (OUT / name).write_text(page(fr["title"], fr["subtitle"], fr["bubbles"], fr["reply_kb"]), encoding="utf-8")
            print("wrote", name)


if __name__ == "__main__":
    main()

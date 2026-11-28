# 已批准的 haha.meme 链上 SVG 参考生成器。
# svg(name, tld) 的输出是设计真源。链上拼接规则见 docs/contracts/SVG.md。
# 本文件不是合约。不要把它编译进 Solidity；合约使用同目录的 *.svgpart 常量。

def doge(x,y,s):  # shiba head
    return f'''<g transform="translate({x},{y}) scale({s})"><path d="M-30 -20 L-22 -48 L-6 -28 L6 -28 L22 -48 L30 -20 Q38 10 0 32 Q-38 10 -30 -20Z" fill="#E8A23A" stroke="#7A4A10" stroke-width="3"/><path d="M-18 8 Q0 30 18 8 Q0 18 -18 8Z" fill="#FFF1D6"/><circle cx="-11" cy="-6" r="3.5" fill="#3A2A10"/><circle cx="11" cy="-6" r="3.5" fill="#3A2A10"/><ellipse cx="0" cy="8" rx="5" ry="3.5" fill="#3A2A10"/></g>'''
def frog(x,y,s):
    return f'''<g transform="translate({x},{y}) scale({s})"><ellipse cx="0" cy="8" rx="34" ry="24" fill="#5BA83B" stroke="#2C5A1A" stroke-width="3"/><ellipse cx="-14" cy="-14" rx="14" ry="11" fill="#5BA83B" stroke="#2C5A1A" stroke-width="3"/><ellipse cx="14" cy="-14" rx="14" ry="11" fill="#5BA83B" stroke="#2C5A1A" stroke-width="3"/><ellipse cx="-14" cy="-14" rx="8" ry="6" fill="#fff"/><ellipse cx="14" cy="-14" rx="8" ry="6" fill="#fff"/><circle cx="-11" cy="-14" r="3" fill="#111"/><circle cx="17" cy="-14" r="3" fill="#111"/><path d="M-22 14 Q0 24 22 14" fill="none" stroke="#A0322A" stroke-width="5" stroke-linecap="round"/></g>'''
def coin(x,y,s,sym):
    return f'''<g transform="translate({x},{y}) scale({s})"><circle r="26" fill="#F5C542" stroke="#9A6B00" stroke-width="3"/><circle r="19" fill="none" stroke="#9A6B00" stroke-width="2"/><text y="9" text-anchor="middle" font-family="Arial" font-size="24" font-weight="bold" fill="#9A6B00">{sym}</text></g>'''
def svg(name,tld):
    n=len(name+tld)+1
    fsz=int(min(96,420/n/0.58))
    tex=(coin(40,430,0.9,"Ð")+doge(105,420,0.85)+frog(180,435,0.8)+coin(250,410,0.75,"S")+doge(320,438,0.7)+frog(395,415,0.85)+coin(465,440,0.8,"Ð")
         +doge(30,480,0.6)+coin(140,485,0.6,"P")+frog(285,482,0.6)+coin(355,488,0.55,"Ð")+doge(440,486,0.6))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="500" height="500" viewBox="0 0 500 500"><defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFC21A"/><stop offset="1" stop-color="#FF7A1A"/></linearGradient></defs><rect width="500" height="500" fill="url(#g)"/><g opacity="0.28">{tex}</g><text x="250" y="62" text-anchor="middle" font-family="Arial" font-size="30" font-weight="bold" fill="#fff">haha.meme</text><text x="250" y="{250+fsz*0.35:.0f}" text-anchor="middle" font-family="Arial" font-size="{fsz}" font-weight="bold" fill="#fff">{name}.{tld}</text><text x="250" y="468" text-anchor="middle" font-family="Arial" font-size="24" font-weight="bold" fill="#fff" letter-spacing="2">agent id</text></svg>'''

if __name__ == "__main__":
    from pathlib import Path
    here = Path(__file__).resolve().parent
    samples = here / "samples"
    samples.mkdir(exist_ok=True)
    for name, tld in (("a", "haha"), ("myagent", "meme"), ("superlongagentname2026", "haha")):
        (samples / f"{name}.{tld}.svg").write_text(svg(name, tld), encoding="utf-8")

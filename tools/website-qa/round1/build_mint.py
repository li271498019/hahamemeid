# One-off generator: derive site/mint.html from site/ai.html (head, nav, footer) + tools/src/mint-body.html.
import re, pathlib
root = pathlib.Path(__file__).resolve().parent.parent
ai = (root / "site/ai.html").read_text().split("\n")
body = (root / "tools/src/mint-body.html").read_text().rstrip("\n")
head = "\n".join(ai[:62]) + "\n"
head = head.replace('data-i18n-title="ai.docTitle"', 'data-i18n-title="dog.docTitle"').replace('data-i18n="ai.docTitle"', 'data-i18n="dog.docTitle"')
head = head.replace('data-i18n="ai.docDesc"', 'data-i18n="dog.docDesc"')
head = head.replace("haha.meme · Haha AI 链上运行的AI大模型", "haha.meme · Haha Dog 铸造：链上 AI 像素狗，免费铸造")
head = head.replace("Haha AI：权重和推理都在智能合约里的 AI 大模型。输入任意种子，现场画出一只像素狗，可验证、可复核。",
                    "Haha Dog：由链上运行的 Haha AI 大模型现场画出的像素狗。免费铸造，总量 10,000，持有 .ai 即可，铸造后约 4 个区块自动出图，可免费重铸。")
head = head.replace("https://haha.meme/ai", "https://haha.meme/mint").replace("haha.meme：Haha AI", "haha.meme：Haha Dog")
head = head.replace('<link rel="stylesheet" href="/css/haha-ai.css?v=1">', '<link rel="stylesheet" href="/css/haha-ai.css?v=1">\n<link rel="stylesheet" href="/css/haha-dog.css?v=1">')
# nav: current page is the mint link, not the Haha AI link
head = head.replace('<a href="/ai.html" aria-current="page">', '<a href="/ai.html">').replace('<a href="/mint.html">', '<a href="/mint.html" aria-current="page">')
foot_start = next(i for i, l in enumerate(ai) if l.startswith("<footer>"))
foot = ai[foot_start]
tail = """</div>
<div id="toast" role="status"></div>
<script src="/js/addresses.js?v=9"></script>
<script src="/js/rpc.js?v=18"></script>
<script src="/js/i18n.js?v=72"></script>
<script src="/js/haha-ai-i18n.js?v=2"></script>
<script src="/js/haha-dog-i18n.js?v=1"></script>
<script src="/js/instructions.js?v=12"></script>
<script src="/js/session.js?v=8"></script>
<script src="/js/ui.js?v=9"></script>
<script src="/js/haha-ai-model.js?v=1"></script>
<script src="/js/haha-dog.js?v=1"></script>
<script src="/js/haha-dog-mint.js?v=1"></script>
</body>
</html>
"""
(root / "site/mint.html").write_text(head + body + "\n" + foot + "\n" + tail)

# Haha Dog site changes (local only, nothing pushed or deployed)

Base: live release c2ba731 (copied from the server, read-only). Patch paths are `web/site/...`.
- `haha-dog-site.patch`  apply from the repo root with `git apply`
- `site/`                full patched tree (git repo; `git diff` against its single "base" commit = the patch)
- `previews/`            desktop + mobile, zh + en screenshots, plus the agent commands the buttons copy
- `tools/`               local server, screenshot/flow tests, chain_check.js (browser model vs deployed svgOf)

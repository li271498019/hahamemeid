Round 3 (deployed live as release 20261128-055102-haha-dog-r3, UTC server clock = 2026-11-28 13:51 UTC+8; rollback = 20261128-045829-haha-dog-r2)
- site-round3.patch  git diff --binary vs live site (= private main ccad923 web/site); apply: git apply --directory=web/site site-round3.patch
- site/ working tree (git repo: base = live ccad923), live-snapshot/ = untouched copy of the r2 release
- previews/ local, live-shots/ production screenshots, tools/ (make_placeholder.js/.py regenerate assets/dog/unrendered.gif from the same model + keyframes as ai.html)

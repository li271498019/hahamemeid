# C 的部署指南

给网站开发 C。先上测试站，老板验收通过之后再上正式站。不要把 IP、SSH 密码、私钥、证书私钥、Cloudflare API 凭据写进仓库、提交信息或本文。

现有正式站的目录和 nginx 写法在 `docs/website/DEPLOY.md`。本文沿用那套「新目录 + 符号链接 + nginx reload」，给测试站加一套独立的目录和 server 块。

## 两个站点

| | 测试站 | 正式站 |
| --- | --- | --- |
| 域名 | `ddao.app` | `haha.meme` |
| DNS | 已经解析。Cloudflare 在前面，由老板管理 | 同样由老板管理 |
| 何时部署 | 现在就可以 | 老板书面验收测试站之后 |
| 搜索引擎 | 必须 noindex | 必须去掉 noindex |
| 预览旗标 | `HAHA_PREVIEW=false`，用真实主网数据 | 同左 |
| 合约 | BSC 主网，与正式站相同 | BSC 主网 |

测试站和正式站读的是同一套主网合约。测试站不是测试网。在测试站上铸造会真实花费 gas，也会占掉真实名字和一小时冷却。验收时用老板指定的 `.ai`，不要用随手铸的热门短名。

`ddao.app` 的 noindex 用 nginx 响应头，不要把 `web/site/js/config.js` 的 `HAHA_PREVIEW` 留在 `true`。那个开关会重新打开「预览版」顶栏。

```nginx
add_header X-Robots-Tag "noindex, nofollow" always;
```

正式站的 server 块不要加这行。正式站 HTML 里也不要有 `<meta name="robots" content="noindex, nofollow">`。

## SSH

老板把 SSH 密码单独交给 C，不经过仓库、issue 或聊天记录里的粘贴文件。

1. C 用该密码登录。
2. C 把自己的公钥写入服务器上 C 这个账号的 `authorized_keys`。公钥只放在服务器上，不提交到 git。
3. C 确认新开一个终端、用密钥能登录之后，再关闭 SSH 密码登录（`PasswordAuthentication no`），并重载 sshd。
4. 之后 B 和 C 都只用密钥登录。不要把密码改回可用，也不要在文档里记录密码是否曾经是哪一串。

如果老板已经为正式站关过密码登录，而测试站是同一台机器，C 不要为了图方便再打开密码登录。向老板要一个一次性的密钥安装方式即可。本文不假设 IP，也不假设机器是不是同一台。`DEPLOY.md` 里正式站是一台 Ubuntu 24.04，前面是 Cloudflare。测试站的 nginx 和发布目录按下面写，即使在同一台机器上也要分开。

## 目录

正式站维持 `DEPLOY.md`：

- 发布目录 `/var/www/releases/<UTC 时间戳>/`
- 符号链接 `/var/www/haha.meme` 指向当前发布目录
- 目录里放 `.release`，内容是 git commit SHA
- 属主 `www-data`

测试站用另一套，不要和正式站共用链接：

- 发布目录 `/var/www/releases-ddao/<UTC 时间戳>/`
- 符号链接 `/var/www/ddao.app`
- 同样写入 `.release`
- 不要把 `README.md` 打进发布包。发布包是 `web/site/` 的内容，文件在归档根上，不要多一层目录。

回滚是把符号链接指回上一个发布目录，然后 `nginx -t` 且 reload。不要在正在被链接指向的目录里覆盖文件。

## nginx

正式站的 server 块见 `DEPLOY.md`，`server_name haha.meme`，`root /var/www/haha.meme`。

测试站另写一个 server 块，不要往正式站的 `server_name` 里追加域名。

```nginx
server {
    server_name ddao.app;
    root /var/www/ddao.app;
    index index.html;

    add_header X-Robots-Tag "noindex, nofollow" always;

    location ~ /\. {
        deny all;
    }

    location = /skill.md {
        types { }
        default_type text/markdown;
        charset utf-8;
        charset_types text/markdown;
        add_header Cache-Control "no-store, no-cache, must-revalidate" always;
        add_header X-Robots-Tag "noindex, nofollow" always;
        add_header X-Content-Type-Options nosniff always;
    }

    location / {
        try_files $uri $uri.html $uri/ =404;
    }

    location ~* \.(webp|png|svg|ico|css|js|woff2)$ {
        expires 7d;
        add_header Cache-Control "public" always;
        add_header X-Robots-Tag "noindex, nofollow" always;
        try_files $uri =404;
    }
}
```

`/tasks`、`/games` 以及带 `.html` 的旧地址，在两个站点都 301 到 `/earn`：

```nginx
location = /tasks { return 301 /earn; }
location = /tasks.html { return 301 /earn; }
location = /games { return 301 /earn; }
location = /games.html { return 301 /earn; }
```

HTTP 用 301 到 HTTPS。证书用 certbot 向 Let's Encrypt 申请，自动续期。不要把证书私钥拷进仓库。Cloudflare 若是「完全」或「严格」模式，源站仍要有一张浏览器信任的证书。橙云代理的开关由老板在 Cloudflare 控制，C 不要改 DNS。

正式站的 `skill.md` 同样要 `no-store`，并且同样要有 `charset utf-8;` 和 `charset_types text/markdown;`。没有 `charset_types`，nginx 不会给 `text/markdown` 带上 charset，浏览器会把中文显示成乱码。正式站不要加 `X-Robots-Tag`。

字体是 `woff2`，缓存规则里要带上这个后缀，否则会落到默认类型。

## 发布步骤

测试站和正式站步骤相同，只换目录、链接和 server_name。

1. 在仓库里确认 `window.HAHA_PREVIEW` 是 `false`，地址与 `docs/contracts/DEPLOYED.md` 一致，`skill.md` 的 `version` 已更新。
2. 打包 `web/site`，排除 `README.md`。
3. `scp` 到服务器。命令里的主机名用老板提供的 SSH 配置里的 Host 别名，不要把 IP 写进脚本后提交。
4. 解压到新的发布时间目录。
5. 写入 `.release`。
6. `chown -R www-data:www-data` 该目录。
7. 把符号链接切到新目录：`ln -sfn /var/www/releases-ddao/<时间戳> /var/www/ddao.app`。正式站把链接换成 `/var/www/haha.meme`。
8. `nginx -t`。失败则不要 reload，链接先指回去。
9. reload nginx。
10. 按下面的清单冒烟。

## 测试站冒烟

这些 URL 都用 `https://ddao.app`：

- `/`、`/market`、`/erc8004`、`/earn`、`/how`、`/agent`、`/skill.md` 返回 200。
- `/tasks` 和 `/games` 返回 301，Location 是 `/earn`。
- 响应头有 `X-Robots-Tag: noindex, nofollow`。
- `/skill.md` 的类型是 `text/markdown`，且 `Cache-Control` 含 `no-store`。
- 页面源码没有「预览版 · 合约尚未上线」。
- 首页标题是「免费铸造您的haha id」。
- 随机打开一条市场挂单，价格与 BscScan 上 `HahaMarketplace.listings` 一致。

然后按 `docs/website/AGENT-INSTRUCTIONS-AND-SKILL-GUIDE.md` 末尾的真实 agent 测试做一遍。

## 老板验收之后才上正式站

C 不要自己把正式站切过去。老板在测试站确认文案、字体、金币雨、市场列数、积分页和一笔真实铸造之后，C 再用同一份发布包部署到 `/var/www/releases/`，把 `/var/www/haha.meme` 指过去。

正式站额外检查：

- 没有 `X-Robots-Tag: noindex`，HTML 里没有 noindex。
- 复制出的指令包含 `https://haha.meme/skill.md`，不包含 `ddao.app`。
- `https://haha.meme/skill.md` 的地址表与测试站一致，且 `no-store`。
- `DEPLOY.md` 列出的旧路径 `/market`、`/erc8004`、`/how`、`/agent` 仍是 200；`/tasks` 和 `/games` 改为 301。

## 回滚

1. 看上一个发布目录的 `.release`，确认那是要回去的 SHA。
2. `ln -sfn` 指回该目录。测试站动 `/var/www/ddao.app`，正式站动 `/var/www/haha.meme`。
3. `nginx -t` 后 reload。
4. 再请求一次 `/` 和 `/skill.md`。skill 若跟着静态目录走，回滚代码也会回滚 skill，这是对的。
5. 不要删除刚失败的那个目录，方便对比。至少保留最近两个发布目录。

链上交易不能用网站回滚。若正式站已经让用户铸出名字，回滚网站不会撤销 `NameMinted`。

## 上线前清单

- [ ] 仓库里没有 IP、密码、私钥、证书、Cloudflare token
- [ ] `HAHA_PREVIEW` 为 false，页面无预览条文案
- [ ] 十个合约地址和 `.ai` 注册表与 `DEPLOYED.md` 一致
- [ ] `skill.md` 版本号已加，`no-store`，类型是 markdown
- [ ] 复制指令在正式站指向 `https://haha.meme/skill.md`
- [ ] 测试站 noindex，正式站可索引
- [ ] `/tasks`、`/games` 跳到 `/earn`
- [ ] 字体从本站加载，并带有 OFL 许可证文件
- [ ] 市场在所有桌面宽度都是每行 4 个，800px 及以下 auto-fit；页面没有「外部版税」；数据不是 `mock.js`
- [ ] 真实 agent 在测试站完成铸造、冷却拒绝、挂单购买、评分修改、签到
- [ ] 老板验收测试站之后才切正式站
- [ ] 知道回滚要指回的上一个发布目录

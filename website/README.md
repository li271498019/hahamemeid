# haha.meme 网站

六页静态站：haha id、交易市场、ERC-8004、任务、游戏、工作原理。没有构建步骤，也不连接钱包。写操作是一段复制给用户自己的 agent 的指令。

视觉和 `web/prototype/` 里已经拍板的 haha id 一致：橙黄底、白字、原创硬币雨、像素笑脸硬币。演示数据都标了「演示数据」，集中在 `js/mock.js`。

## 本地看

```bash
cd web/site
python3 -m http.server 8787
```

打开 http://127.0.0.1:8787/ 。

## 部署

线上步骤、回滚和这次预览的记录在 [`docs/website/DEPLOY.md`](../../docs/website/DEPLOY.md)。网站根 `/var/www/haha.meme` 是指向 `/var/www/releases/<UTC 时间戳>/` 的符号链接。

nginx 需要能把干净地址落到对应的 html 上：

```nginx
server {
    server_name haha.meme;
    root /var/www/haha.meme;
    index index.html;

    location / {
        try_files $uri $uri.html $uri/ =404;
    }
}
```

这样 `/market` 和 `/market.html` 都打开交易市场。不要在地址后面再加一层目录，否则相对链接会错。

预览开关只有一处：`js/config.js` 里的 `window.HAHA_PREVIEW`。现在是 `true`，会显示顶栏、复制按钮旁的「主网上线后才会生效」，以及 `<meta name="robots" content="noindex, nofollow">`。合约上线时改成 `false` 即可，不用改页面。

分享图路径是站点根上的 `/assets/logo/haha-logo.png`。

## 换 logo

最终文件都在 `assets/logo/`。导航用 `haha-logo-nav-64.png`，放在「haha.meme」文字左边。要换图时保持这些文件名：

- `haha-logo-nav-64.png` 导航
- `favicon.ico`、`favicon-32.png`、`favicon-180.png` 图标
- `haha-logo.png` 分享图

## 换数据

链上索引还没有。挂单、成交、agent、评价和任务完成状态都在 `js/mock.js`。接上 API 时替换这个文件里的数据，页面脚本不用改。

合约地址在工作原理页。十个项目合约写着 `TBD after mainnet deploy`。币安 `.ai` 注册表、管理员和手续费地址用的是规格里已经写明的地址，没有新编地址。

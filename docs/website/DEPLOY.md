# 网站发布

给后面接手的人。这里只记机器角色、目录和步骤。不写 IP、密钥、证书私钥或 Cloudflare 凭据。

## 2026-11-21 预览

- 时间：2026-11-21 09:15（UTC+8）。
- 地址：https://haha.meme
- 提交：`8fe44c2a33712b85afa80b830921bfae3abd9d40`
- 归档 sha256：`5118d5ffdaca616a8f0d5c88c7868ed4207b07bd3eb9da88272cf84effbe9879`
- 预览模式开着：`web/site/js/config.js` 里 `window.HAHA_PREVIEW = true`。顶栏、复制按钮旁的「主网上线后这条指令才会生效」，以及 `noindex`，都由这一处控制。

## 服务器

- Vultr 上的 Ubuntu 24.04，nginx 1.24。
- 前面是 Cloudflare 代理。DNS 由项目方管理。
- HTTPS 证书是 Let's Encrypt，90 天，用 certbot 申请，自动续期 timer 已启用。
- HTTP 用 301 转到 HTTPS。
- SSH 只允许密钥登录，密码登录已关闭。
- ufw 放行 22、80、443。

## 目录

每次发布解压到一个新目录：

`/var/www/releases/<UTC 时间戳>/`

目录里放一个 `.release` 文件，内容是这次的 commit SHA。

`/var/www/haha.meme` 是指向当前发布目录的符号链接。nginx 的 root 指这个链接。回滚就是把链接指回旧目录，然后重新加载 nginx。

`README.md` 不发到服务器上。

## nginx

- `root /var/www/haha.meme;`
- `try_files $uri $uri.html $uri/ =404;`，所以 `/market` 和 `/market.html` 都能打开。`/` 是 `index.html`（haha id）。
- 拒绝点文件。
- `webp`、`png`、`svg`、`ico`、`css`、`js` 缓存 7 天。
- `/site.webmanifest` 的类型是 `application/manifest+json`。线上 server 块是独立文件 `/etc/nginx/sites-enabled/haha.meme`。

```nginx
server {
    server_name haha.meme;
    root /var/www/haha.meme;
    index index.html;

    location ~ /\. {
        deny all;
    }

    location = /site.webmanifest {
        types { }
        default_type application/manifest+json;
    }

    location / {
        try_files $uri $uri.html $uri/ =404;
    }

    location ~* \.(webp|png|svg|ico|css|js)$ {
        expires 7d;
        add_header Cache-Control "public";
        try_files $uri =404;
    }
}
```

HTTP 到 HTTPS 的 301，以及证书路径，由 certbot 配好，不要把私钥写进仓库。

## 发布步骤

1. 在仓库里把 `web/site` 打成归档。文件在归档根上，不要多套一层目录。不要把 `README.md` 打进去。
2. `scp` 到服务器。
3. 解压到新的 `/var/www/releases/<UTC 时间戳>/`。
4. 把 commit SHA 写入该目录的 `.release`。
5. `chown` 给 `www-data`。
6. 把 `/var/www/haha.meme` 指到这个新目录。
7. `nginx -t`，通过后 reload。
8. 冒烟：下面这些地址都要返回 200。
   - `/`
   - `/market`
   - `/erc8004`
   - `/tasks`
   - `/games`
   - `/how`
   - `/agent`

## 正式上线前

- 把 `window.HAHA_PREVIEW` 改成 `false`。
- 在工作原理页填上十个项目合约的主网地址。
- 发布 `skill.md`。
- 用真实的索引或 API 换掉 `web/site/js/mock.js`。

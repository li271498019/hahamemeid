p="/etc/nginx/sites-available/haha.meme"
s=open(p).read()
old_static='  location ~* \\.(webp|png|svg|ico|css|js)$ { expires 7d; add_header Cache-Control "public"; }\n'
old_root='  location / { try_files $uri $uri.html $uri/ =404; }\n'
assert old_static in s and old_root in s and "/api/" not in s
new='''  location = /skill.md {
    types { }
    default_type text/markdown;
    charset utf-8;
    add_header Cache-Control "no-store, no-cache, must-revalidate" always;
    add_header X-Content-Type-Options nosniff always;
  }
  location = /tasks { return 301 /earn; }
  location = /tasks.html { return 301 /earn; }
  location = /games { return 301 /earn; }
  location = /games.html { return 301 /earn; }
  location /api/ {
    proxy_pass http://127.0.0.1:8787/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 10s;
  }
  location /rpc/ {
    proxy_pass https://bsc-dataseed.binance.org/;
    proxy_ssl_server_name on;
    proxy_set_header Host bsc-dataseed.binance.org;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_connect_timeout 3s;
    proxy_read_timeout 8s;
  }
  location / { add_header Cache-Control "no-cache" always; try_files $uri $uri.html $uri/ =404; }
'''
s=s.replace(old_root,new)
s=s.replace(old_static,'  location ~* \\.(webp|png|svg|ico|css|js|woff2)$ { expires 7d; add_header Cache-Control "public" always; try_files $uri =404; }\n')
open(p,"w").write(s)
print("patched")

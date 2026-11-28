#!/usr/bin/env python3
"""Add the /agent-chat/ nginx location + rate-limit zone. Run as root."""
import subprocess, sys

RATE_LIMIT = "/etc/nginx/conf.d/rate-limit.conf"
SITE = "/etc/nginx/sites-enabled/haha.meme"
ZONE_LINE = "limit_req_zone $binary_remote_addr zone=agentchat:10m rate=120r/m;\n"

with open(RATE_LIMIT, encoding="utf-8") as f:
    rl = f.read()
if "zone=agentchat" not in rl:
    if not rl.endswith("\n"):
        rl += "\n"
    rl += ZONE_LINE
    with open(RATE_LIMIT, "w", encoding="utf-8") as f:
        f.write(rl)
    print("rate-limit zone added")
else:
    print("rate-limit zone already present")

LOCATION = """  location /agent-chat/ {
    # haha agent channel (2026-11-27, C): REST API for the agent dialog.
    # Service (systemd haha-agent-chat) listens on 127.0.0.1:8899.
    # proxy_pass trailing slash strips the /agent-chat/ prefix.
    limit_req zone=agentchat burst=20 nodelay;
    limit_req_status 429;
    limit_req_log_level warn;
    limit_conn conn 20;
    client_max_body_size 25m;
    add_header Retry-After 60 always;
    include /etc/nginx/snippets/security-headers-haha.conf;
    proxy_pass http://127.0.0.1:8899/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 60s;
    proxy_send_timeout 60s;
  }
  location = /agent-chat {
    return 301 /agent-chat/;
  }

"""
with open(SITE, encoding="utf-8") as f:
    site = f.read()
if "location /agent-chat/" in site:
    print("location already present")
else:
    anchor = "  location / {\n"
    assert site.count(anchor) == 1, "anchor not unique"
    site = site.replace(anchor, LOCATION + anchor, 1)
    with open(SITE, "w", encoding="utf-8") as f:
        f.write(site)
    print("location added")

r = subprocess.run(["nginx", "-t"], capture_output=True, text=True)
print(r.stdout)
print(r.stderr)
if r.returncode != 0:
    print("nginx -t FAILED, not reloading")
    sys.exit(1)
r = subprocess.run(["systemctl", "reload", "nginx"], capture_output=True, text=True)
print("nginx reload rc:", r.returncode)
print(r.stdout)
print(r.stderr)
print("NGINX DONE")

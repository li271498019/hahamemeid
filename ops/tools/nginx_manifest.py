p="/etc/nginx/sites-enabled/haha.meme"
s=open(p).read()
if "site.webmanifest" not in s:
    anchor="  location = /tasks { return 301 /earn; }\n"
    assert anchor in s
    s=s.replace(anchor,'  location = /site.webmanifest { types { } default_type application/manifest+json; add_header Cache-Control "public, max-age=86400" always; }\n'+anchor,1)
    open(p,"w").write(s); print("added")

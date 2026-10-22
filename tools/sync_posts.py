#!/usr/bin/env python3
"""Sync the blog in content/posts/ to a running Vyasa site.

Each content/posts/<slug>.md (front matter + Markdown) becomes a post. A post
whose publish_at (content/posts/schedule.json) is in the future is created
as `scheduled`; Vyasa's scheduler publishes it then. Re-running updates
posts in place and never moves an already published post back to scheduled.

    VYASA_URL=https://setucp.com VYASA_ADMIN_EMAIL=... VYASA_ADMIN_PASSWORD=... \
      python3 tools/sync_posts.py [--dry-run] [slug ...]

--dry-run converts every post and prints a summary without a network call.
"""

import datetime as dt
import html
import http.cookiejar
import json
import mimetypes
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
POSTS = os.path.join(HERE, "..", "content", "posts")
PERMALINK = "/blog/{slug}"
BLOG_PAGE = os.path.join(HERE, "..", "content", "blog-page.json")


def die(msg):
    sys.exit(f"sync_posts: error: {msg}")


# ---- Markdown -> Vyasa blocks ------------------------------------------------

def post_path(slug):
    return PERMALINK.replace("{slug}", slug)


def inline(text):
    """Markdown inline -> the allowlisted inline HTML Vyasa stores."""
    out, pos = [], 0
    pattern = re.compile(r"`([^`]+)`|\*\*(.+?)\*\*|\*(.+?)\*|\[([^\]]+)\]\(([^)\s]+)\)")
    for m in pattern.finditer(text):
        out.append(html.escape(text[pos:m.start()], quote=False))
        code, bold, em, label, href = m.groups()
        if code is not None:
            out.append(f"<code>{html.escape(code, quote=False)}</code>")
        elif bold is not None:
            out.append(f"<strong>{inline(bold)}</strong>")
        elif em is not None:
            out.append(f"<em>{inline(em)}</em>")
        else:
            if href.startswith("post:"):
                href = post_path(href[5:])
            out.append(f'<a href="{html.escape(href)}">{inline(label)}</a>')
        pos = m.end()
    out.append(html.escape(text[pos:], quote=False))
    return "".join(out)


def para(text):
    return {"kind": "paragraph", "attrs": {"text": inline(text)}}


IMAGE = re.compile(r'^!\[([^\]]*)\]\(([^)\s]+)(?:\s+"([^"]*)")?\)\s*$')
LIST_ITEM = re.compile(r"^(\s*)([-*]|\d+\.)\s+(.*)$")


def to_blocks(md, images):
    """`images` maps a relative image path to its uploaded media dict."""
    lines = md.split("\n")
    blocks, i = [], 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith("```"):
            lang = line[3:].strip()
            body = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                body.append(lines[i])
                i += 1
            i += 1
            attrs = {"code": "\n".join(body)}
            if lang:
                attrs["language"] = lang
            blocks.append({"kind": "code", "attrs": attrs})
            continue
        h = re.match(r"^(#{2,4})\s+(.*)$", line)
        if h:
            blocks.append({"kind": "heading", "attrs": {"level": len(h.group(1)), "text": inline(h.group(2).strip())}})
            i += 1
            continue
        m = IMAGE.match(line.strip())
        if m:
            alt, src, caption = m.group(1), m.group(2), m.group(3) or ""
            media = images[src]
            attrs = {"url": f"/api/v1/media/{media['id']}/raw", "mediaId": media["id"], "alt": alt}
            if caption:
                attrs["caption"] = inline(caption)
            if media.get("width") and media.get("height"):
                attrs["width"], attrs["height"] = media["width"], media["height"]
            blocks.append({"kind": "image", "attrs": attrs})
            i += 1
            continue
        if line.startswith(">"):
            body = []
            while i < len(lines) and lines[i].startswith(">"):
                body.append(lines[i].lstrip(">").strip())
                i += 1
            blocks.append({"kind": "quote", "attrs": {"text": inline(" ".join(body))}})
            continue
        if line.lstrip().startswith("|"):
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", c) for c in cells):
                    rows.append([inline(c) for c in cells])
                i += 1
            blocks.append({"kind": "table", "attrs": {"header": rows[0], "rows": rows[1:]}})
            continue
        if LIST_ITEM.match(line):
            blocks.append(parse_list(lines, i))
            i = blocks[-1].pop("_end")
            continue
        body = [line.strip()]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#{2,4}\s|```|>|\||!\[)", lines[i]) \
                and not LIST_ITEM.match(lines[i]):
            body.append(lines[i].strip())
            i += 1
        blocks.append(para(" ".join(body)))
    return blocks


def parse_list(lines, i):
    first = LIST_ITEM.match(lines[i])
    indent, ordered = len(first.group(1)), first.group(2)[0].isdigit()
    children = []
    while i < len(lines):
        m = LIST_ITEM.match(lines[i])
        if m and len(m.group(1)) == indent:
            text = [m.group(3).strip()]
            i += 1
            # Lazy continuation lines belong to the item.
            while i < len(lines) and lines[i].strip() and not LIST_ITEM.match(lines[i]) \
                    and lines[i].startswith(" "):
                text.append(lines[i].strip())
                i += 1
            children.append(para(" ".join(text)))
        elif m and len(m.group(1)) > indent:
            nested = parse_list(lines, i)
            i = nested.pop("_end")
            children.append(nested)
        else:
            break
    return {"kind": "list", "attrs": {"ordered": ordered}, "children": children, "_end": i}


def read_post(path):
    text = open(path, encoding="utf-8").read()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        die(f"{path}: no front matter")
    front = {}
    for line in m.group(1).split("\n"):
        if ":" in line:
            k, _, v = line.partition(":")
            front[k.strip()] = v.strip().strip('"')
    for key in ("title", "seo_title", "seo_description", "keyphrase", "excerpt", "category", "tags", "cover_alt"):
        if not front.get(key):
            die(f"{path}: front matter lacks {key}")
    return front, m.group(2)


# ---- HTTP --------------------------------------------------------------------

class Api:
    def __init__(self, base):
        self.base = base.rstrip("/") + "/api/v1"
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def csrf(self):
        for c in self.jar:
            if "csrf" in c.name.lower():
                return c.value
        return None

    def call(self, method, path, body=None, ctype="application/json", ok=(200, 201, 204)):
        data = body if isinstance(body, (bytes, type(None))) else json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=data, method=method)
        if data is not None:
            req.add_header("content-type", ctype)
        token = self.csrf()
        if token:
            req.add_header("x-csrf-token", token)
        try:
            with self.opener.open(req, timeout=120) as r:
                status, raw = r.status, r.read()
        except urllib.error.HTTPError as e:
            status, raw = e.code, e.read()
        if status not in ok:
            die(f"{method} {path}: HTTP {status} {raw[:300].decode(errors='replace')}")
        return status, (json.loads(raw) if raw else None)

    def upload(self, path, alt):
        boundary = uuid.uuid4().hex
        mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
        parts = [
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{os.path.basename(path)}"\r\n'
            f"Content-Type: {mime}\r\n\r\n".encode(),
            open(path, "rb").read(),
            f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="alt"\r\n\r\n{alt}\r\n--{boundary}--\r\n'.encode(),
        ]
        # The same bytes again return the existing item, so this is idempotent.
        media = self.call("POST", "/media", b"".join(parts), f"multipart/form-data; boundary={boundary}")[1]
        # The blurhash and dimensions are computed after the upload returns,
        # and a card shows its thumbnail only with a blurhash.
        for _ in range(20):
            if media.get("blurhash") and media.get("width"):
                break
            time.sleep(0.5)
            media = self.call("GET", f"/media/{media['id']}")[1]
        return media


def term_ids(api, cache, taxonomy, names):
    if taxonomy not in cache:
        cache[taxonomy] = {t["name"].lower(): t["id"] for t in api.call("GET", f"/terms?taxonomy={taxonomy}")[1]}
    ids = []
    for name in names:
        if name.lower() not in cache[taxonomy]:
            term = api.call("POST", "/terms", {"taxonomy": taxonomy, "name": name})[1]
            cache[taxonomy][name.lower()] = term["id"]
        ids.append(cache[taxonomy][name.lower()])
    return ids


def ensure_blog_page(api):
    page = json.load(open(BLOG_PAGE, encoding="utf-8"))
    status, found = api.call("GET", f"/posts/slug/page/{page['slug']}", ok=(200, 404))
    body = {k: page[k] for k in ("title", "slug", "content", "excerpt", "layout")}
    body["status"] = "published"
    if status == 200:
        api.call("PUT", f"/posts/{found['id']}", body)
        pid = found["id"]
    else:
        pid = api.call("POST", "/posts", {"type": "page", **body})[1]["id"]
    api.call("PUT", f"/posts/{pid}", {"meta": {"seo_title": page["seo_title"], "seo_description": page["seo_description"]}})
    print("page /blog")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    schedule = {s["slug"]: s for s in json.load(open(os.path.join(POSTS, "schedule.json")))}
    slugs = args or [s for s in schedule if os.path.exists(os.path.join(POSTS, f"{s}.md"))]
    posts = []
    for slug in slugs:
        front, md = read_post(os.path.join(POSTS, f"{slug}.md"))
        cover = os.path.join(POSTS, "covers", f"{slug}.png")
        if not os.path.exists(cover):
            die(f"missing cover {cover} (run tools/covers.mjs)")
        refs = [m.group(2) for m in map(lambda l: IMAGE.match(l.strip()), md.split("\n")) if m]
        for r in refs:
            if not os.path.exists(os.path.join(POSTS, r)):
                die(f"{slug}: missing image {r}")
        for link in re.findall(r"\]\(post:([^)]+)\)", md):
            if link not in schedule:
                die(f"{slug}: link to unknown post {link}")
        posts.append((slug, front, md, cover, refs))
    if dry:
        for slug, front, md, _, refs in posts:
            fake = {r: {"id": 0} for r in refs}
            blocks = to_blocks(md, fake)
            words = len(re.sub(r"```.*?```", "", md, flags=re.S).split())
            print(f"{schedule[slug]['publish_at']}  {slug}: {len(blocks)} blocks, {words} words, "
                  f"{len(refs)} images, seo_title {len(front['seo_title'])}c, desc {len(front['seo_description'])}c")
        return

    for var in ("VYASA_URL", "VYASA_ADMIN_EMAIL", "VYASA_ADMIN_PASSWORD"):
        if not os.environ.get(var):
            die(f"{var} is not set")
    api = Api(os.environ["VYASA_URL"])
    api.call("POST", "/auth/login", {"email": os.environ["VYASA_ADMIN_EMAIL"], "password": os.environ["VYASA_ADMIN_PASSWORD"]})
    api.call("PUT", "/options", {"permalink_pattern": PERMALINK})
    ensure_blog_page(api)

    now = dt.datetime.now(dt.timezone.utc)
    terms, media = {}, {}
    for slug, front, md, cover, refs in posts:
        for r in refs:
            if r not in media:
                media[r] = api.upload(os.path.join(POSTS, r), os.path.basename(r))
        blocks = to_blocks(md, media)
        cov = api.upload(cover, front["cover_alt"])
        ids = term_ids(api, terms, "category", [front["category"]]) + \
            term_ids(api, terms, "tag", [t.strip() for t in front["tags"].split(",") if t.strip()])
        at = dt.datetime.fromisoformat(schedule[slug]["publish_at"].replace("Z", "+00:00"))
        meta = {
            "seo_title": front["seo_title"],
            "seo_description": front["seo_description"],
            "seo_keyphrase": front["keyphrase"],
            "featured_media_id": str(cov["id"]),
            "featured_media_url": f"/api/v1/media/{cov['id']}/raw?variant=medium",
            "featured_blurhash": cov.get("blurhash") or "",
            "og_image": f"/api/v1/media/{cov['id']}/raw",
        }
        body = {
            "title": front["title"],
            "slug": slug,
            "content": {"schema_version": 1, "blocks": blocks},
            "excerpt": front["excerpt"],
            "term_ids": ids,
        }
        status, found = api.call("GET", f"/posts/slug/post/{slug}", ok=(200, 404))
        published = status == 200 and found.get("status") == "published"
        if not published:
            if at > now:
                body.update(status="scheduled", scheduled_for=at.isoformat())
            else:
                body["status"] = "published"
        if status == 200:
            api.call("PUT", f"/posts/{found['id']}", body)
            pid = found["id"]
        else:
            pid = api.call("POST", "/posts", body)[1]["id"]
        api.call("PUT", f"/posts/{pid}", {"meta": meta})
        print(f"{body.get('status', 'published'):9} {at:%Y-%m-%d %H:%M}Z  {post_path(slug)}")


if __name__ == "__main__":
    main()

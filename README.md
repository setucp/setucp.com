# Setu landing site (setucp.com)

`apply.sh` configures a running **Vyasa 0.2.0** instance as the public landing
page for [Setu](https://github.com/setucp/setu), entirely through Vyasa's HTTP
API. It is idempotent: run it again to update, never to duplicate.

## What it does

| Step | Endpoint |
|---|---|
| Log in (session cookie) | `POST /api/v1/auth/login` |
| Upload the icon (PNG; Vyasa refuses SVG in the media library) | `POST /api/v1/media` |
| Site title, tagline, language, `site_url`, favicon | `PUT /api/v1/options` |
| Install the `setu-landing` theme (a `.vytheme` zip built from `theme/`) | `GET/POST /api/v1/themes` |
| Activate it | `POST /api/v1/themes/{id}/activate` |
| Pages `/install` and `/security` (from `content/pages/*.json`) | `GET /api/v1/posts/slug/page/{slug}`, `POST/PUT /api/v1/posts[/{id}]` |
| Menus `main` (header) and `footer` | `GET/POST /api/v1/menus`, `POST /api/v1/menus/{id}/items`, `DELETE /api/v1/menus/items/{id}` |
| Verify `GET /` contains the landing sections | public |

**The home page is the theme's `index` layout.** Vyasa 0.2.0 has no "front
page" option: `GET /` always renders the active theme's `index` template.
All landing sections (hero, install, how it works, features, built for,
comparison, roadmap, call to action) are therefore in `theme/layout.json`
under `index`, built from Vyasa's native sections, and activating the theme
is what "sets the home page".

## Run

```sh
VYASA_URL=https://setucp.com \
VYASA_ADMIN_EMAIL=admin@example.com \
VYASA_ADMIN_PASSWORD='...' \
./apply.sh
```

Needs `bash`, `curl`, `jq` >= 1.7, `zip`, `sha256sum`. The admin account must
not have 2FA enabled. Credentials are read from the environment only and sent
from a temp file inside a private temp dir that is removed on exit. Optional:
`VYASA_SITE_URL` (public URL stored as `site_url`, default `VYASA_URL`),
`VYASA_INSECURE=1` (curl `-k`).

Re-runs: the theme package version is derived from a hash of `theme/`, so an
unchanged theme is not re-uploaded, and an edited one installs as a new
version and is activated (older versions stay installed and can be rolled
back with `POST /api/v1/themes/setu-landing/rollback`). Pages are updated by
slug; menu items are replaced only when they differ.

## Edit

- `content/site.json` title, tagline; `content/menu.json`, `content/footer-menu.json`
- `content/pages/*.json` page body as a Vyasa block document
- `theme/tokens.json` colours (light and dark), type, widths
- `theme/layout.json` the landing page itself
- `theme/assets/theme.css` styling; `theme/assets/fonts/` self-hosted Inter and
  Sora (Vyasa's CSP only allows same-origin fonts); `theme/assets/images/` brand SVGs

## Verify

```sh
curl -s https://setucp.com/ | grep -c 'Your binaries. Your servers. One control panel.'
curl -sI https://setucp.com/install | head -1
```

Then open the site in light and dark mode and at phone width. The theme follows
`prefers-color-scheme`.

#!/usr/bin/env bash
# Sets up the Setu landing site on a running Vyasa 0.2.0 instance through its
# HTTP API. Idempotent: re-running updates what exists instead of duplicating.
#
#   VYASA_URL=https://setucp.com \
#   VYASA_ADMIN_EMAIL=you@example.com \
#   VYASA_ADMIN_PASSWORD=... \
#   ./apply.sh
#
# Optional: VYASA_SITE_URL (public address stored as the site_url option;
# default VYASA_URL), VYASA_INSECURE=1 (curl -k, for a self-signed test host).
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
THEME_DIR="$HERE/theme"
CONTENT_DIR="$HERE/content"
THEME_NAME="setu-landing"

die() { printf 'apply.sh: error: %s\n' "$*" >&2; exit 1; }
log() { printf '==> %s\n' "$*"; }
trap 'die "failed at line $LINENO (command: $BASH_COMMAND)"' ERR

# ---- preflight --------------------------------------------------------------
for tool in curl jq zip sha256sum; do
  command -v "$tool" >/dev/null 2>&1 || die "required tool not found: $tool"
done
jq -ne --argjson n 1 '$n' >/dev/null 2>&1 || die "jq with --argjson support is required"
# Vyasa ids exceed 2^53; jq before 1.7 would silently round them.
jq_ver="$(jq --version | sed 's/^jq-//')"
case "$jq_ver" in
  1.[0-6]|1.[0-6].*) die "jq >= 1.7 is required (found $jq_ver): Vyasa ids exceed 2^53" ;;
esac
[ -n "${VYASA_URL:-}" ] || die "VYASA_URL is not set (e.g. https://setucp.com)"
[ -n "${VYASA_ADMIN_EMAIL:-}" ] || die "VYASA_ADMIN_EMAIL is not set"
[ -n "${VYASA_ADMIN_PASSWORD:-}" ] || die "VYASA_ADMIN_PASSWORD is not set"
BASE="${VYASA_URL%/}"
SITE_URL="${VYASA_SITE_URL:-$BASE}"
API="$BASE/api/v1"
for f in theme/manifest.toml theme/tokens.json theme/layout.json theme/assets/theme.css \
         content/site.json content/menu.json content/footer-menu.json; do
  [ -f "$HERE/$f" ] || die "missing file: $f"
done

WORK="$(mktemp -d)"
JAR="$WORK/cookies"
BODY="$WORK/body"
trap 'rm -rf "$WORK"' EXIT
trap 'die "failed at line $LINENO (command: $BASH_COMMAND)"' ERR
STATUS=""

CURL=(curl -sS --connect-timeout 10 --max-time 120)
[ "${VYASA_INSECURE:-}" = "1" ] && CURL+=(-k)

# req METHOD PATH [extra curl args...]  -> sets STATUS, writes $BODY.
# A JSON request body is passed with  --data-binary @file  by the caller.
req() {
  local method="$1" path="$2"; shift 2
  STATUS="$("${CURL[@]}" -o "$BODY" -w '%{http_code}' -X "$method" \
    -b "$JAR" -c "$JAR" "$@" "$API$path")" || die "cannot reach $BASE ($method $path)"
}
# ok  -> die with the server's message unless STATUS is 2xx.
ok() {
  case "$STATUS" in
    2??) return 0 ;;
    *) die "$1 failed: HTTP $STATUS $(jq -r '(.code // "") + ": " + (.message // "")' "$BODY" 2>/dev/null || head -c 300 "$BODY")" ;;
  esac
}
# json_req METHOD PATH JSON
json_req() {
  local method="$1" path="$2" json="$3"
  printf '%s' "$json" > "$WORK/req.json"
  req "$method" "$path" -H 'content-type: application/json' --data-binary "@$WORK/req.json"
}

# ---- 1. log in --------------------------------------------------------------
log "Logging in to $BASE as the admin"
# The credentials go over stdin, never on a command line.
jq -n --arg email "$VYASA_ADMIN_EMAIL" --arg password "$VYASA_ADMIN_PASSWORD" \
  '{email: $email, password: $password}' > "$WORK/login.json"
req POST /auth/login -H 'content-type: application/json' --data-binary "@$WORK/login.json"
rm -f "$WORK/login.json"
if [ "$STATUS" = "401" ] || [ "$STATUS" = "403" ]; then
  die "login rejected (HTTP $STATUS): check VYASA_ADMIN_EMAIL / VYASA_ADMIN_PASSWORD"
fi
if [ "$STATUS" = "428" ] || jq -e '.code == "mfa_required"' "$BODY" >/dev/null 2>&1; then
  die "this account has two-factor authentication on; use an admin account without it for this script"
fi
ok "login"
ROLE="$(jq -r '.role // ""' "$BODY")"
[ "$ROLE" = "admin" ] || [ "$ROLE" = "owner" ] || die "the account has role '$ROLE'; an administrator is required"

# ---- 2. logo and favicon (media library) ----------------------------------------
log "Uploading the logo"
LOGO_FILE="$CONTENT_DIR/media/setu-icon-512.png"
[ -f "$LOGO_FILE" ] || die "missing $LOGO_FILE"
# The same bytes again return the existing item (HTTP 200), so this is idempotent.
req POST /media -F "file=@$LOGO_FILE;type=image/png" -F "alt=Setu"
ok "logo upload"
LOGO_ID="$(jq -r '.id' "$BODY")"
[ -n "$LOGO_ID" ] && [ "$LOGO_ID" != "null" ] || die "logo upload returned no id"

# ---- 3. site settings -------------------------------------------------------
log "Setting site title, tagline and logo"
OPTIONS="$(jq -c --arg url "$SITE_URL" --argjson logo "$LOGO_ID" \
  '. + {site_url: $url, site_favicon_media_id: $logo}' \
  "$CONTENT_DIR/site.json")"
json_req PUT /options "$OPTIONS"
ok "site settings"

# ---- 4. theme ---------------------------------------------------------------
log "Packaging the theme"
STAGE="$WORK/theme"
mkdir -p "$STAGE"
cp -R "$THEME_DIR/." "$STAGE/"
# The package version is derived from the theme's content: unchanged files
# re-use the installed version, any edit installs a new one.
PKG_VERSION=$(
  { (cd "$THEME_DIR" && find . -type f ! -name manifest.toml -print0 | sort -z | xargs -0 sha256sum)
    grep -v '^version' "$THEME_DIR/manifest.toml"
  } | sha256sum | cut -c1-7 | { read -r hex; echo $(( 16#$hex + 1 )); }
)
sed -i "s/^version *=.*/version = $PKG_VERSION/" "$STAGE/manifest.toml"
PKG="$WORK/$THEME_NAME-$PKG_VERSION.vytheme"
(cd "$STAGE" && zip -X -q -r "$PKG" . -x '.*')

req GET /themes
ok "theme list"
THEME_ID="$(jq -r --arg n "$THEME_NAME" --argjson v "$PKG_VERSION" \
  '[.[] | select(.name == $n and .package_version == $v)][0].id // empty' "$BODY")"
if [ -n "$THEME_ID" ]; then
  log "Theme $THEME_NAME (package version $PKG_VERSION) is already installed"
else
  log "Installing theme $THEME_NAME (package version $PKG_VERSION)"
  req POST /themes -F "file=@$PKG;type=application/zip"
  ok "theme install"
  THEME_ID="$(jq -r '.id' "$BODY")"
fi
req POST "/themes/$THEME_ID/activate"
ok "theme activation"
# The home page IS the theme's `index` layout in Vyasa 0.2.0 (there is no
# "front page" option), so activating the theme is what sets the home page.

# ---- 5. pages ---------------------------------------------------------------
shopt -s nullglob
for file in "$CONTENT_DIR"/pages/*.json; do
  slug="$(jq -r '.slug' "$file")"
  log "Page /$slug"
  req GET "/posts/slug/page/$slug"
  if [ "$STATUS" = "200" ]; then
    id="$(jq -r '.id' "$BODY")"
    json_req PUT "/posts/$id" "$(jq -c '{title, slug, content, excerpt, status: "published",
      meta: {seo_description: .seo_description}}' "$file")"
    ok "update page $slug"
  elif [ "$STATUS" = "404" ]; then
    json_req POST /posts "$(jq -c '{type: "page", status: "published", title, slug, content, excerpt}' "$file")"
    ok "create page $slug"
    id="$(jq -r '.id' "$BODY")"
    json_req PUT "/posts/$id" "$(jq -c '{meta: {seo_description: .seo_description}}' "$file")"
    ok "page meta $slug"
  else
    ok "look up page $slug"
  fi
done

# ---- 6. menus ---------------------------------------------------------------
sync_menu() {
  local file="$1" slug name location id existing wanted
  slug="$(jq -r '.slug' "$file")"; name="$(jq -r '.name' "$file")"; location="$(jq -r '.location' "$file")"
  log "Menu '$slug'"
  req GET /menus; ok "menu list"
  id="$(jq -r --arg s "$slug" '[.[] | select(.slug == $s)][0].id // empty' "$BODY")"
  if [ -z "$id" ]; then
    json_req POST /menus "$(jq -nc --arg n "$name" --arg s "$slug" --arg l "$location" '{name: $n, slug: $s, location: $l}')"
    ok "create menu $slug"
    id="$(jq -r '.id' "$BODY")"
  fi
  req GET "/menus/$id"; ok "menu read"
  existing="$(jq -c '[.[1] | sort_by(.sort_order, .id)[] | {label, url}]' "$BODY")"
  wanted="$(jq -c '[.items[] | {label, url}]' "$file")"
  if [ "$existing" = "$wanted" ]; then
    echo "    already up to date"
    return 0
  fi
  # Replace the items: delete what is there, add the wanted ones in order.
  local item_ids item
  item_ids="$(jq -r '.[1][].id' "$BODY")"
  for item in $item_ids; do
    req DELETE "/menus/items/$item"; ok "delete menu item"
  done
  local n i=0
  n="$(jq '.items | length' "$file")"
  while [ "$i" -lt "$n" ]; do
    json_req POST "/menus/$id/items" "$(jq -c --argjson i "$i" '.items[$i] + {sort_order: $i}' "$file")"
    ok "add menu item"
    i=$((i + 1))
  done
}
sync_menu "$CONTENT_DIR/menu.json"
sync_menu "$CONTENT_DIR/footer-menu.json"

# ---- 7. verify --------------------------------------------------------------
log "Checking the public home page"
page="$WORK/home.html"
code="$("${CURL[@]}" -o "$page" -w '%{http_code}' "$BASE/")" || die "cannot fetch $BASE/"
[ "$code" = "200" ] || die "GET / returned HTTP $code"
for marker in 'Your binaries. Your servers. One control panel.' 'id="install"' 'id="how"' \
              'id="features"' 'id="roadmap"'; do
  grep -qF "$marker" "$page" || die "home page is missing expected content: $marker"
done
log "Done. Landing site is live at $BASE/ (theme $THEME_NAME v$PKG_VERSION, row $THEME_ID)"

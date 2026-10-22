// Renders a 1200x630 cover for every content/posts/<slug>.md into
// content/posts/covers/<slug>.png, in the site's fonts and colours.
//
//   PLAYWRIGHT_CORE=/path/to/node_modules/playwright-core \
//   CHROME=/path/to/chrome node tools/covers.mjs [slug ...]
import { createRequire } from 'module';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_CORE || 'playwright-core');
const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const posts = path.join(root, 'content/posts');
const b64 = f => fs.readFileSync(path.join(root, f)).toString('base64');
const sora = b64('theme/assets/fonts/sora-latin.woff2');
const inter = b64('theme/assets/fonts/inter-latin.woff2');
const logo = b64('content/media/setu-icon-512.png');

// Category -> accent; everything else stays in the brand indigo.
const accents = { Guides: '#6366f1', Engineering: '#22d3ee', Operations: '#34d399', Ecosystem: '#f59e0b', News: '#f472b6' };

const front = file => {
  const m = fs.readFileSync(file, 'utf8').match(/^---\n([\s\S]*?)\n---/);
  return Object.fromEntries(m[1].split('\n').filter(l => l.includes(':')).map(l => {
    const i = l.indexOf(':');
    return [l.slice(0, i).trim(), l.slice(i + 1).trim().replace(/^"|"$/g, '')];
  }));
};
const esc = s => s.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);

const page = (f, n) => `<!doctype html><html><head><style>
@font-face{font-family:Sora;src:url(data:font/woff2;base64,${sora}) format('woff2');font-weight:100 900}
@font-face{font-family:Inter;src:url(data:font/woff2;base64,${inter}) format('woff2');font-weight:100 900}
*{margin:0;box-sizing:border-box}
body{width:1200px;height:630px;overflow:hidden;background:#0b1020;color:#f4f4f5;font-family:Inter,sans-serif;position:relative}
.glow{position:absolute;inset:0;background:
  radial-gradient(700px 420px at 100% 0%, ${f.accent}55, transparent 70%),
  radial-gradient(600px 400px at 0% 100%, #4f46e540, transparent 70%)}
.grid{position:absolute;inset:0;background-image:linear-gradient(#ffffff0d 1px,transparent 1px),linear-gradient(90deg,#ffffff0d 1px,transparent 1px);background-size:48px 48px;
  mask-image:linear-gradient(120deg,transparent 30%,#000 100%)}
svg.arc{position:absolute;right:-40px;bottom:96px;opacity:.55}
.wrap{position:absolute;inset:0;padding:64px 72px;display:flex;flex-direction:column}
.kicker{align-self:flex-start;font:600 22px Inter;letter-spacing:.06em;text-transform:uppercase;color:${f.accent};
  border:1.5px solid ${f.accent}88;background:${f.accent}1a;padding:8px 18px;border-radius:999px}
h1{font-family:Sora;font-weight:700;font-size:${f.title.length > 48 ? 60 : 68}px;line-height:1.12;letter-spacing:-.02em;margin-top:40px;max-width:900px}
.foot{margin-top:auto;display:flex;align-items:center;gap:16px;font:600 24px Sora;color:#e4e4e7}
.foot img{width:44px;height:44px;border-radius:10px}
.foot span{margin-left:auto;font:500 20px Inter;color:#9ca4b4}
</style></head><body><div class="glow"></div><div class="grid"></div>
<svg class="arc" width="560" height="260" viewBox="0 0 560 260" fill="none" stroke="${f.accent}" stroke-width="3">
  <path d="M10 250 Q280 -40 550 250"/><path d="M10 250 H550"/>
  ${Array.from({ length: 11 }, (_, i) => { const x = 10 + i * 54; const y = 250 - (4 * 290 * ((x - 10) / 540) * (1 - (x - 10) / 540)) * 0.5 * 1.0; return `<path d="M${x} 250 V${y.toFixed(1)}" stroke-opacity=".6"/>`; }).join('')}
</svg>
<div class="wrap"><div class="kicker">${esc(f.cover_kicker || f.category)}</div><h1>${esc(f.title)}</h1>
<div class="foot"><img src="data:image/png;base64,${logo}">Setu<span>setucp.com/blog · ${String(n).padStart(2, '0')}</span></div></div></body></html>`;

const schedule = JSON.parse(fs.readFileSync(path.join(posts, 'schedule.json'), 'utf8'));
const wanted = process.argv.slice(2);
const browser = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});
const tab = await browser.newPage({ viewport: { width: 1200, height: 630 } });
fs.mkdirSync(path.join(posts, 'covers'), { recursive: true });
for (const s of schedule) {
  const file = path.join(posts, `${s.slug}.md`);
  if (!fs.existsSync(file) || (wanted.length && !wanted.includes(s.slug))) continue;
  const f = front(file);
  f.accent = accents[f.category] || '#6366f1';
  await tab.setContent(page(f, s.n), { waitUntil: 'load' });
  await tab.evaluate(() => document.fonts.ready);
  await tab.screenshot({ path: path.join(posts, 'covers', `${s.slug}.png`) });
  console.log('cover', s.slug);
}
await browser.close();

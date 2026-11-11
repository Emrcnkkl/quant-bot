// Ortak yardımcılar ve site çerçevesi (menü, altbilgi, belirme efekti) — tüm sayfalar
// Sitenin adı yalnızca burada (ve sayfa <title> etiketlerinde) geçer.
const SITE = {name: ["piyasa", "m"], tg: "https://t.me/+T8qnrNlgQIwzNTJk"};
// 4. alan: "alt" → masaüstü üst menüde gösterilmez (alt bilgide ve mobil menüde görünür); "vurgu" → çerçeveli, öne çıkan sekme
const NAV = [["index.html", "Ana sayfa", "home"], ["piyasalar.html", "Piyasalar", "piyasalar"], ["ekonomi.html", "Ekonomi", "ekonomi"],
             ["haberler.html", "Haberler", "haberler"], ["halkaarz.html", "Halka arz", "halkaarz"], ["takvim.html", "Takvim", "takvim"],
             ["sinyal.html", "BIST50 Sinyal", "sinyal", "vurgu"], ["sozluk.html", "Sözlük", "sozluk"], ["iletisim.html", "İletişim", "iletisim"]];
const $ = s => document.querySelector(s);
const fmt = (x, d = 2) => x == null ? "–" : Number(x).toLocaleString("tr-TR", {minimumFractionDigits: d, maximumFractionDigits: d});
const pct = (x, d = 1) => x == null ? "–" : `<span class="${x > 0 ? "pos" : x < 0 ? "neg" : ""}">${x > 0 ? "+" : ""}${fmt(x, d)}%</span>`;
const tl = v => fmt(v, 0) + " ₺";
const COMP = {ema200: "200 günlük ort.", ema_cross: "20/50 günlük ort.", adx: "Trend gücü", rsi: "RSI", macd: "MACD", volume: "Hacim", breakout: "Kırılım", relative: "Endekse göre"};
const STATE = {"POZİSYONDA": "modelde", "GİRİŞ": "yarın alınacak", "ÇIKIŞ": "yarın satılacak", "BEKLE": ""};
const MONTHS = ["Ocak","Şubat","Mart","Nisan","Mayıs","Haziran","Temmuz","Ağustos","Eylül","Ekim","Kasım","Aralık"];
const monthName = ym => { const [y, m] = ym.split("-"); return `${MONTHS[+m - 1]} ${y}`; };
const trDate = iso => new Date(iso + "T00:00:00").toLocaleDateString("tr-TR", {day: "numeric", month: "long", year: "numeric"});
const START = 100000;
// Bot hafta içi 18:40'ta (TR) çalışır: bir sonraki güncellemenin zamanı (resmi tatiller hesaba katılmaz)
function nextUpdate() {
  const trNow = new Date(Date.now() + 3 * 3600e3), d = new Date(trNow);   // UTC alanlarında TR saati
  d.setUTCHours(18, 40, 0, 0);
  if (trNow >= d) d.setUTCDate(d.getUTCDate() + 1);
  while (d.getUTCDay() === 0 || d.getUTCDay() === 6) d.setUTCDate(d.getUTCDate() + 1);
  const days = Math.round((Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()) - Date.UTC(trNow.getUTCFullYear(), trNow.getUTCMonth(), trNow.getUTCDate())) / 864e5);
  const day = days === 0 ? "bugün" : days === 1 ? "yarın" : d.toLocaleDateString("tr-TR", {weekday: "long", timeZone: "UTC"});
  return `${day} 18:40`;
}
// Hisse simgesi: koda göre sabit bir renk tonu
const hue = t => [...t].reduce((a, c) => (a * 31 + c.charCodeAt(0)) % 360, 7);
const who = (t, name, extra = "") => `<div class="who">${extra}<span class="av" style="--h:${hue(t)}">${t.slice(0, 2)}</span><div><span class="tk">${t}</span><span class="nm">${name}</span></div></div>`;
// Sayaç animasyonu
function countUp(el, to, fmtFn, ms = 1100) {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) { el.textContent = fmtFn(to); return; }
  const t0 = performance.now(), ease = x => 1 - Math.pow(1 - x, 3);
  const step = now => { const k = Math.min(1, (now - t0) / ms); el.textContent = fmtFn(to * ease(k)); if (k < 1) requestAnimationFrame(step); };
  requestAnimationFrame(step);
}

function chrome(active) {
  const brand = `<span class="wm">${SITE.name[0]}<span class="gtext">${SITE.name[1]}</span></span>`;
  const link = ([h, t, k, f]) => `<a href="${h}" class="${[k === active ? "on" : "", f === "vurgu" ? "hl" : ""].join(" ").trim()}"${k === active ? ' aria-current="page"' : ""}>${t}</a>`;
  const top = NAV.filter(x => x[3] !== "alt" || x[2] === active).map(link).join(""), links = NAV.map(link).join("");
  $("#top").innerHTML = `<div class="wrap">
    <a class="brand" href="index.html"><span class="mark"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 3 2 8l10 5 10-5-10-5Z" fill="#3b82f6"/><path d="m2 12 10 5 10-5" stroke="#3b82f6" stroke-width="2" stroke-linejoin="round" opacity=".7"/><path d="m2 16 10 5 10-5" stroke="#10b981" stroke-width="2" stroke-linejoin="round"/></svg></span>${brand}</a>
    <div class="links">${top}</div>
    <span class="live" title="Piyasa verisi gün içinde yarım saatte bir, sinyaller her iş günü 18:40'ta güncellenir"><span class="dot"></span><span class="t" id="livetxt">GÜNCEL</span></span>
    <button class="help th" id="themebtn" type="button" title="Koyu / açık tema" aria-label="Koyu ya da açık temaya geç"></button>
    <a class="help" href="sinyal.html#sss" title="Sık sorulan sorular">?</a>
  </div>
  <div class="mnav">${links}</div>`;
  $("#top .mnav a.on")?.scrollIntoView({block: "nearest", inline: "center"});
  themeIcon(); $("#themebtn").onclick = () => {
    const next = isDark() ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("tema", next); } catch (e) { /* gizli sekme vb. */ }
    themeIcon(); window.dispatchEvent(new Event("resize"));   // grafikler yeni renklerle yeniden çizilsin
  };
  const f = $("#foot");
  if (f) f.innerHTML = `<div class="fb"><span class="brand" style="font-size:16px;margin:0">${brand}</span></div>
    <p class="small">${NAV.map(([h, t]) => `<a href="${h}">${t}</a>`).join(" · ")} · <a href="${SITE.tg}" target="_blank" rel="noopener">Telegram kanalı</a></p>
    <p id="disc">Bu sitedeki bilgiler yatırım tavsiyesi değildir. Veriler gecikmeli olabilir; kararlarınızı resmî kaynaklardan doğrulayın.</p>
    <p id="meta"></p>`;
}
// Kaydırınca beliren öğeler
function reveal(sel = "main section > *, footer > *") {
  const rio = new IntersectionObserver(es => es.forEach(en => { if (en.isIntersecting) { en.target.classList.add("in"); rio.unobserve(en.target); } }), {rootMargin: "0px 0px -8% 0px"});
  document.querySelectorAll(sel).forEach(el => { el.classList.add("rv"); rio.observe(el); });
}

// ---------------- Piyasa verisi yardımcıları (ana sayfa ve Piyasalar) ----------------
const MK_EPOCH = Date.UTC(2000, 0, 1);
const dayToDate = n => new Date(MK_EPOCH + n * 864e5);
function mkVal(it, v = it.last) {
  if (v == null) return "–";
  const s = fmt(v, it.dec);
  return it.unit === "₺" ? s + " ₺" : it.unit === "$" ? "$" + s : it.unit === "%" ? "%" + s : s;
}
const mkChg = (it, v) => v == null ? "–" : it.kind === "bp"
  ? `<span class="${v > 0 ? "pos" : v < 0 ? "neg" : ""}">${v > 0 ? "+" : ""}${fmt(v, 2)} puan</span>` : pct(v, 2);
function sparkSvg(vals, w = 300, h = 46) {
  const v = vals.filter(x => x != null); if (v.length < 2) return "";
  const lo = Math.min(...v), hi = Math.max(...v), up = v[v.length - 1] >= v[0], col = up ? "var(--al)" : "var(--sat)";
  const pts = v.map((x, i) => `${(i / (v.length - 1) * w).toFixed(1)},${(h - 3 - (x - lo) / ((hi - lo) || 1) * (h - 6)).toFixed(1)}`);
  return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true"><path d="M0,${h} L${pts.join(" L")} L${w},${h}Z" fill="${col}" opacity=".10"/><path d="M${pts.join(" L")}" fill="none" stroke="${col}" stroke-width="1.6" vector-effect="non-scaling-stroke"/></svg>`;
}
// Etkileşimli alan grafiği: üzerine gelince tarih ve değer
function areaChart(box, days, vals, it) {
  const W = Math.max(300, box.clientWidth), H = W < 560 ? 220 : 300, L = 8, R = 64, T = 10, Bm = 24;
  const lo = Math.min(...vals), hi = Math.max(...vals), pad = (hi - lo) * .06 || 1;
  const x = i => L + i / (vals.length - 1) * (W - L - R), y = v => T + (1 - (v - lo + pad) / (hi - lo + 2 * pad)) * (H - T - Bm);
  const up = vals[vals.length - 1] >= vals[0], col = up ? "var(--al)" : "var(--sat)";
  const pts = vals.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" L");
  const ticks = [lo, (lo + hi) / 2, hi].map(v => `<text x="${W - R + 8}" y="${y(v) + 4}" font-size="11" fill="var(--muted)">${fmt(v, it.dec)}</text><line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line)"/>`).join("");
  const span = days[days.length - 1] - days[0], step = Math.max(1, Math.floor(vals.length / 5));
  const xl = days.map((d, i) => i % step ? "" : `<text x="${x(i)}" y="${H - 6}" font-size="11" fill="var(--muted)" text-anchor="middle">${dayToDate(d).toLocaleDateString("tr-TR", span > 800 ? {year: "numeric"} : {month: "short", year: "2-digit"})}</text>`).join("");
  box.innerHTML = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${ticks}${xl}
    <path d="M${x(0)},${H - Bm} L${pts} L${x(vals.length - 1)},${H - Bm}Z" fill="${col}" opacity=".10"/>
    <path d="M${pts}" fill="none" stroke="${col}" stroke-width="2"/>
    <line id="hx" y1="${T}" y2="${H - Bm}" stroke="var(--line2)" visibility="hidden"/><circle id="hc" r="4" fill="${col}" visibility="hidden"/></svg><div class="tip" id="htip"></div>`;
  const svg = box.querySelector("svg"), tip = box.querySelector(".tip");
  svg.onmousemove = svg.ontouchmove = ev => {
    const p = ev.touches ? ev.touches[0] : ev, r = svg.getBoundingClientRect();
    const i = Math.max(0, Math.min(vals.length - 1, Math.round((p.clientX - r.left - L) / (W - L - R) * (vals.length - 1))));
    svg.querySelector("#hx").setAttribute("x1", x(i)); svg.querySelector("#hx").setAttribute("x2", x(i)); svg.querySelector("#hx").setAttribute("visibility", "visible");
    svg.querySelector("#hc").setAttribute("cx", x(i)); svg.querySelector("#hc").setAttribute("cy", y(vals[i])); svg.querySelector("#hc").setAttribute("visibility", "visible");
    tip.style.display = "block"; tip.style.left = x(i) + "px"; tip.style.top = y(vals[i]) + "px";
    tip.innerHTML = `${dayToDate(days[i]).toLocaleDateString("tr-TR", {day: "numeric", month: "short", year: "numeric"})} · <b>${mkVal(it, vals[i])}</b>`;
  };
  svg.onmouseleave = () => { tip.style.display = "none"; svg.querySelector("#hx").setAttribute("visibility", "hidden"); svg.querySelector("#hc").setAttribute("visibility", "hidden"); };
}
const loadJSON = f => fetch(f + "?v=" + Date.now()).then(r => r.ok ? r.json() : null).catch(() => null);
const mkFind = (M, sym) => M?.groups.flatMap(g => g.items).find(i => i.sym === sym);

// Göreli zaman: "12 dk önce", "3 saat önce", "dün 14:20"
function ago(iso) {
  const t = new Date(iso), m = Math.round((Date.now() - t) / 6e4);
  if (m < 1) return "şimdi"; if (m < 60) return `${m} dk önce`; if (m < 360) return `${Math.round(m / 60)} saat önce`;
  const opt = {hour: "2-digit", minute: "2-digit", timeZone: "Europe/Istanbul"};
  const d0 = new Date().toLocaleDateString("tr-TR", {timeZone: "Europe/Istanbul"}), d1 = t.toLocaleDateString("tr-TR", {timeZone: "Europe/Istanbul"});
  return (d0 === d1 ? "bugün " : new Date(Date.now() - 864e5).toLocaleDateString("tr-TR", {timeZone: "Europe/Istanbul"}) === d1 ? "dün " : t.toLocaleDateString("tr-TR", {day: "numeric", month: "short", timeZone: "Europe/Istanbul"}) + " ") + t.toLocaleTimeString("tr-TR", opt);
}
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));

// Çok çizgili grafik (aylık seriler): series = [{name, color, vals, dash}], x = ["2005-01", ...]
function lineChart(box, x, series, o = {}) {
  const W = Math.max(300, box.clientWidth), H = o.h || (W < 560 ? 230 : 300), L = 8, R = 56, T = 12, Bm = 24;
  const all = series.flatMap(s => s.vals).filter(v => v != null && (!o.log || v > 0));
  let lo = Math.min(...all, o.zero ? 0 : Infinity), hi = Math.max(...all);
  const tr = v => o.log ? Math.log(v) : v; lo = tr(lo); hi = tr(hi); const pad = (hi - lo) * .05 || 1;
  const X = i => L + i / (x.length - 1) * (W - L - R), Y = v => T + (1 - (tr(v) - lo + pad) / (hi - lo + 2 * pad)) * (H - T - Bm);
  const ticks = (o.log ? [Math.exp(lo), Math.exp((lo + hi) / 2), Math.exp(hi)] : [lo, (lo + hi) / 2, hi]).map(v =>
    `<line x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--line)"/><text x="${W - R + 6}" y="${Y(v) + 4}" font-size="11" fill="var(--muted)">${o.fmt ? o.fmt(v) : fmt(v, 0)}</text>`).join("");
  const zero = !o.log && lo < 0 && hi > 0 ? `<line x1="${L}" x2="${W - R}" y1="${Y(0)}" y2="${Y(0)}" stroke="var(--line2)" stroke-dasharray="3 3"/>` : "";
  const step = Math.ceil(x.length / (W < 560 ? 5 : 9));
  const xl = x.map((m, i) => i % step ? "" : `<text x="${X(i)}" y="${H - 6}" font-size="11" fill="var(--muted)" text-anchor="middle">${m.slice(0, 4)}</text>`).join("");
  const paths = series.map(s => { let d = "", pen = false;
    s.vals.forEach((v, i) => { if (v == null || (o.log && v <= 0)) { pen = false; return; } d += `${pen ? "L" : "M"}${X(i).toFixed(1)},${Y(v).toFixed(1)}`; pen = true; });
    return `<path d="${d}" fill="none" stroke="${s.color}" stroke-width="${s.w || 2}" ${s.dash ? `stroke-dasharray="${s.dash}"` : ""} stroke-linejoin="round"/>`; }).join("");
  box.style.position = "relative";
  box.innerHTML = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${ticks}${zero}${xl}${paths}<line class="hx" y1="${T}" y2="${H - Bm}" stroke="var(--line2)" visibility="hidden"/></svg><div class="tip"></div>`;
  const svg = box.querySelector("svg"), tip = box.querySelector(".tip"), hx = svg.querySelector(".hx");
  svg.onmousemove = svg.ontouchmove = ev => {
    const p = ev.touches ? ev.touches[0] : ev, r = svg.getBoundingClientRect();
    const i = Math.max(0, Math.min(x.length - 1, Math.round((p.clientX - r.left - L) / (W - L - R) * (x.length - 1))));
    hx.setAttribute("x1", X(i)); hx.setAttribute("x2", X(i)); hx.setAttribute("visibility", "visible");
    tip.style.display = "block"; tip.style.left = Math.min(Math.max(X(i), 90), W - 90) + "px"; tip.style.top = (T + 30) + "px";
    tip.innerHTML = `<b>${monthName(x[i])}</b><br>` + series.map(s => `<span style="color:${s.color}">●</span> ${s.name}: <b>${s.vals[i] == null ? "–" : (o.fmt ? o.fmt(s.vals[i]) : fmt(s.vals[i], 1))}</b>`).join("<br>");
  };
  svg.onmouseleave = () => { tip.style.display = "none"; hx.setAttribute("visibility", "hidden"); };
}
const legend = series => `<div class="lgd">${series.map(s => `<span><i style="background:${s.color}"></i>${s.name}</span>`).join("")}</div>`;

// Tema: html[data-theme] (elle seçim, localStorage "tema") yoksa cihaz tercihi
const isDark = () => (document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark")) === "dark";
function themeIcon() {
  const b = $("#themebtn"); if (!b) return;
  b.innerHTML = isDark()
    ? '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>'
    : '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"/></svg>';
  b.title = isDark() ? "Açık temaya geç" : "Koyu temaya geç";
}

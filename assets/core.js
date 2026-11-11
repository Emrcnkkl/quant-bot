// Ortak yardımcılar ve site çerçevesi (menü, altbilgi, belirme efekti) — tüm sayfalar
// Sitenin adı yalnızca burada (ve sayfa <title> etiketlerinde) geçer.
const SITE = {name: ["Piyasa", "Pusulası"], tg: "https://t.me/+T8qnrNlgQIwzNTJk"};
const NAV = [["index.html", "Ana sayfa", "home"], ["piyasalar.html", "Piyasalar", "piyasalar"], ["takvim.html", "Takvim", "takvim"],
             ["sinyal.html", "Sinyal botu", "sinyal"], ["sozluk.html", "Sözlük", "sozluk"], ["iletisim.html", "İletişim", "iletisim"]];
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
  const brand = `<span>${SITE.name[0]} <span class="gtext">${SITE.name[1]}</span></span>`;
  const links = NAV.map(([h, t, k]) => `<a href="${h}"${k === active ? ' class="on" aria-current="page"' : ""}>${t}</a>`).join("");
  $("#top").innerHTML = `<div class="wrap">
    <a class="brand" href="index.html"><span class="mark"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 3 2 8l10 5 10-5-10-5Z" fill="#3b82f6"/><path d="m2 12 10 5 10-5" stroke="#3b82f6" stroke-width="2" stroke-linejoin="round" opacity=".7"/><path d="m2 16 10 5 10-5" stroke="#10b981" stroke-width="2" stroke-linejoin="round"/></svg></span>${brand}</a>
    <div class="links">${links}</div>
    <span class="live" title="Piyasa verisi gün içinde yarım saatte bir, sinyaller her iş günü 18:40'ta güncellenir"><span class="dot"></span><span class="t" id="livetxt">GÜNCEL</span></span>
    <a class="help tg" href="${SITE.tg}" target="_blank" rel="noopener" title="Telegram kanalı: AL/SAT bildirimleri"><svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M21.4 3.6 2.9 10.8c-1.2.5-1.2 1.3-.2 1.6l4.7 1.5 1.8 5.6c.2.6.4.8.9.8.4 0 .6-.2.9-.4l2.3-2.2 4.7 3.5c.9.5 1.5.2 1.7-.8L22.8 5c.3-1.3-.5-1.9-1.4-1.4ZM8.6 13.6l9.6-6.1c.5-.3.9-.1.5.2l-8 7.3-.3 3.3-1.8-4.7Z"/></svg></a>
    <a class="help" href="sinyal.html#sss" title="Sık sorulan sorular">?</a>
  </div>
  <div class="mnav">${links}</div>`;
  $("#top .mnav a.on")?.scrollIntoView({block: "nearest", inline: "center"});
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

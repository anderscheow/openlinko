(() => {
  const doc = document.documentElement;
  doc.classList.remove("no-js");
  if (window.top !== window.self) { try { window.top.location = window.location.href; } catch (e) { document.body.hidden = true; } }
  let L = {};
  try { L = JSON.parse(document.getElementById("ol-cfg").textContent); } catch (e) {}
  const still = matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---- a sample 73-byte status frame, laid out like the real one (docs/api-map.md) ---- */
  const B = new Array(73).fill(0);
  const fill = [0x5a,0x01,0x00,0x00,0x00,0x00,0x02,0x10,0x00,0x00,0x31,0x07];
  fill.forEach((v, i) => (B[i] = v));
  B[12] = 0x05; B[13] = 0x68;              // 12 V: 1384 x 0.01 = 13.84 V
  B[14] = 0x00; B[15] = 0x00;              // speed 0
  B[16] = 0x03; B[17] = 0x1c;
  B[18] = 0x00; B[19] = 0x30; B[20] = 0xc0; // odometer 12480 km
  B[22] = 0x01; B[24] = 0xac;              // A/C set point (J5: (0xAC & 0x7F) / 2 = 22 C)
  B[25] = 0x0e; B[26] = 0x00; B[27] = 0x64;
  B[28] = 0x48;                             // battery 72 %
  B[29] = 0x01; B[30] = 0x3e;              // range 318 km
  for (let i = 44; i <= 51; i++) B[i] = 0xff; // tyre block: FF on indirect TPMS
  B[54] = 0x00; B[55] = 0x81;              // 12.9 kWh/100 km
  B[60] = 0x7f; B[61] = 0xfe; B[66] = 0x00; B[67] = 0x02;
  B[68] = 0x01; B[69] = 0xcc; B[70] = 0x01; B[71] = 0x3e; B[72] = 0x3c;

  const F = [
    { b: [28], v: "72", u: "%", key: "battery", rule: "byte 28 · u8" },
    { b: [29, 30], v: "318", u: "km", key: "range", rule: "bytes 29–30 · u16 BE" },
    { b: [12, 13], v: "13.84", u: "V", key: "volt", rule: "bytes 12–13 · u16 × 0.01" },
    { b: [18, 19, 20], v: "12,480", u: "km", key: "odo", rule: "bytes 18–20 · u24 BE" },
    { b: [54, 55], v: "12.9", u: "kWh/100", key: "cons", rule: "bytes 54–55 · × 0.1" },
    { b: [3], v: L.locked || "Locked", u: "", key: "lock", rule: "byte 3 · 0 = locked" },
    { b: [44, 45, 46, 47, 48, 49, 50, 51], v: "FF", u: "", key: "tyres", rule: "bytes 44–51 · FF = no sensor" },
  ];

  const hex = document.querySelector(".hex");
  if (hex) {
    const cells = [];
    const owner = {};
    F.forEach((f, i) => f.b.forEach(b => (owner[b] = i)));
    for (let i = 0; i < 73; i++) {
      if (i % 8 === 0) {
        const o = document.createElement("span");
        o.className = "off";
        o.textContent = i.toString(16).padStart(2, "0");
        o.setAttribute("aria-hidden", "true");
        hex.appendChild(o);
      }
      const c = document.createElement("b");
      c.textContent = B[i].toString(16).padStart(2, "0").toUpperCase();
      if (owner[i] !== undefined) {
        c.className = "f";
        c.tabIndex = 0;
        c.setAttribute("role", "button");
        c.setAttribute("aria-label", (L.names || {})[F[owner[i]].key] || F[owner[i]].key);
      } else c.setAttribute("aria-hidden", "true");
      cells.push(c);
      hex.appendChild(c);
    }
    const kEl = document.querySelector(".read .k");
    const rEl = document.querySelector(".read .rule");
    const vEl = document.querySelector(".read .v");
    let cur = 0, timer = null, paused = false;
    const show = i => {
      cur = i;
      cells.forEach(c => c.classList.remove("on"));
      F[i].b.forEach(b => cells[b].classList.add("on"));
      kEl.textContent = (L.names || {})[F[i].key] || F[i].key;
      rEl.textContent = F[i].rule;
      vEl.innerHTML = F[i].v + (F[i].u ? "<small>" + F[i].u + "</small>" : "");
    };
    const tick = () => { if (!paused && !document.hidden) show((cur + 1) % F.length); };
    show(0);
    if (!still) timer = setInterval(tick, 2600);
    const pick = e => {
      const i = cells.indexOf(e.target);
      if (i < 0 || owner[i] === undefined) return;
      paused = true;
      show(owner[i]);
    };
    hex.addEventListener("click", pick);
    hex.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(e); } });
    hex.addEventListener("mouseover", e => { if (owner[cells.indexOf(e.target)] !== undefined) { paused = true; show(owner[cells.indexOf(e.target)]); } });
    hex.addEventListener("mouseleave", () => { paused = false; });
  }

  /* ---- install tabs ---- */
  const tabs = [...document.querySelectorAll(".tabs button")];
  const sel = t => {
    tabs.forEach(b => {
      const on = b === t;
      b.setAttribute("aria-selected", on);
      b.tabIndex = on ? 0 : -1;
      document.getElementById(b.getAttribute("aria-controls")).hidden = !on;
    });
  };
  tabs.forEach((b, i) => {
    b.addEventListener("click", () => sel(b));
    b.addEventListener("keydown", e => {
      const d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
      if (d) { e.preventDefault(); const n = tabs[(i + d + tabs.length) % tabs.length]; sel(n); n.focus(); }
    });
  });
  if (/Android/i.test(navigator.userAgent)) { const a = tabs.find(t => t.dataset.os === "android"); if (a) sel(a); }

  document.querySelectorAll(".copy").forEach(btn => {
    btn.addEventListener("click", async () => {
      const pre = btn.closest(".term").querySelector("pre");
      const text = [...pre.querySelectorAll(".cmd")].map(s => s.textContent).join("\n");
      try { await navigator.clipboard.writeText(text); btn.textContent = L.copied || "Copied"; }
      catch { btn.textContent = "Ctrl+C"; }
      setTimeout(() => (btn.textContent = L.copy || "Copy"), 1800);
    });
  });

  /* ---- reveal ---- */
  if (!still && "IntersectionObserver" in window) {
    const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }), { rootMargin: "0px 0px -8% 0px" });
    document.querySelectorAll(".rv").forEach(el => io.observe(el));
  } else document.querySelectorAll(".rv").forEach(el => el.classList.add("in"));
})();

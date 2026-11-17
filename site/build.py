"""Build the OpenLinko landing page in English and Indonesian from one template.

    python site/build.py      ->  site/openlinko/index.html and site/openlinko/id/index.html
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "openlinko"
BASE = "https://jaylabb.my.id/openlinko/"
GH = "https://github.com/GodrezJr2/openlinko"
ADD = GH + "/issues/new?template=add-car.yml"

SHOTS = ["home", "energy", "dist", "chg", "doors", "plan"]

EN = dict(
    lang="en", root="", url=BASE, other_url=BASE + "id/", other_lang="id", other_name="Bahasa Indonesia",
    readme=GH + "#setup",
    title="OpenLinko: CarLinko dashboard for Jaecoo, Omoda and Chery cars",
    desc="A free, open-source dashboard for cars on the CarLinko app: Jaecoo J5 EV, Omoda E5, Chery Tiggo 7 and 8 PHEV. "
         "Trips, energy use, charging cost, tyres and remote control, self-hosted on your PC or an old Android phone.",
    og_title="OpenLinko: your CarLinko car, fully decoded",
    og_desc="Trips, charging cost, energy use, tyres and remote control for Jaecoo, Omoda and Chery. Self-hosted and open source.",
    skip="Skip to content", nav_how="How it works", nav_cars="Cars", nav_install="Install", nav_faq="FAQ",
    over="Open source · for CarLinko cars",
    h1="Your CarLinko car, <em>fully decoded.</em>",
    lede="A free dashboard for <b>Jaecoo, Omoda and Chery</b>. It reads your own CarLinko account and keeps everything the app "
         "throws away: trips, real energy use, charging cost, tyres and remote control.",
    cta1="Get it on GitHub", cta2="Install in 2 minutes",
    note="Free, MIT license. Runs on your PC or an old Android phone. Not affiliated with Chery Group or CarLinko.",
    dump_l="Status frame · 73 bytes", dump_r="Decoded",
    dump_foot="Sample frame. Offsets are the real ones, mapped on four cars.",
    names=dict(battery="Battery", range="Range", volt="12 V battery", odo="Odometer", cons="Energy use",
               lock="Doors", tyres="Tyres (indirect TPMS)"),
    locked="Locked", copy="Copy", copied="Copied",
    tag_batt="BATTERY", tag_range="RANGE", tag_12v="12 V", tag_lock="DOORS", tag_lock_v="Locked",
    s1_over="What you get", s1_h="Everything the app forgets, kept.",
    s1_sub="The CarLinko app shows your car right now and little else. OpenLinko logs every update the car sends, "
           "so the numbers add up over days and months.",
    shots=[("Home", "Range, battery, climate, doors"), ("Energy", "kWh/100 km per day, net of regen"),
           ("Calendar", "Distance and cost for every day"), ("Charging", "Each session with kWh and cost"),
           ("Doors", "3D car with remote controls"), ("Charge plan", "Time and cost to a target %")],
    alts=["Home screen: 318 km range, 72% battery, quick actions", "Energy: kWh per 100 km for each day against the WLTP rating",
          "Distance calendar with km, energy and cost per day", "Charging: last session power curve, kWh and cost",
          "Doors and windows on a 3D car with remote controls", "Charge calculator: time, kWh and cost to a target percentage"],
    s2_over="Features", s2_h="Built on a real car, checked against real receipts.",
    feats=[("Real energy use", "kWh/100 km per day, net of regen, beside the head unit's own figure and the WLTP rating."),
           ("Charging cost that matches the receipt", "Every session with kWh, power curve and cost. On the reference car it matches the charger receipts to 99.6 to 99.9%."),
           ("Trips and a driving calendar", "Distance, energy and cost for each day, with trips found from the odometer."),
           ("Remote control", "Lock, A/C with temperature, windows, tailgate and find car, sent the way the official app sends them. Cloud only, no Bluetooth."),
           ("Tyres, 12 V and battery health", "Tyre pressures on cars with direct TPMS, the 12 V voltage, and charge habits for LFP packs."),
           ("Head unit add-on", "Climate Gesture for the J5: change fan and temperature with a two finger swipe on the car's own screen.")],
    s3_over="Supported cars", s3_h="Four cars, three brands, four countries.",
    s3_sub="The byte layout held identical on every car owners tried, so it looks like a CarLinko platform layout, not a per model one.",
    cars=[("Jaecoo J5 EV", "Electric", "Indonesia", "Reference car"), ("Omoda E5", "Electric", "Uruguay", "Confirmed"),
          ("Chery Tiggo 7 PHEV", "Plug-in hybrid", "Malaysia", "Confirmed"), ("Chery Tiggo 8 PHEV", "Plug-in hybrid", "South Africa", "Confirmed")],
    more_n="Another Jaecoo, Omoda, Chery or Exeed", more_m="Any CarLinko car", more_st="Add your car →",
    carnote="Not listed? The dashboard has a <b>Report my car</b> page that copies a report with the plate, VIN and account ids removed, "
            "ready for an <a href=\"" + ADD + "\">Add my car</a> issue.",
    s4_over="Install", s4_h="Runs on something you already own.",
    s4_sub="One machine stays on and logs the car. Your phone, Android or iPhone, opens the dashboard in the browser.",
    t_win="Windows PC", t_and="Old Android phone", t_lin="Linux · Pi · VPS",
    how_win="<b>No coding.</b> Download the repo as a ZIP, unzip it, double click <code>start.bat</code>. It installs Python if needed and opens the dashboard. Sign in with your CarLinko account.",
    how_and="Install <b>Termux</b> and <b>Termux:Boot</b> from F-Droid, paste these three lines, leave the phone on the charger. It starts again after a reboot.",
    how_lin="One script sets up the services. <code>--tailscale</code> lets you open it from anywhere without exposing it to the internet.",
    win_c="# after downloading and unzipping the repo", alt="Docker and Home Assistant setups are in the <a href=\"" + GH + "#setup\">README</a>.",
    s5_over="Privacy", s5_h="Your account. Your machine. No OpenLinko cloud.",
    pts=[("Stays local", "Password, token, VIN and plate live in a local file that is never committed."),
         ("One owner per install", "It is not a hosted service and never stores anyone else's account."),
         ("Gentle on your account", "Login retries are rate limited, so a wrong password can't hammer CarLinko."),
         ("Keeps your phone app signed in", "CarLinko allows one session per account. A second account linked to your car avoids the tug of war.")],
    s6_over="FAQ", s6_h="Questions owners ask.",
    faq=[("Is there a dashboard for my Jaecoo J5 EV?", "Yes. OpenLinko was built on a Jaecoo J5 EV. It reads the same data the CarLinko app shows and keeps the history: trips, energy use net of regen, charging sessions with cost, tyres and 12 V health."),
         ("Does it work with Omoda, Chery Tiggo or Exeed?", "It is confirmed on an Omoda E5, a Chery Tiggo 7 PHEV and a Chery Tiggo 8 PHEV as well as the J5. Other Chery Group cars on the CarLinko app very likely work, since the byte layout was identical on all four."),
         ("Is it an official CarLinko app?", "No. It is an independent open source project, not affiliated with Jaecoo, Omoda, Chery or CarLinko. It talks to the same cloud the official app uses, with your own login."),
         ("Do I need a server?", "You need one thing that stays on: a Windows PC, a Raspberry Pi, a small VPS, or a spare Android phone on the charger. The phone you carry just opens it in the browser."),
         ("Does it work on iPhone?", "Yes, as the screen you look at: open it in Safari and add it to the home screen. iOS can't run the always on part, so that runs on a PC, server or spare Android phone."),
         ("Does it work with Home Assistant?", "Yes, through its REST API. Separate Home Assistant integrations for CarLinko cars are also listed in the README."),
         ("How much does it cost?", "Nothing. It is MIT licensed and runs on hardware you already have.")],
    end_big="Read your<br>own <em>car.</em>",
    foot_l="OpenLinko, formerly J5 EV Dashboard. MIT license. Built by <a href=\"https://jaylabb.my.id/\">Jayson</a>.",
    foot_tm="Jaecoo, Omoda, Chery, Exeed and CarLinko are trademarks of their owners. This project is not affiliated with them.",
)

ID = dict(
    lang="id", root="../", url=BASE + "id/", other_url=BASE, other_lang="en", other_name="English",
    readme=GH + "/blob/main/README.id.md",
    title="OpenLinko: dashboard CarLinko untuk Jaecoo, Omoda dan Chery",
    desc="Dashboard gratis dan open source untuk mobil di aplikasi CarLinko: Jaecoo J5 EV, Omoda E5, Chery Tiggo 7 dan 8 PHEV. "
         "Trip, konsumsi energi, biaya charging, ban dan kontrol jarak jauh, jalan di PC sendiri atau HP Android bekas.",
    og_title="OpenLinko: mobil CarLinko kamu, terbaca semua",
    og_desc="Trip, biaya charging, konsumsi energi, ban dan kontrol jarak jauh untuk Jaecoo, Omoda dan Chery. Self-hosted dan open source.",
    skip="Langsung ke isi", nav_how="Cara kerja", nav_cars="Mobil", nav_install="Pasang", nav_faq="FAQ",
    over="Open source · untuk mobil CarLinko",
    h1="Mobil CarLinko kamu, <em>terbaca semua.</em>",
    lede="Dashboard gratis untuk <b>Jaecoo, Omoda dan Chery</b>. Membaca akun CarLinko kamu sendiri dan menyimpan semua yang dibuang "
         "aplikasinya: trip, konsumsi energi asli, biaya charging, ban dan kontrol jarak jauh.",
    cta1="Ambil di GitHub", cta2="Pasang dalam 2 menit",
    note="Gratis, lisensi MIT. Jalan di PC atau HP Android bekas. Tidak berafiliasi dengan Chery Group atau CarLinko.",
    dump_l="Frame status · 73 byte", dump_r="Terbaca",
    dump_foot="Contoh frame. Offset-nya asli, sudah dipetakan di empat mobil.",
    names=dict(battery="Baterai", range="Jarak tempuh", volt="Aki 12 V", odo="Odometer", cons="Konsumsi energi",
               lock="Pintu", tyres="Ban (TPMS tidak langsung)"),
    locked="Terkunci", copy="Salin", copied="Tersalin",
    tag_batt="BATERAI", tag_range="JARAK", tag_12v="AKI 12 V", tag_lock="PINTU", tag_lock_v="Terkunci",
    s1_over="Yang kamu dapat", s1_h="Semua yang dilupakan aplikasinya, tersimpan.",
    s1_sub="Aplikasi CarLinko cuma menunjukkan kondisi mobil saat ini. OpenLinko mencatat setiap update yang dikirim mobil, "
           "jadi angkanya terkumpul dari hari ke hari.",
    shots=[("Beranda", "Jarak, baterai, AC, pintu"), ("Energi", "kWh/100 km per hari, bersih setelah regen"),
           ("Kalender", "Jarak dan biaya tiap hari"), ("Charging", "Tiap sesi dengan kWh dan biaya"),
           ("Pintu", "Mobil 3D dengan kontrol jarak jauh"), ("Rencana charging", "Waktu dan biaya ke persen target")],
    alts=["Layar utama: jarak 318 km, baterai 72%, tombol cepat", "Energi: kWh per 100 km tiap hari dibanding rating WLTP",
          "Kalender jarak dengan km, energi dan biaya per hari", "Charging: kurva daya sesi terakhir, kWh dan biaya",
          "Pintu dan jendela di mobil 3D dengan kontrol jarak jauh", "Kalkulator charging: waktu, kWh dan biaya ke persen target"],
    s2_over="Fitur", s2_h="Dibuat di mobil asli, dicek dengan struk asli.",
    feats=[("Konsumsi energi asli", "kWh/100 km per hari, bersih setelah regen, di samping angka head unit dan rating WLTP."),
           ("Biaya charging yang cocok dengan struk", "Tiap sesi lengkap dengan kWh, kurva daya dan biaya. Di mobil referensi cocok dengan struk PLN Mobile 99,6 sampai 99,9%."),
           ("Trip dan kalender berkendara", "Jarak, energi dan biaya tiap hari, dengan trip yang dideteksi dari odometer."),
           ("Kontrol jarak jauh", "Kunci, AC dengan suhu, jendela, bagasi dan cari mobil, dikirim seperti aplikasi resminya. Lewat cloud, tanpa Bluetooth."),
           ("Ban, aki 12 V dan baterai", "Tekanan ban di mobil dengan TPMS langsung, tegangan aki 12 V, dan kebiasaan charging untuk baterai LFP."),
           ("Add-on head unit", "Climate Gesture untuk J5: atur kipas dan suhu dengan geser dua jari di layar mobil.")],
    s3_over="Mobil yang didukung", s3_h="Empat mobil, tiga merek, empat negara.",
    s3_sub="Susunan byte-nya identik di semua mobil yang dicoba pemiliknya, jadi kelihatannya ini format platform CarLinko, bukan per model.",
    cars=[("Jaecoo J5 EV", "Listrik", "Indonesia", "Mobil referensi"), ("Omoda E5", "Listrik", "Uruguay", "Terkonfirmasi"),
          ("Chery Tiggo 7 PHEV", "Plug-in hybrid", "Malaysia", "Terkonfirmasi"), ("Chery Tiggo 8 PHEV", "Plug-in hybrid", "Afrika Selatan", "Terkonfirmasi")],
    more_n="Jaecoo, Omoda, Chery atau Exeed lain", more_m="Mobil CarLinko apa saja", more_st="Tambahkan mobilmu →",
    carnote="Belum ada di daftar? Dashboard punya halaman <b>Report my car</b> yang menyalin laporan tanpa plat, VIN dan id akun, "
            "siap untuk issue <a href=\"" + ADD + "\">Add my car</a>.",
    s4_over="Pasang", s4_h="Jalan di perangkat yang sudah kamu punya.",
    s4_sub="Satu perangkat nyala terus untuk mencatat data mobil. HP kamu, Android atau iPhone, tinggal buka dashboard di browser.",
    t_win="PC Windows", t_and="HP Android bekas", t_lin="Linux · Pi · VPS",
    how_win="<b>Tanpa coding.</b> Download repo sebagai ZIP, ekstrak, klik dua kali <code>start.bat</code>. Python dipasang otomatis kalau belum ada, lalu dashboard terbuka. Login pakai akun CarLinko.",
    how_and="Pasang <b>Termux</b> dan <b>Termux:Boot</b> dari F-Droid, tempel tiga baris ini, biarkan HP dicolok charger. Nyala lagi sendiri setelah restart.",
    how_lin="Satu skrip memasang service-nya. <code>--tailscale</code> supaya bisa dibuka dari mana saja tanpa dibuka ke internet.",
    win_c="# setelah download dan ekstrak repo", alt="Docker dan Home Assistant ada di <a href=\"" + GH + "/blob/main/README.id.md\">README</a>.",
    s5_over="Privasi", s5_h="Akunmu. Perangkatmu. Nggak ada cloud OpenLinko.",
    pts=[("Tetap lokal", "Password, token, VIN dan plat disimpan di file lokal yang nggak pernah di-commit."),
         ("Satu pemilik per instalasi", "Bukan layanan hosting dan nggak pernah menyimpan akun orang lain."),
         ("Aman buat akunmu", "Percobaan login dibatasi, jadi password salah nggak membanjiri CarLinko."),
         ("Aplikasi di HP tetap login", "CarLinko cuma izinkan satu sesi per akun. Akun kedua yang ditautkan ke mobil mencegah saling tendang.")],
    s6_over="FAQ", s6_h="Yang sering ditanya pemilik.",
    faq=[("Ada dashboard untuk Jaecoo J5 EV?", "Ada. OpenLinko dibuat di Jaecoo J5 EV. Ia membaca data yang sama dengan aplikasi CarLinko lalu menyimpan riwayatnya: trip, konsumsi energi bersih setelah regen, sesi charging beserta biayanya, ban dan aki 12 V."),
         ("Bisa untuk Omoda, Chery Tiggo atau Exeed?", "Sudah terbukti di Omoda E5, Chery Tiggo 7 PHEV dan Chery Tiggo 8 PHEV selain J5. Mobil Chery Group lain di aplikasi CarLinko kemungkinan besar jalan, karena susunan byte-nya identik di keempatnya."),
         ("Apakah ini aplikasi resmi CarLinko?", "Bukan. Ini proyek open source independen, tidak berafiliasi dengan Jaecoo, Omoda, Chery atau CarLinko. Ia bicara ke cloud yang sama dengan aplikasi resmi, pakai login kamu sendiri."),
         ("Perlu server?", "Perlu satu perangkat yang nyala terus: PC Windows, Raspberry Pi, VPS kecil, atau HP Android bekas yang dicolok charger. HP yang kamu bawa tinggal buka di browser."),
         ("Bisa di iPhone?", "Bisa, sebagai layar untuk melihat: buka di Safari lalu tambahkan ke layar utama. iOS nggak bisa menjalankan bagian yang nyala terus, jadi itu jalan di PC, server atau HP Android bekas."),
         ("Bisa disambung ke Home Assistant?", "Bisa, lewat REST API-nya. Integrasi Home Assistant terpisah untuk mobil CarLinko juga tercantum di README."),
         ("Bayar?", "Gratis. Lisensi MIT dan jalan di perangkat yang sudah kamu punya.")],
    end_big="Baca<br>mobilmu <em>sendiri.</em>",
    foot_l="OpenLinko, dulu J5 EV Dashboard. Lisensi MIT. Dibuat oleh <a href=\"https://jaylabb.my.id/\">Jayson</a>.",
    foot_tm="Jaecoo, Omoda, Chery, Exeed dan CarLinko adalah merek dagang pemiliknya. Proyek ini tidak berafiliasi dengan mereka.",
)

GH_SVG = ('<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 .5a11.5 11.5 0 0 0-3.64 22.41c.58.1.79-.25.79-.56v-2c-3.2.7-3.88-1.37-3.88-1.37-.53-1.33-1.28-1.69-1.28-1.69-1.05-.71.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.77 2.7 1.26 3.36.96.1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.68 0-1.25.45-2.28 1.18-3.08-.12-.29-.51-1.46.11-3.04 0 0 .97-.31 3.17 1.18a11 11 0 0 1 5.77 0c2.2-1.49 3.17-1.18 3.17-1.18.62 1.58.23 2.75.11 3.04.74.8 1.18 1.83 1.18 3.08 0 4.41-2.69 5.39-5.25 5.67.41.36.78 1.06.78 2.14v3.17c0 .31.21.67.8.56A11.5 11.5 0 0 0 12 .5Z"/></svg>')


def ver(name):
    """Short content hash, so the host's 10-year cache never serves a stale asset."""
    import hashlib
    return hashlib.sha1((OUT / "assets" / name).read_bytes()).hexdigest()[:8]


def safe(s):
    """Keep JSON inside a <script> block from closing it early."""
    return s.replace("</", "<\\/")


def page(t):
    r = t["root"]
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "SoftwareApplication", "name": "OpenLinko", "alternateName": ["J5 EV Dashboard", "CarLinko dashboard"],
         "applicationCategory": "UtilitiesApplication", "operatingSystem": "Windows, Linux, macOS, Android (Termux), Docker",
         "description": t["desc"], "url": t["url"], "downloadUrl": GH, "codeRepository": GH,
         "license": "https://opensource.org/licenses/MIT", "image": BASE + "img/og.jpg", "inLanguage": t["lang"],
         "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
         "author": {"@type": "Person", "name": "Jayson Christopher Lim", "url": "https://jaylabb.my.id/"}},
        {"@type": "FAQPage", "inLanguage": t["lang"], "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in t["faq"]]}]}
    js_cfg = json.dumps({"names": t["names"], "locked": t["locked"], "copy": t["copy"], "copied": t["copied"]}, ensure_ascii=False)

    shots = "\n".join(
        f'<figure class="rv"><div class="ph"><img src="{r}img/v2-{s}-light.jpg" width="585" height="1266" loading="lazy" alt="{t["alts"][i]}"></div>'
        f'<figcaption><b>{t["shots"][i][0]}</b><span>{t["shots"][i][1]}</span></figcaption></figure>'
        for i, s in enumerate(SHOTS))
    feats = "\n".join(f'<li class="rv"><h3>{h}</h3><p>{p}</p></li>' for h, p in t["feats"])
    cars = "\n".join(f'<div class="carrow rv"><span class="n">{n}</span><span class="m">{k}</span><span class="m">{c}</span><span class="st">{s}</span></div>'
                     for n, k, c, s in t["cars"])
    pts = "\n".join(f'<li><b>{h}</b><span>{p}</span></li>' for h, p in t["pts"])
    faq = "\n".join(f'<details{" open" if i == 0 else ""}><summary>{q}</summary><p>{a}</p></details>' for i, (q, a) in enumerate(t["faq"]))

    return f"""<!doctype html>
<html lang="{t['lang']}" class="no-js">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'none'; upgrade-insecure-requests">
<meta name="referrer" content="strict-origin-when-cross-origin">
<title>{t['title']}</title>
<meta name="description" content="{t['desc']}">
<link rel="canonical" href="{t['url']}">
<link rel="alternate" hreflang="en" href="{BASE}">
<link rel="alternate" hreflang="id" href="{BASE}id/">
<link rel="alternate" hreflang="x-default" href="{BASE}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="OpenLinko">
<meta property="og:locale" content="{'id_ID' if t['lang'] == 'id' else 'en_US'}">
<meta property="og:title" content="{t['og_title']}">
<meta property="og:description" content="{t['og_desc']}">
<meta property="og:url" content="{t['url']}">
<meta property="og:image" content="{BASE}img/og.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#0c0d0b">
<link rel="icon" href="{r}img/icon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..800&family=JetBrains+Mono:wght@400;500;600&display=swap">
<link rel="stylesheet" href="{r}assets/site.css?v={ver('site.css')}">
<link rel="preload" as="image" href="{r}img/j5.webp" imagesrcset="{r}img/j5-640.webp 640w, {r}img/j5.webp 1006w" imagesizes="(max-width:760px) 100vw, 980px">
<script type="application/ld+json">{safe(json.dumps(ld, ensure_ascii=False))}</script>
<script type="application/json" id="ol-cfg">{safe(js_cfg)}</script>
</head>
<body>
<a class="skip" href="#main">{t['skip']}</a>
<header class="bar"><div class="wrap">
  <a class="logo" href="./"><i aria-hidden="true"></i>OpenLinko</a>
  <nav aria-label="Site">
    <a class="opt" href="#cars">{t['nav_cars']}</a><a class="opt" href="#install">{t['nav_install']}</a><a class="opt" href="#faq">{t['nav_faq']}</a>
    <a href="{t['other_url']}" hreflang="{t['other_lang']}" lang="{t['other_lang']}">{t['other_name']}</a>
    <a class="gh" href="{GH}">GitHub</a>
  </nav>
</div></header>

<main id="main">
<div class="hero">
  <div class="wrap grid">
    <div>
      <p class="over">{t['over']}</p>
      <h1>{t['h1']}</h1>
      <p class="lede">{t['lede']}</p>
      <div class="cta">
        <a class="btn volt" href="{GH}">{GH_SVG}{t['cta1']}</a>
        <a class="btn ghost" href="#install">{t['cta2']}</a>
      </div>
      <p class="note">{t['note']}</p>
    </div>
    <div class="dump" aria-label="{t['dump_l']}">
      <div class="head"><span>{t['dump_l']}</span><span>{t['dump_r']}</span></div>
      <div class="hex"></div>
      <div class="read" aria-live="polite"><span class="k"></span><span class="rule"></span><span class="v"></span></div>
      <div class="foot">{t['dump_foot']}</div>
    </div>
  </div>
  <div class="seam">
    <div class="car"><img src="{r}img/j5.webp" srcset="{r}img/j5-640.webp 640w, {r}img/j5.webp 1006w" sizes="(max-width:760px) 100vw, 980px" width="1006" height="420" alt="Jaecoo J5 EV"></div>
    <ul class="tags" aria-hidden="true">
      <li class="t1"><span>{t['tag_batt']} · b28</span>72 %</li>
      <li class="t2"><span>{t['tag_range']} · b29–30</span>318 km</li>
      <li class="t3"><span>{t['tag_12v']} · b12–13</span>13.84 V</li>
      <li class="t4"><span>{t['tag_lock']} · b3</span>{t['tag_lock_v']}</li>
    </ul>
  </div>
</div>

<div class="light">
<section class="s first" id="how"><div class="wrap">
  <p class="over">{t['s1_over']}</p>
  <h2 class="rv">{t['s1_h']}</h2>
  <p class="sub rv">{t['s1_sub']}</p>
  <div class="rail">
{shots}
  </div>
</div></section>

<section class="s"><div class="wrap">
  <p class="over">{t['s2_over']}</p>
  <h2 class="rv">{t['s2_h']}</h2>
  <ol class="feats">
{feats}
  </ol>
</div></section>

<section class="s" id="cars"><div class="wrap">
  <p class="over">{t['s3_over']}</p>
  <h2 class="rv">{t['s3_h']}</h2>
  <p class="sub rv">{t['s3_sub']}</p>
  <div class="cars">
{cars}
    <a class="carrow more rv" href="{ADD}"><span class="n">{t['more_n']}</span><span class="m">{t['more_m']}</span><span class="m"></span><span class="st">{t['more_st']}</span></a>
  </div>
  <p class="carnote">{t['carnote']}</p>
</div></section>

<section class="s" id="install"><div class="wrap">
  <p class="over">{t['s4_over']}</p>
  <h2 class="rv">{t['s4_h']}</h2>
  <p class="sub rv">{t['s4_sub']}</p>
  <div class="tabs" role="tablist">
    <button role="tab" id="tb-win" aria-controls="p-win" aria-selected="true" data-os="win">{t['t_win']}</button>
    <button role="tab" id="tb-and" aria-controls="p-and" aria-selected="false" tabindex="-1" data-os="android">{t['t_and']}</button>
    <button role="tab" id="tb-lin" aria-controls="p-lin" aria-selected="false" tabindex="-1" data-os="linux">{t['t_lin']}</button>
  </div>
  <div class="panel" id="p-win" role="tabpanel" aria-labelledby="tb-win"><div class="term">
    <div class="tb"><i></i><span>PowerShell</span><button class="copy" type="button">{t['copy']}</button></div>
    <pre><span class="c">{t['win_c']}</span>
<span class="p">&gt;</span> <span class="cmd">.\\start.bat</span></pre>
    <p class="how">{t['how_win']} <a class="zip" href="{GH}/archive/refs/heads/main.zip">ZIP ↓</a></p>
  </div></div>
  <div class="panel" id="p-and" role="tabpanel" aria-labelledby="tb-and" hidden><div class="term">
    <div class="tb"><i></i><span>Termux</span><button class="copy" type="button">{t['copy']}</button></div>
    <pre><span class="p">$</span> <span class="cmd">pkg install -y git</span>
<span class="p">$</span> <span class="cmd">git clone https://github.com/GodrezJr2/openlinko ~/openlinko</span>
<span class="p">$</span> <span class="cmd">bash ~/openlinko/tools/termux-setup.sh</span></pre>
    <p class="how">{t['how_and']}</p>
  </div></div>
  <div class="panel" id="p-lin" role="tabpanel" aria-labelledby="tb-lin" hidden><div class="term">
    <div class="tb"><i></i><span>bash</span><button class="copy" type="button">{t['copy']}</button></div>
    <pre><span class="p">$</span> <span class="cmd">git clone https://github.com/GodrezJr2/openlinko</span>
<span class="p">$</span> <span class="cmd">cd openlinko &amp;&amp; ./tools/install.sh --tailscale</span></pre>
    <p class="how">{t['how_lin']}</p>
  </div></div>
  <p class="alt">{t['alt']}</p>
</div></section>
</div>

<section class="band"><div class="wrap">
  <p class="over">{t['s5_over']}</p>
  <h2 class="rv">{t['s5_h']}</h2>
  <ul class="pts">
{pts}
  </ul>
</div></section>

<div class="light">
<section class="s" id="faq"><div class="wrap">
  <p class="over">{t['s6_over']}</p>
  <h2 class="rv">{t['s6_h']}</h2>
  <div class="faq">
{faq}
  </div>
</div></section>
</div>
</main>

<div class="end"><div class="wrap">
  <p class="big rv" aria-hidden="true">{t['end_big']}</p>
  <div class="cta">
    <a class="btn volt" href="{GH}">{GH_SVG}{t['cta1']}</a>
    <a class="btn ghost" href="#install">{t['cta2']}</a>
  </div>
  <footer>
    <span>{t['foot_l']}</span>
    <span><a href="{GH}">GitHub</a> · <a href="{t['other_url']}" hreflang="{t['other_lang']}">{t['other_name']}</a></span>
    <p>{t['foot_tm']}</p>
  </footer>
</div></div>
<script src="{r}assets/site.js?v={ver('site.js')}" defer></script>
</body>
</html>
"""


for t, dest in ((EN, OUT / "index.html"), (ID, OUT / "id" / "index.html")):
    html = page(t)
    assert not re.search(r"\{\w+\}", re.sub(r"<script.*?</script>", "", html, flags=re.S)), "unfilled placeholder"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html, encoding="utf-8", newline="\n")
    print("wrote", dest.relative_to(HERE))

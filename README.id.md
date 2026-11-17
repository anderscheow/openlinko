# OpenLinko — dashboard self-hosted untuk mobil berbasis CarLinko

*Jaecoo · Omoda · Chery · Exeed — BEV dan PHEV. Dulu bernama **J5 EV Dashboard**: dimulai di Jaecoo J5 EV, dan pemilik lain sudah mengonfirmasi di Omoda E5, Tiggo 7 PHEV dan Tiggo 8 PHEV.*

[English](README.md) · **Bahasa Indonesia** · [Website](https://jaylabb.my.id/openlinko/id/)

PWA mobile-first untuk semua mobil yang pakai app CarLinko: baterai, jarak tempuh dan kondisi
mobil secara live, kunci / AC / jendela / bagasi dari jauh, pemakaian energi bersih setelah regen,
sesi dan biaya charge, ban, kesehatan aki 12 V, dan add-on head unit.

Ini dibikin karena app bawaan CarLinko cuma nunjukin kondisi saat ini: ga ada total perjalanan,
ga ada riwayat biaya charge, ga ada efisiensi dari waktu ke waktu. Semua di sini diturunkan dari data
yang **memang sudah** dikirim mobil ke cloud-nya; project ini cuma baca akunmu sendiri dan nyimpen
riwayatnya. Tekanan dan suhu ban muncul kalau mobilmu punya TPMS langsung; mobil dengan TPMS tidak
langsung (seperti J5 EV) memang cuma kirim status, dan dashboard bilang begitu, bukan ngarang angka.

> Dibangun dari mobil nyata, bukan dari lembar spesifikasi. Output biaya charge cocok dengan struk
> PLN Mobile pemiliknya sampai **99,6–99,9 %** (lihat [Akurasi](#akurasi)) — angka itu dari satu
> mobil, karena butuh struk asli untuk diuji. Decode telemetrinya sendiri sudah terkonfirmasi di dua.

> **Mobil CarLinko lain?** Sudah terkonfirmasi di **dua mobil, dua merek, dua jenis penggerak,
> dua negara** — Jaecoo J5 EV (BEV, Indonesia) dan Chery Tiggo 8 PHEV (Afrika Selatan). Semua
> offset byte telemetri identik di keduanya, yang menunjukkan layout blob-nya berasal dari
> platform CarLinko sendiri, bukan dari modelnya. Konstanta yang memang beda per model (skala
> ban, jenis penggerak, foto mobilnya) dibaca dari API saat setup, jadi mobil baru sebagian besar
> mengatur dirinya sendiri.
>
> Catatan yang perlu disebut terus terang: Jaecoo, Omoda, Exeed dan Chery semuanya merek
> **Chery Group**, dan CarLinko itu aplikasi Chery Group — jadi "jalan di CarLinko" realistisnya
> berarti "jalan se-Chery Group", bukan harfiah mobil apa pun. Dua mobil itu sinyal kuat, bukan
> bukti: byte yang belum kami petakan bisa saja beda, dan mobil ICE murni belum pernah dicoba.
> Kalau mobilmu beda, tolong coba & kirim
> [laporan mobil](https://github.com/GodrezJr2/openlinko/issues/new?template=add-car.yml) ya — satu mobil kedua
> jauh lebih berharga buat proyek ini daripada berapa lama pun menatap yang pertama. 🙏

## Demo

<p align="center"><img src="docs/media/walkthrough.gif" width="800" alt="Walkthrough tampilan v2: beranda, energi, kalender jarak, tampilan pintu 3D, pengisian dan kalkulator cas"></p>

*Satu rekaman utuh tampilan v2 di layar seukuran HP, jalan di mode demo bawaan
(`python server.py --demo`, data contoh, tanpa akun). Diedit di [Motion Studio](https://github.com/GodrezJr2/motion-studio).*

Versi mobil asli: [1½ menit di HP dengan Jaecoo J5 EV asli](https://github.com/user-attachments/assets/f17d167d-cbf9-4eb0-92b4-44361f6da6a5)
(tampilan Classic, plat & VIN disamarkan, bisa juga [diunduh](https://github.com/GodrezJr2/openlinko/releases/download/assets/j5-dashboard-demo.mp4)).

## Screenshot

**Tampilan v2** (default di `/`, juga di `/v2.html`). Gambarnya ikut tema GitHub kamu;
tema terang dan gelap dua-duanya sudah ada.

<table>
<tr><th>Beranda</th><th>Energi</th><th>Jarak</th></tr>
<tr><td align="center" width="33%"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/v2-home-dark.jpg"><img src="docs/screenshots/v2-home-light.jpg" width="260" alt="Home: range, battery, climate, doors and tyres"></picture></td><td align="center" width="33%"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/v2-energy-dark.jpg"><img src="docs/screenshots/v2-energy-light.jpg" width="260" alt="Energy: kWh/100 km per day, net of regen, beside the head-unit figure"></picture></td><td align="center" width="33%"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/v2-dist-dark.jpg"><img src="docs/screenshots/v2-dist-light.jpg" width="260" alt="Distance: a calendar of km, energy and charging cost per day"></picture></td></tr>
<tr><th>Pintu &amp; jendela</th><th>Pengisian</th><th>Kalkulator cas</th></tr>
<tr><td align="center" width="33%"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/v2-doors-dark.jpg"><img src="docs/screenshots/v2-doors-light.jpg" width="260" alt="Doors and windows on a 3D car you can turn, with remote controls"></picture></td><td align="center" width="33%"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/v2-chg-dark.jpg"><img src="docs/screenshots/v2-chg-light.jpg" width="260" alt="Charging: last session curve, kWh in and cost"></picture></td><td align="center" width="33%"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/screenshots/v2-plan-dark.jpg"><img src="docs/screenshots/v2-plan-light.jpg" width="260" alt="Charge calculator: time, kWh and cost to a target %"></picture></td></tr>
</table>


*Pakai data demo. Plat & VIN disembunyikan secara default (tombol mata privasi).*

**Tampilan Classic** (`/index.html`, atau jadikan default lewat Pengaturan) punya tambahan perencana perjalanan jauh dan peta SPKLU:

<table>
<tr><th>Perencana perjalanan</th><th>Peta SPKLU</th></tr>
<tr><td align="center" valign="top"><img src="docs/screenshots/trip-planner.png" width="300" alt="Perencana perjalanan"></td><td align="center" valign="top"><img src="docs/screenshots/spklu-map.png" width="300" alt="Peta SPKLU"></td></tr>
</table>

---

## ⚠️ Legal & etika — baca ini dulu

Ini project **interoperability / reverse-engineering pribadi** untuk akses **mobil dan akunmu
sendiri**. Disediakan untuk keperluan edukasi & pribadi.

- **Pakai hanya dengan akun dan mobil milikmu sendiri.** Jangan akses data orang lain.
- Ini ngobrol sama **API vendor yang privat & tak terdokumentasi**. **Tanpa garansi** dan bisa
  rusak kapan saja kalau vendor mengubah backend-nya. **Tidak berafiliasi, tidak didukung**
  oleh Jaecoo, Chery, maupun CarLinko.
- **Tidak ada data pribadi yang disertakan.** Akun, token, VIN, plat, vehicle id, dan device
  serial-mu cuma ada di `creds.json` yang gitignored (lihat [Setup](#setup)). Kunci penanda-tangan
  request itu **konstanta app** (string yang sama di tiap install CarLinko, gampang dibaca dari
  APK) — di-bundle biar setup cukup email + password; itu bukan rahasia yang terikat ke kamu.
- **Jangan jalankan ini sebagai layanan publik/multi-user.** Itu berarti menyimpan kredensial
  orang lain (yang bisa membuka/mengontrol mobil mereka) dan hampir pasti melanggar ketentuan
  vendor. Deployment yang dimaksud adalah **satu instance per pemilik**, self-hosted, privat
  (mis. di belakang Tailscale). Lihat [Menuju multi-user](#menuju-multi-user).
- Sebagian besar read-only. Tab Control **sudah ada** (kunci, A/C, jendela, sunroof, bagasi,
  find-car, stop charging), tapi statusnya **beta**: cuma *Stop charging* yang opcode-nya
  terkonfirmasi, sisanya hasil decode best-effort dari APK, dan tiap tap itu **aksi nyata di mobil
  nyata** — perhatikan mobilnya waktu dipakai. Juga **cloud-only: belum bisa Bluetooth.** Kontrol
  Bluetooth-proximity yang ada di app CarLinko **tidak** diimplementasikan, jadi mobil harus bangun
  dan punya sinyal seluler; kalau tidak, command-nya gagal (`50043`).

Kalau ga setuju sama poin di atas, jangan dipakai.

---

## Fitur

Tampilan default adalah **v2** (`/`): app yang berpusat di mobil, model 3D mobilmu dengan status
live dan satu layar untuk tiap bagiannya. Tampilan Classic masih ada di `/index.html` (atau ganti di Pengaturan).

- **Mobil live** — baterai %, jarak, odometer, 12 V, parkir / charging / jalan, pintu, jendela,
  sunroof, bagasi dan status kunci, dikirim lewat WebSocket realtime CarLinko dan disimpan di SQLite.
- **Kontrol jarak jauh** — kunci / buka, AC on / off dengan suhu target, jendela, bagasi, find car,
  stop charging. Perintahnya dienkripsi AES seperti app resmi, dan UI baru berubah setelah mobil
  sendiri melaporkannya. Kunci, bagasi, jendela dan AC sudah terkonfirmasi di J5 EV; lihat
  [docs/control-opcodes.md](docs/control-opcodes.md). **Cloud-only — belum bisa Bluetooth.**
- **Climate** — AC dan suhu target, plus panel kursi gaya head unit; kontrol pemanas / ventilasi
  kursi dan defog masih beta.
- **Energi** — kWh/100 km per trip dan rata-rata bergulir **bersih setelah regen** (angka head unit
  tetap ada sebagai "sebelum regen"), total kWh, biaya dan km, hemat vs bensin.
- **Baterai & pengisian** — sesi charge terdeteksi otomatis (kWh masuk pack, kWh dibayar, biaya),
  kurva charge, tips perawatan baterai, kesehatan aki 12 V, dan perkiraan kasar kesehatan baterai
  dari charge panjang (AC di rumah atau DC cepat, tanpa alat OBD).
- **Ban** — tekanan per roda kalau mobil punya TPMS langsung; satu status di mobil dengan TPMS tidak langsung.
- **Share card** — gambar statistik mobilmu yang rapi untuk dibagikan, tanpa plat dan VIN.
- **Add-on head unit** — Climate Gesture: atur kipas dan suhu pakai dua jari di head unit J5,
  dipasang dari dashboard lewat jaringan lokal. Lihat [Add-on head unit](#add-on-head-unit-climate-gesture).
- **BEV dan PHEV** — level bensin, jarak bensin dan konsumsi bensin di PHEV.
- **Home Assistant** — baca lewat REST sensor + notif baterai rendah / charge selesai
  ([docs/HOMEASSISTANT.md](docs/HOMEASSISTANT.md)).
- **Tambahan (opsional, butuh Google Maps key)** — perencana charge perjalanan jauh dan peta SPKLU.
- Toggle privasi, dark mode, English / Bahasa Indonesia.

Lihat [PRODUCT.md](PRODUCT.md) untuk alasan produk dan [DESIGN.md](DESIGN.md) untuk sistem visual.

## Arsitektur

```
  TCU mobil ─(seluler)─> cloud CarLinko ──┐
                                          │  WebSocket (auth token, tanpa signing) — blob telemetri
   tools/logger.py  ◀──────────────────────┘  decode + simpan tiap frame ke carlinko.db
        │                                      (auth.py auto-refresh token saat kedaluwarsa)
        ▼
   carlinko.db (SQLite)
        │
        ▼
   tools/server.py  ── /api/summary, /api/trip, /api/spklu ──▶  web/ PWA (vanilla JS, Leaflet)
   (http.server stdlib)        + Google Places (opsional)        disajikan lewat Tailscale
```

- **Tanpa framework, tanpa build step.** Backend pakai pustaka standar Python; frontend HTML/CSS/JS
  tulis tangan dengan dua lib vendored (Leaflet, slot-text). Self-hosted & ramah offline.
- **Telemetrinya blob 73 byte.** Offset field dipetakan dengan cara nyetir mobil dan ngeliat byte
  mana yang berubah (baterai = byte 28, range = 29–30 BE, odometer = 18–20 BE, …).
  Lihat [docs/api-map.md](docs/api-map.md).

## Akurasi

Analitik charge dikalibrasi terhadap struk PLN Mobile asli si pemilik:

| Sesi               | Dashboard            | Struk                | Cocok   |
| ------------------ | -------------------- | -------------------- | ------- |
| 58 → 100 %         | 28,9 kWh / Rp 73.491 | 28,94 kWh / Rp 73.521 | 99,9 % |
| 35 → 80 %          | 29,1 kWh / Rp 73.981 | 29,23 kWh / Rp 74.273 | 99,6 % |

Efisiensi charge DC dimodelkan tergantung SoC (isi sampai 100 % rugi lebih banyak dari sampai
80 %), dikalibrasi ke dua struk. Pack terpakai ≈ 58,9 kWh.

Perencana charge memperkirakan yang benar-benar kamu bayar di meteran, dicek terhadap struk
SPKLU PLN Mobile asli:

| Perencana charge di app | Struk PLN Mobile asli |
| :---: | :---: |
| ![Estimasi perencana charge](docs/screenshots/accuracy-app.png) | ![Struk SPKLU PLN Mobile](docs/screenshots/accuracy-receipt.png) |

App memperkirakan **58,2 kWh** untuk dibeli di meteran @ **Rp 2.540/kWh**; struk menunjukkan
**57,34 kWh** yang benar-benar terkirim pada tarif all-in **Rp 2.540/kWh** yang sama — harga
per-kWh-nya pas dan volumenya meleset ~1,5 % (sesi di struk berhenti sedikit sebelum penuh).
Hitungan refund-nya juga cocok: beli Rp 152.448, terpakai Rp 145.694.

## Coba dulu (demo, tanpa akun)
Mau lihat tampilannya sebelum setup? Jalankan **mode demo** — data palsu tapi realistis, tanpa
akun CarLinko, tanpa mobil, tanpa database:
```bash
cd tools && python server.py --demo      # lalu buka http://localhost:8088
# atau pakai Docker:  docker compose run --rm -p 8088:8088 web python server.py --demo 8088
```
Ada banner 🧪 *Demo mode* biar jelas semua datanya bukan asli. Enak buat lihat-lihat atau screenshot.

## Privasi & keamanan
Semua jalan **di komputermu sendiri** — tidak ada backend yang aku operasikan, dan datamu tidak
pernah dikirim ke server manapun yang aku kontrol. Detail lengkap di **[SECURITY.md](SECURITY.md)**; singkatnya:
- **Email/password** CarLinko kamu disimpan lokal di `tools/creds.json` (di-gitignore) dan dipakai
  cuma untuk login ke cloud **milik CarLinko** (`*.hzhjcl.com`) lewat TLS — sama seperti appnya.
- Panggilan keluar lainnya cuma ke **Google Maps** (kalau kamu isi key) dan layanan peta/rute gratis
  (OpenStreetMap / OSRM) buat perencana trip. Selain itu tidak ada yang keluar dari device-mu.
- Jaga dashboard tetap privat (LAN / Tailscale). Kalau terpaksa kena internet, set
  `dashboard_password` biar `/api/summary` tidak terbuka untuk publik.
- Nemu celah keamanan? Lihat [SECURITY.md](SECURITY.md) — lapor secara privat, jangan buka issue publik.

## Setup

### Prasyarat
- Python 3.10+, `pip install requests websocket-client`
- Akun CarLinko yang ada mobilmu
- (opsional) Google Maps API key untuk perencana trip / peta SPKLU

Tanpa capture app, tanpa MITM, tanpa decompile — cukup login pakai akunmu. (Kunci penanda-tangan
sudah di-bundle, dan blob `v-data` yang dikirim app ternyata diabaikan server, jadi dibuang.)

### Risiko akun — baca dulu
Dashboard ini **tidak resmi**: dia ngobrol ke cloud CarLinko dengan cara yang sama seperti app, tapi
tanpa izin CarLinko. Di November 2026 ada user yang lapor akun CarLinko yang dipakai dashboard-nya
**di-disable** ("Your account has been disabled"). Pemicunya belum diketahui. Akun apa pun yang
kamu loginkan ke dashboard bisa kena hal yang sama, jadi pakai dengan risiko sendiri.

Yang dilakukan dashboard supaya jejaknya kecil: satu socket yang terus terbuka (bukan polling), dan
**login guard**: login ulang otomatis dibatasi 6x per jam, mundur dari 1 menit sampai 30 menit
setelah gagal, dan berhenti total kalau CarLinko menolak akunnya (dashboard lalu menampilkan banner
sampai kamu login ulang manual). Selalu update ke versi terbaru. Versi lama bisa mencoba login yang
gagal setiap beberapa detik.

### Akun kedua (opsional)
CarLinko cuma izinin **satu sesi aktif per akun**, jadi login dashboard bisa nge-logout app
resmi-mu. Bentrok ini bisa dihindari dengan kasih dashboard **akun CarLinko-nya sendiri** (akun
utama jadi tidak ikut, tapi lihat catatan risiko di atas: akun yang dilaporkan di-disable justru
akun kedua):

1. Bikin akun CarLinko kedua (email beda).
2. Dari akun utama, **Me → Authorisation → +** lalu authorise email akun kedua ke mobilmu.
3. Login-kan dashboard ke akun kedua; app tetap di akun utama.

> Catatan: layar *Authorisation* di app menyebut berbagi kontrol Bluetooth — pastikan akun yang
> di-authorise juga bisa narik mobil lewat **cloud** (jalankan `python setup.py` di akun itu; kalau
> auto-deteksi nemu mobilnya, berarti aman). Kalau ga bisa, alternatifnya pakai satu akun saja dan
> terima sesekali login ulang.

### Cara cepat — Docker (disarankan)
```bash
docker compose up -d        # lalu buka http://localhost:8088
```
Pas pertama buka, dashboard nampilin **halaman login** — isi **email + password** CarLinko-mu,
nanti dia login dan **auto-deteksi mobilmu** (vehicle id, device SN, VIN, plat, model). Selesai.
Lebih suka terminal? `docker compose run --rm web python setup.py` melakukan hal yang sama secara
interaktif. Semua yang persisten (creds, token, database) ada di `./data`.

### Cara cepat — satu perintah (Linux, selalu nyala)

Kalau punya mesin yang nyala terus — home server, mini PC, Raspberry Pi — ini mengurus semuanya:
virtualenv, dependensi, login, dan dua service systemd biar selamat dari reboot.

```bash
git clone https://github.com/GodrezJr2/openlinko.git
cd openlinko
./tools/install.sh                 # tambah --tailscale untuk akses dari HP di mana pun
```

Yang ditanya cuma yang memang tak bisa ditebak: login CarLinko dan negara/mata uangmu. Semuanya
terikat ke user dan folder ini — tak ada path yang diasumsikan, tak ada yang dipasang global
kecuali Tailscale kalau kamu minta.

```
./tools/install.sh --tailscale     # + akses privat dari mana saja, tanpa ekspos ke publik
./tools/install.sh --port 9000     # port lain
./tools/install.sh --no-service    # cuma setup; tanpa systemd
```

**Kenapa `--tailscale`?** Logger perlu jalan 24/7 untuk membangun tren, riwayat pengisian dan biaya.
Kamu pasti mau dashboard-nya di HP — tapi ini membaca data mobilmu, jadi **jangan** di-port-forward
ke internet terbuka. Tailscale menaruh mesin dan HP-mu di satu jaringan privat, jadi dashboard bisa
diakses dari mana saja tapi tetap tak terlihat oleh siapa pun. Gratis untuk pemakaian pribadi.

### Cara cepat — Python (manual)
```bash
pip install requests websocket-client
cd tools
python setup.py                # konfigurasi interaktif + login + auto-deteksi mobil
python logger.py --adaptive    # rekam telemetri (cepat saat aktif, lambat saat parkir)
python server.py 8088          # dashboard di http://<host>:8088
```
Ga mau pakai helper? `cp creds.example.json tools/creds.json && chmod 600 tools/creds.json`
lalu isi manual. `creds.json` dan `token.txt` gitignored — jangan pernah di-commit.

Unit systemd rujukan ada di [`tools/`](tools/) kalau mau menulis sendiri
([logger](tools/carlinko-logger.service), [web](tools/carlinko-web.service)) — tapi `install.sh`
sudah membuatkan yang benar sesuai user dan path-mu, jadi harusnya tak perlu.

### Referensi `creds.json`
| key | wajib | apa |
| --- | --- | --- |
| `email`, `password` | ✅ | login CarLinko-mu (plaintext via TLS; disimpan lokal saja) |
| `region` | | region API, default `sea` |
| `vehicle_id`, `device_sn` | auto | vehicle id + serial device — **`setup.py` yang ngisiin** |
| `vehicle` | auto | `{plate, model, vin}` — auto-deteksi; UI sembunyiin plat+VIN default |
| `battery_kwh`, `wltp_kwh_100`, `tariff_idr` | | kapasitas paket berguna + rujukan WLTP + tarif lokal. **Mobil tidak pernah mengirim ukuran paket**, jadi angkanya dari kamu atau dari tabel mobil dikenal di [`tools/known_cars.py`](tools/known_cars.py); model yang belum dikenal ditanya saat setup dan ditandai *asumsi* di UI sampai diisi. Angka ini menskalakan semua kWh, biaya dan efisiensi |
| `gmaps_key` | | Google Maps key — aktifin perencana trip + peta SPKLU (kalau ga, fallback OSM) |
| `dashboard_password` | | set (halaman login → Advanced) untuk kunci dashboard pakai password — **wajib kalau URL-nya bisa diakses dari internet** |

## Mau di-host di mana

Butuh host yang **nyala 24/7** (logger polling terus buat tren + riwayat charge). HP yang kamu
bawa sehari-hari ga bisa jadi host: iOS ga bisa jalanin server background sama sekali, dan Android
bakal matiin app background di HP yang dibawa-bawa. Tapi **HP Android bekas yang dicolok charger**
bisa (lihat [HP Android bekas (Termux)](#hp-android-bekas-termux) di bawah). HP kamu sendiri cukup
jadi browser (add to home screen jadi PWA).

| Host | Biaya | Catatan |
| --- | --- | --- |
| PC nganggur / laptop lama / **Raspberry Pi** di rumah | gratis | paling privat; akses lewat [Tailscale](https://tailscale.com) |
| **HP Android bekas** dicolok charger (Termux) | gratis | ga perlu PC; lihat [di bawah](#hp-android-bekas-termux). Udah dites di emulator Android 14; laporan dari HP asli ditunggu |
| **VPS** murah (Hetzner, Contabo, DigitalOcean…) | ~$4/bln | paling gampang nyala terus; privat pakai Tailscale, atau set `dashboard_password` |
| **Fly.io / Railway / Render** free tier | gratis | deploy Docker image; set `dashboard_password`. Host yang cuma kasih satu service + satu volume bisa jalanin logger bareng dashboard pakai start command `bash railway_start.sh` (lihat bawah) |
| **Oracle Cloud Free / Google e2-micro** | gratis | VM nyala terus gratis |

### HP Android bekas (Termux)

HP Android 7+ yang udah ga kepake bisa jadi server yang nyala terus: colok charger, sambung Wi-Fi, taruh di laci.

1. Install **Termux** dan **Termux:Boot** dari [F-Droid](https://f-droid.org/packages/com.termux/)
   (Termux versi Play Store udah ketinggalan). Buka Termux:Boot sekali.
2. Di Termux:
   ```bash
   pkg install -y git && git clone https://github.com/GodrezJr2/openlinko ~/openlinko
   bash ~/openlinko/tools/termux-setup.sh
   ```
3. Buka alamat yang muncul, lalu login.

Skripnya install Python + dua library, nahan wake-lock, nyalain ulang dashboard kalau mati, dan
jalan lagi otomatis setelah HP restart. Kontrolnya: `openlinko start | stop | restart | status | log | update`.

Biar ga dimatiin Android:
- **Pengaturan → Aplikasi → Termux → Baterai → Tidak dibatasi.** Di Xiaomi / OPPO / vivo / realme
  juga izinkan **Autostart** dan kunci Termux di layar aplikasi terbaru.
- Android 12+ bisa matiin proses anak Termux ("phantom process killer"). Di Android 14+ nyalakan
  **Opsi pengembang → Disable child process restrictions**; di 12–13 jalankan sekali dari PC:
  `adb shell settings put global settings_enable_monitor_phantom_procs false`.
- Biar bisa dibuka dari luar rumah, install app Tailscale di HP ini dan HP kamu.

> **Host publik = wajib set dashboard password.** Di host privat/rumah/Tailscale boleh dibiarin
> kebuka. Begitu URL-nya bisa dicapai dari internet, set `dashboard_password` (halaman login →
> Advanced) biar cuma kamu yang bisa buka.

> **Satu service, dua proses.** `docker compose` jalanin dashboard sama logger sebagai dua
> service yang share `./data`. Host yang nempelin volume ke *satu* service doang (Railway) nggak
> bisa gitu, jadi `tools/railway_start.sh` jalanin logger di background dan dashboard di
> foreground dari satu container. Set jadi start command service-nya — `bash railway_start.sh` —
> dan taruh isi `creds.json` di service variable `CREDS_JSON`; script-nya nulis itu ke volume
> tiap boot. Ini sengaja **bukan** default image: CarLinko cuma ngebolehin satu sesi aktif per
> akun, jadi `docker run` yang diam-diam nyalain logger bakal bikin app CarLinko kamu sendiri
> ke-logout.

### Setup per-OS
Jalur Docker sama persis di semua OS — install Docker, lalu `docker compose up -d` dan buka
`http://localhost:8088`:
- **macOS / Windows**: install [Docker Desktop](https://www.docker.com/products/docker-desktop/), buka, lalu jalanin dua perintah di Terminal / PowerShell dari folder repo yang udah di-clone.
- **Linux**: `sudo apt install docker.io docker-compose-plugin` (atau setara di distro-mu), lalu dua perintah yang sama.

Ga pakai Docker? Install **Python 3.10+** ([python.org](https://www.python.org/downloads/) di macOS/Windows, `sudo apt install python3 python3-pip` di Linux) lalu pakai langkah *Cara cepat — Python* di atas.

### Setup pakai AI coding agent
Kalau ga biasa sama terminal, paste ini ke AI coding agent (Claude Code, Cursor, dll) yang jalan
di mesin yang bakal jadi host:

```text
Set up the open-source project https://github.com/GodrezJr2/openlinko on this machine.
Clone it, then bring it up with Docker (docker compose up -d). It serves a login page on
http://localhost:8088 — tell me the URL when it's running. I'll enter my CarLinko email and
password there myself; do not ask me for them. If Docker isn't available, fall back to the
Python quick-start in the README (pip install requests websocket-client, then run
tools/server.py and tools/logger.py). If the host is reachable from the internet, remind me to
set a dashboard password on the login page's Advanced section.
```

## Add-on head unit: Climate Gesture
Atur kipas dan suhu dari **mana aja di layar head unit** pakai dua jari, tanpa buka layar climate.
Taruh dua jari sekitar sepertiga detik, lalu geser: ke samping = kipas (1 sampai 10), atas/bawah
= suhu (15.5 sampai 30.5 °C). Ada kartu kecil yang nunjukin nilainya. Nyala sendiri tiap
restart. Dites di Jaecoo J5 EV asli (head unit T13J-INTL 00.04.15, Android 12).

**Panduan step-by-step plus gambar ada di dalam dashboard:** jalanin di laptop (Windows: file
`start`, atau `python tools/server.py`), login, lalu **Account → Head unit add-ons**. Cuma mau
add-on-nya? Ga perlu login CarLinko: tap **Only want the head unit add-on?** di halaman sign-in,
atau buka `/addons`. Sekitar 10 menit, mobil parkir, tanpa kabel. Versi singkat:

1. **Engineering menu** — di head unit *Settings → System → Version information*, tap
   *APP Version* 10 kali, isi password = **6 digit terakhir SOC Version**.
2. **Enable ADB** — nyalain di Engineering mode. Yang lain jangan disentuh.
3. **Hotspot yang sama** — nyalain hotspot HP; head unit (*Connection → WiFi*) dan laptop konek ke situ.
4. **Find dan install** — tap *Find head unit*, pilih, *Install*.
5. **Coba** — dua jari, tahan, geser. Habis itu matiin lagi WiFi head unit (CarPlay / Android
   Auto wireless ga jalan selama WiFi nyala); add-on tetap jalan.

Ga perlu backup: cuma install app biasa, ga ada file sistem atau setting mobil yang berubah. Buat
uninstall, buka app Climate Gesture lalu tap **Remove Climate Gesture**. Setelah terpasang, app ini
nutup ADB lewat WiFi jadi device lain di jaringan ga bisa masuk head unit. **Ga resmi** — bukan dari
Jaecoo atau Chery; update head unit bisa bikin ga jalan. Installer ngecek A/C dulu dan nolak head
unit yang ga dikenal. Source: [headunit/climate-gesture](headunit/climate-gesture), APK:
[headunit/dist](headunit/dist) (perintah `adb` manual ada di halaman add-ons).

## Menuju multi-user

Ini sengaja **single-tenant per instance**. Cara bersih biar pemilik lain bisa pakai adalah
dengan **tiap orang menjalankan instance-nya sendiri** dengan `creds.json` masing-masing —
bukan nge-host satu layanan yang menyimpan kredensial semua orang. Model berbeda bisa override
`battery_kwh` / `wltp_kwh_100` / `tariff_idr`, dan nama/VIN/plat kendaraan datang dari
`creds.json`, jadi app-nya udah adaptif per mobil.

## Struktur project
- `tools/` — backend Python (`server.py`, `logger.py`, `auth.py`, `setup.py`) + utilitas reverse-engineering
- `web/` — PWA-nya (satu `index.html` + `leaflet.*` & `slot-text.js` vendored)
- `docs/` — peta API dan catatan signing hasil decompile (rahasia sudah diredaksi)
- `PRODUCT.md`, `DESIGN.md` — catatan produk + desain visual

## Kontribusi
Pemilik Jaecoo / CarLinko lain dipersilakan — [laporan mobil](https://github.com/GodrezJr2/openlinko/issues/new?template=add-car.yml)
paling berguna sekarang: di dashboard, **Akun → Report my car** nyalin laporan yang udah
disensor (tanpa plat, VIN, lokasi) buat ditempel di situ. Lihat
[CONTRIBUTING.md](CONTRIBUTING.md), dan [SECURITY.md](SECURITY.md) untuk privasi/keamanan.
Tanya-tanya → [Discussions](https://github.com/GodrezJr2/openlinko/discussions).

## Lisensi
[MIT](LICENSE). Tidak berafiliasi dengan Jaecoo, Chery, maupun CarLinko. Merek dagang milik pemiliknya masing-masing.

# Security & privacy

This project is **self-hosted**. There is no server I run, no account on my side, and no telemetry
phoning home. Everything below describes what the code on *your* machine does.

## What data the app touches, and where it goes

| Data | Stored | Leaves your machine? |
| --- | --- | --- |
| CarLinko email + password | `tools/creds.json` (local, gitignored) | Only to **CarLinko's own cloud** (`*.hzhjcl.com`) over HTTPS, to log in — exactly like the official app |
| Auth token | `tools/token.txt` (local, gitignored) | Sent back to CarLinko's cloud on each request |
| Telemetry (SoC, range, odometer, …) | `carlinko.db` (local SQLite) | No |
| Vehicle plate / VIN | `creds.json` (local) | No (UI masks them by default) |
| Trip planner queries (place names, route) | not stored | To **Google Maps** (only if you set `gmaps_key`) and/or free OpenStreetMap / OSRM endpoints |

**No analytics, no tracking, no third-party backend.** The only outbound traffic is to CarLinko's
cloud and the optional map services above.

## Your responsibilities when hosting

- **Never commit** `creds.json`, `token.txt`, your `gmaps_key`, password, VIN or plate. They are
  already in `.gitignore` — keep them there.
- Prefer to keep the dashboard on a **private network** (LAN or [Tailscale](https://tailscale.com/)).
- If the dashboard **must** be reachable from the internet, set a `dashboard_password`
  (login page → *Advanced*). Without it, `/api/summary` is open to anyone who finds the URL.
- Restrict your Google Maps API key in the Google Cloud Console so a leaked key can't be abused. The
  dashboard calls Google from the server and the key never reaches the browser, so:
  - **API restriction:** allow only **Places API (New)**, the one Google API it uses
    (`places:searchText`, `places:searchNearby`).
  - **Application restriction:** **IP addresses**, set to the host's public outbound IP, if it has a fixed
    one. Do **not** pick *Websites (HTTP referrers)*: a server call sends no `Referer`, so Google refuses
    every request and the dashboard quietly falls back to OpenStreetMap. A host with no fixed outbound IP
    (Railway's Hobby plan has none) cannot use an IP allowlist: keep the API restriction, add a daily quota
    cap and a budget alert instead.
  - When Google refuses the key, the server logs `google places refused the request (<reason>)` once and the
    trip planner answers `"src": "osm"`, so a wrong restriction shows up instead of passing for a working key.
- Use a **second CarLinko account** for the dashboard (see the README) so a shared token isn't tied
  to your primary login.

## How auth works (for the curious)

- The optional dashboard password is stored **salted + SHA-256 hashed** — the plaintext is never saved.
- Sessions are stateless **HMAC-signed cookies** (30-day expiry) keyed by a random per-install secret.
- The CarLinko request signing key is an **app-global constant** (identical in every install of the
  official app), so bundling it exposes nothing your own APK doesn't already contain.

## Reporting a vulnerability

Found something? **Please report it privately first** — don't open a public issue with exploit
details. Use [GitHub private vulnerability reporting](https://github.com/GodrezJr2/openlinko/security/advisories/new)
(Security tab → *Report a vulnerability*). I'll respond as fast as I can.

This is a hobby project with no warranty — see [LICENSE](LICENSE).

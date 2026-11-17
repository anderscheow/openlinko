# research/

Scripts used to reverse-engineer CarLinko and the J5 head unit. **The dashboard doesn't need
any of them**; everything it runs lives in [`tools/`](../tools). They're kept so the findings in
[`docs/api-map.md`](../docs/api-map.md) and [`docs/control-opcodes.md`](../docs/control-opcodes.md)
can be reproduced. Run them from the repo root; they read `creds.json` / `token.txt` from `tools/`.

| Area | Scripts |
| --- | --- |
| Request signing (from `libapp.so` via Blutter) | `blutter_setup.sh`, `sig_crack.py`, `sig_verify.py`, `decompiled/` |
| Captured app traffic (mitmproxy) | `parse_flows.py`, `parse_ws.py`, `extract_token.py` |
| Realtime WebSocket | `ws_client.py`, `ws_diag.py` |
| Decoding the telemetry blob | `find_power.py`, `find_consumption.py`, `speed_cal.py`, `door_probe.py`, `check_live.py`, `report.py` |
| Cloud account | `query_service.py` (telematics subscription expiry) |
| Head unit VHAL (read-only, root ADB) | `hu_probe.py` (snap / diff / watch) |
| 3D car model for `web/car3d.js` | `car-model/` (`car_prep.py` → `car_solid.py` → `split_car.py`, `car_mirror.py`, `cleanup_dense.sh`) |

Some early scripts read an old `carlinko.db` at the repo root; the logger now writes it to
`tools/` (or `$CARLINKO_DATA`), so point them there if you re-run one.

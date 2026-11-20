#!/usr/bin/env python3
"""Checks for the opt-in car location feature (#23): the logger's cached-position reader and the
server's two read-only views. Nothing here touches the network or the owner's real data."""
import atexit
import contextlib
import io
import json
import math
import os
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import MagicMock, patch

_TMP = tempfile.TemporaryDirectory()
atexit.register(_TMP.cleanup)
os.environ["CARLINKO_DATA"] = _TMP.name        # both modules read it at import: never the real creds.json
sys.path.insert(0, os.path.dirname(__file__))
import auth
import location_settings
import logger
import server


class FixTest(unittest.TestCase):
    def test_only_plausible_fixes_pass(self):
        self.assertEqual(logger._loc_fix({"lat": 3.139, "lng": 101.6869}), (3.139, 101.6869))
        self.assertEqual(logger._loc_fix({"lat": "3.139", "lng": "101.6869"}), (3.139, 101.6869))
        for bad in (None, [], "x", {}, {"lat": None, "lng": 1}, {"lat": "abc", "lng": 1},
                    {"lat": 0, "lng": 0},                       # the "no fix" placeholder
                    {"lat": 91, "lng": 0}, {"lat": 0, "lng": 181},
                    {"lat": math.nan, "lng": 1}, {"lat": math.inf, "lng": 1}):
            self.assertIsNone(logger._loc_fix(bad), bad)

    def test_sea_region_repairs_the_longitude_the_cloud_sends_a_digit_short(self):
        # Seen live 2026-11-19: a car in Cheras/Kajang (E 101.77) came back as 10.177414 = real / 10.
        lat, lng = logger._loc_fix({"lat": 3.048407, "lng": 10.177414}, "sea")
        self.assertEqual(lat, 3.048407)
        self.assertAlmostEqual(lng, 101.77414, places=5)
        for lng_ok in (101.77414, 95.2, 90.0, 140.5, 179.9):             # already inside the region: untouched
            self.assertEqual(logger._loc_fix({"lat": 3.0, "lng": lng_ok}, "sea"), (3.0, lng_ok))

    def test_sea_region_drops_what_cannot_be_right_instead_of_drawing_it_in_africa(self):
        for lng_bad in (5.0, 9.9, 18.5, 25.0, -70.0):                    # x10 is not a sea longitude either
            self.assertIsNone(logger._loc_fix({"lat": 3.0, "lng": lng_bad}, "sea"), lng_bad)

    def test_regions_without_a_known_box_pass_through_unchanged(self):
        for region in (None, "", "eu", "unknown"):
            self.assertEqual(logger._loc_fix({"lat": 48.1, "lng": 11.5}, region), (48.1, 11.5), region)

    def test_the_log_says_it_once_and_never_prints_a_coordinate(self):
        import contextlib, io
        buf = io.StringIO()
        with patch.object(logger, "_LOC_SAID", set()), contextlib.redirect_stdout(buf):
            for _ in range(3):
                logger._loc_fix({"lat": 3.048407, "lng": 10.177414}, "sea")
                logger._loc_fix({"lat": 3.048407, "lng": 5.0}, "sea")
        out = buf.getvalue()
        self.assertEqual(out.count("digit short"), 1)
        self.assertEqual(out.count("outside the sea region"), 1)
        for needle in ("3.048", "10.177", "101.77", "5.0"):
            self.assertNotIn(needle, out)

    def test_config_typos_fall_back_instead_of_raising(self):
        with patch.dict(logger._C, {"location_interval": "soon", "location_keep_days": ""}):
            self.assertEqual(logger._loc_int("location_interval", 30, 10, 86400), 30)
            self.assertEqual(logger._loc_int("location_keep_days", 90, -1, 36500), 90)
        with patch.dict(logger._C, {"location_interval": 1}):
            self.assertEqual(logger._loc_int("location_interval", 30, 10, 86400), 10)   # clamped, not obeyed
        self.assertFalse(location_settings.flag("false"))
        self.assertTrue(location_settings.flag("true"))
        self.assertFalse(location_settings.flag(None))


class LocateTest(unittest.TestCase):
    """locate() is the only code in this feature that talks to CarLinko."""

    def setUp(self):
        for target, value in ((auth, {"login_status": lambda: None, "api_base": lambda: "https://api.invalid",
                                      "headers_for": lambda body, token=None: {"t": token}}),):
            for name, fn in value.items():
                p = patch.object(target, name, fn)
                p.start()
                self.addCleanup(p.stop)
        for name, value in (("_cfg", lambda: {"device_sn": "SN1"}), ("_loc_token", lambda: "tok")):
            p = patch.object(logger, name, value)
            p.start()
            self.addCleanup(p.stop)

    def post(self, reply):
        resp = MagicMock()
        resp.json.return_value = reply
        return patch("requests.post", return_value=resp)

    def test_reads_the_cached_position_with_the_exact_request_the_cloud_accepts(self):
        with self.post({"code": "0000", "data": {"lat": 3.139, "lng": 101.6869, "address": None}}) as post:
            self.assertEqual(logger.locate(), (3.139, 101.6869))
        (url,), kw = post.call_args
        self.assertEqual(url, "https://api.invalid/maps/deviceLocate")
        self.assertEqual(kw["json"], {"sn": "SN1", "showAddress": 1})
        self.assertIs(type(kw["json"]["showAddress"]), int)       # JSON true is answered 1000 "unknown error"
        self.assertEqual(kw["headers"], {"t": "tok"})

    def test_locate_applies_the_account_region_to_the_longitude(self):
        reply = {"code": "0000", "data": {"lat": 3.048407, "lng": 10.177414, "address": None}}
        with self.post(reply):                                           # no region in creds: defaults to sea
            lat, lng = logger.locate()
        self.assertAlmostEqual(lng, 101.77414, places=5)
        with self.post(reply), patch.object(logger, "_cfg", lambda: {"device_sn": "SN1", "region": "eu"}):
            self.assertEqual(logger.locate(), (3.048407, 10.177414))     # another region: not ours to rewrite

    def test_50052_means_this_car_has_no_position_in_the_cloud(self):
        with self.post({"code": "50052", "msg": "查询定位失败"}):
            self.assertEqual(logger.locate(), "unsupported")

    def test_everything_else_is_a_quiet_retry_later(self):
        for reply in ({"code": "9997"}, {"code": "0000", "data": {"lat": 0, "lng": 0}},
                      {"code": "1000", "msg": "x"}, ["not", "a", "dict"], {"code": "0000", "data": None}):
            with self.post(reply):
                self.assertIsNone(logger.locate(), reply)
        with patch("requests.post", side_effect=OSError("down")):
            self.assertIsNone(logger.locate())

    def test_no_request_while_the_login_guard_holds_or_before_setup(self):
        with self.post({"code": "0000", "data": {"lat": 1, "lng": 1}}) as post:
            with patch.object(auth, "login_status", lambda: {"blocked": True, "wait": None, "reason": "x"}):
                self.assertIsNone(logger.locate())
            with patch.object(logger, "_loc_token", lambda: ""):
                self.assertIsNone(logger.locate())
            with patch.object(logger, "_cfg", lambda: {}), patch.object(logger, "SN", ""):
                self.assertIsNone(logger.locate())
        post.assert_not_called()


class MotionAndRetentionTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.executescript(logger.SCHEMA)
        self.addCleanup(self.conn.close)
        self.now = int(time.time())

    def frame(self, age, odo, raw=None):
        self.conn.execute("INSERT INTO telemetry(ts, odo_guess, raw) VALUES (?,?,?)",
                          (self.now - age, odo, raw))

    def test_moving_means_speed_or_an_advancing_odometer_in_a_fresh_frame(self):
        self.assertFalse(logger._loc_moving(self.conn))                   # no frames at all
        self.frame(200, 1000); self.frame(5, 1000)
        self.assertFalse(logger._loc_moving(self.conn))                   # parked: odometer flat
        self.frame(2, 1003)
        self.assertTrue(logger._loc_moving(self.conn))                    # odometer advanced
        self.conn.execute("DELETE FROM telemetry"); self.frame(5, 1000, "ab")
        with patch.object(logger, "decode", return_value={"speed": 12}):
            self.assertTrue(logger._loc_moving(self.conn))                # speed reading wins
        with patch.object(logger, "decode", side_effect=ValueError("bad blob")):
            self.assertFalse(logger._loc_moving(self.conn))               # malformed blob = no reading

    def test_a_stale_frame_is_never_motion(self):
        self.frame(600, 1000); self.frame(400, 1050)
        self.assertFalse(logger._loc_moving(self.conn))

    def test_purge_drops_only_what_is_older_than_the_keep_window(self):
        self.conn.executescript(logger.LOC_SCHEMA)
        day = 86400
        for age_days in (200, 91, 89, 1):
            self.conn.execute("INSERT INTO positions(ts, lat, lng, moving) VALUES (?,?,?,0)",
                              (self.now - age_days * day, 1.0, 2.0))
        with patch.object(logger, "LOC_KEEP", 90):
            logger._loc_purge(self.conn)
        left = [r[0] for r in self.conn.execute("SELECT ts FROM positions ORDER BY ts")]
        self.assertEqual(left, [self.now - 89 * day, self.now - 1 * day])
        with patch.object(logger, "LOC_KEEP", 0):                         # 0 = keep forever
            self.conn.execute("INSERT INTO positions(ts, lat, lng, moving) VALUES (1, 1.0, 2.0, 0)")
            logger._loc_purge(self.conn)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM positions WHERE ts = 1").fetchone()[0], 1)

    def test_purge_without_a_positions_table_is_a_no_op(self):
        with patch.object(logger, "LOC_KEEP", 90):
            logger._loc_purge(self.conn)                                  # location was never on


class ServerHarness(unittest.TestCase):
    """A dashboard on a throwaway data dir; no tests of its own."""
    def setUp(self):
        self.data = tempfile.TemporaryDirectory()
        self.addCleanup(self.data.cleanup)
        for name, value in (("_DATA", self.data.name), ("DEMO", False),
                            ("DB", os.path.join(self.data.name, "carlinko.db"))):
            p = patch.object(server, name, value)
            p.start()
            self.addCleanup(p.stop)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.H)
        thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.base = "http://127.0.0.1:%d" % self.httpd.server_port
        server._ensure_db()
        self.now = int(time.time())

    def creds(self, **kw):
        with open(os.path.join(self.data.name, "creds.json"), "w") as f:
            json.dump(kw, f)

    def seed(self, rows):
        conn = sqlite3.connect(server.DB)
        conn.executescript(logger.LOC_SCHEMA)
        conn.executemany("INSERT INTO positions(ts, lat, lng, moving) VALUES (?,?,?,?)", rows)
        conn.commit()
        conn.close()

    def get(self, path, cookie=None):
        req = urllib.request.Request(self.base + path, headers={"Cookie": cookie} if cookie else {})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            self.addCleanup(e.close)
            return e.code, None

    def post(self, path, body=None, cookie=None, ctype="application/json", raw=None):
        data = raw if raw is not None else json.dumps(body).encode()
        headers = {"Content-Type": ctype} if ctype else {}
        if cookie:
            headers["Cookie"] = cookie
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            self.addCleanup(e.close)
            try:
                return e.code, json.loads(e.read().decode() or "null")
            except ValueError:
                return e.code, None

    def settings_file(self):
        return os.path.join(self.data.name, "location.json")


class ServerTest(ServerHarness):
    def test_off_by_default_even_when_positions_exist(self):
        self.seed([(self.now - 10, 3.139, 101.6869, 1)])
        for creds in ({}, {"location": False}, {"location": "false"}, {"location": 0}):
            self.creds(**creds)
            _, loc = self.get("/api/location")
            self.assertFalse(loc["enabled"], creds)
            self.assertIsNone(loc["lat"], creds)
            _, route = self.get("/api/route?from=0&to=%d" % self.now)
            self.assertEqual(route, {"points": []}, creds)

    def test_demo_never_serves_a_position(self):
        self.creds(location=True)
        self.seed([(self.now - 10, 3.139, 101.6869, 1)])
        with patch.object(server, "DEMO", True):
            _, loc = self.get("/api/location")
        self.assertFalse(loc["enabled"])
        self.assertIsNone(loc["lat"])

    def test_latest_fix_and_age_and_since(self):
        self.creds(location=True)
        _, none_yet = self.get("/api/location")                           # logger not restarted yet: no table
        self.assertEqual((none_yet["enabled"], none_yet["lat"]), (True, None))
        self.seed([(self.now - 7200, 1.0, 2.0, 1), (self.now - 60, 3.139, 101.6869, 0)])
        _, loc = self.get("/api/location")
        self.assertEqual((loc["lat"], loc["lng"], loc["moving"]), (3.139, 101.6869, False))
        self.assertIn(loc["age_s"], range(60, 70))
        self.assertEqual(loc["since"], self.now - 7200)

    def test_route_is_one_outing_padded_ordered_and_bounded(self):
        self.creds(location=True)
        t = self.now - 10 * 86400
        self.seed([(t - 1000, 9.0, 9.0, 0), (t - 200, 1.0, 1.0, 1), (t, 2.0, 2.0, 1),
                   (t + 600, 3.0, 3.0, 1), (t + 900, 4.0, 4.0, 0), (t + 5000, 9.0, 9.0, 0)])
        _, route = self.get("/api/route?from=%d&to=%d" % (t, t + 600))
        self.assertEqual([p[0] for p in route["points"]], [1.0, 2.0, 3.0, 4.0])   # +-300 s pad
        self.assertEqual(route["points"][0], [1.0, 1.0, t - 200])
        _, wide = self.get("/api/route?from=%d&to=%d" % (t, t + 4 * 86400))       # beyond the 3-day cap
        self.assertEqual(wide, {"points": []})
        _, backwards = self.get("/api/route?from=%d&to=%d" % (t + 5, t))
        self.assertEqual(backwards, {"points": []})
        _, huge = self.get("/api/route?from=0&to=%d" % (2 ** 62))             # must not overflow SQLite
        self.assertEqual(huge, {"points": []})
        status, _ = self.get("/api/route?from=abc&to=1")
        self.assertEqual(status, 400)

    def test_both_endpoints_need_a_session_when_the_dashboard_is_gated(self):
        self.creds(location=True)
        self.seed([(self.now - 10, 3.139, 101.6869, 1)])
        server.set_dashboard_password("test-password")
        for path in ("/api/location", "/api/route?from=0&to=%d" % self.now):
            self.assertEqual(self.get(path)[0], 401, path)
            self.assertEqual(self.get(path, "sid=" + server.make_session())[0], 200, path)


class SettingsTest(unittest.TestCase):
    """location_settings.py: where the switch lives, and why it is not creds.json."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.d = self.dir.name

    def write(self, name, text):
        with open(os.path.join(self.d, name), "w") as f:
            f.write(text)

    def test_the_file_beats_creds_and_creds_is_only_the_default(self):
        self.assertFalse(location_settings.enabled(self.d))                      # nothing anywhere: off
        self.write("creds.json", json.dumps({"location": True}))
        self.assertTrue(location_settings.enabled(self.d))                       # creds default
        self.write("location.json", json.dumps({"enabled": False}))
        self.assertFalse(location_settings.enabled(self.d))                      # the owner's switch wins
        self.write("creds.json", json.dumps({"location": False}))
        self.write("location.json", json.dumps({"enabled": True}))
        self.assertTrue(location_settings.enabled(self.d))
        self.assertTrue(location_settings.enabled(self.d, {"location": False}))  # creds passed in: still the file

    def test_a_garbage_file_is_ignored_and_an_unreadable_value_is_off(self):
        self.write("creds.json", json.dumps({"location": True}))
        for junk in ("", "{", "[]", "null", '"on"', "{}", '{"other": 1}'):
            self.write("location.json", junk)
            self.assertTrue(location_settings.enabled(self.d), junk)             # falls back to creds
        self.write("location.json", json.dumps({"enabled": "maybe"}))
        self.assertFalse(location_settings.enabled(self.d))                      # never read as the creds default
        self.write("location.json", json.dumps({"enabled": "true"}))
        self.assertTrue(location_settings.enabled(self.d))

    def test_the_write_is_atomic_and_owner_only(self):
        location_settings.set_enabled(self.d, True)
        path = os.path.join(self.d, "location.json")
        self.assertEqual(json.load(open(path)), {"enabled": True})
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
        self.assertEqual([f for f in os.listdir(self.d) if f.endswith(".tmp")], [])
        with patch("os.replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                location_settings.set_enabled(self.d, False)
        self.assertEqual(json.load(open(path)), {"enabled": True})               # the old file is intact
        self.assertEqual([f for f in os.listdir(self.d) if f.endswith(".tmp")], [])

    def test_the_unsupported_marker_is_cleared_by_switching_on_only(self):
        self.assertFalse(location_settings.unsupported(self.d))
        location_settings.mark_unsupported(self.d, 1234.9)
        self.assertEqual(json.load(open(os.path.join(self.d, "location_state.json"))), {"unsupported_at": 1234})
        self.assertTrue(location_settings.unsupported(self.d))
        location_settings.set_enabled(self.d, False)                             # off keeps what the cloud said
        self.assertTrue(location_settings.unsupported(self.d))
        location_settings.set_enabled(self.d, True)                              # on asks again
        self.assertFalse(location_settings.unsupported(self.d))
        for junk in ("", "{", "[]", '{"unsupported_at": "x"}', '{"unsupported_at": true}', '{"unsupported_at": 0}'):
            self.write("location_state.json", junk)
            self.assertFalse(location_settings.unsupported(self.d), junk)

    def test_keep_days(self):
        for creds, want in (({}, 90), ({"location_keep_days": 30}, 30), ({"location_keep_days": "7"}, 7),
                            ({"location_keep_days": 0}, 0), ({"location_keep_days": -5}, 90),
                            ({"location_keep_days": "soon"}, 90), ({"location_keep_days": ""}, 90),
                            ({"location_keep_days": 10 ** 9}, 36500), (None, 90)):
            self.assertEqual(location_settings.keep_days(creds), want, creds)


class SwitchTest(ServerHarness):
    """The dashboard side of the switch: status values, the two POST routes, the capability."""

    def test_the_capability_is_advertised_on_or_off_but_never_in_demo(self):
        for creds in ({}, {"location": True}):
            self.creds(**creds)
            _, st = self.get("/api/status")
            self.assertIn("car_location", st["capabilities"], creds)
        self.assertEqual(st["capabilities"], list(server.CAPABILITIES))
        with patch.object(server, "DEMO", True):
            _, demo = self.get("/api/status")
        self.assertNotIn("car_location", demo["capabilities"])

    def test_get_reports_why_there_is_no_pin(self):
        _, d = self.get("/api/location")
        self.assertEqual((d["enabled"], d["status"], d["gated"], d["keep_days"]), (False, "off", False, 90))
        self.creds(location=True, location_keep_days=30)
        _, d = self.get("/api/location")
        self.assertEqual((d["enabled"], d["status"], d["keep_days"]), (True, "waiting", 30))   # no table yet
        self.seed([(self.now - 60, 3.139, 101.6869, 0)])
        self.assertEqual(self.get("/api/location")[1]["status"], "ok")
        location_settings.mark_unsupported(self.data.name, self.now)
        self.assertEqual(self.get("/api/location")[1]["status"], "unsupported")
        self.creds(location=False)
        self.assertEqual(self.get("/api/location")[1]["status"], "off")          # off wins over a stale marker
        server.set_dashboard_password("test-password")
        self.assertTrue(self.get("/api/location", "sid=" + server.make_session())[1]["gated"])

    def test_both_routes_need_a_session_when_gated(self):
        server.set_dashboard_password("test-password")
        sid = "sid=" + server.make_session()
        for path, body in (("/api/location/settings", {"enabled": True}), ("/api/location/erase", {})):
            self.assertEqual(self.post(path, body)[0], 401, path)
            self.assertEqual(self.post(path, body, sid)[0], 200, path)
        self.assertFalse(os.path.exists(self.settings_file()) and not location_settings.enabled(self.data.name))

    def test_bad_requests_are_400_and_change_nothing(self):
        for body, kw in (({"enabled": "yes"}, {}), ({"enabled": 1}, {}), ({}, {}), ([True], {}),
                         ({"enabled": True}, {"ctype": "text/plain"}), ({"enabled": True}, {"ctype": None}),
                         (None, {"raw": b"{"}), (None, {"raw": b"\xff\xfe"})):
            self.assertEqual(self.post("/api/location/settings", body, **kw), (400, {"error": "bad_request"}), (body, kw))
        self.assertEqual(self.post("/api/location/erase", {}, ctype="text/plain")[0], 400)
        self.assertEqual(self.post("/api/location/erase", None, raw=b"[1]")[0], 400)
        self.assertFalse(os.path.exists(self.settings_file()))

    def test_switching_an_open_dashboard_on_asks_first(self):
        self.assertEqual(self.post("/api/location/settings", {"enabled": True}), (409, {"error": "not_gated"}))
        self.assertEqual(self.post("/api/location/settings", {"enabled": True, "allow_open": "true"})[0], 409)
        self.assertFalse(os.path.exists(self.settings_file()))
        status, d = self.post("/api/location/settings", {"enabled": True, "allow_open": True})
        self.assertEqual(status, 200)
        self.assertEqual((d["ok"], d["enabled"], d["status"], d["gated"]), (True, True, "waiting", False))
        self.assertEqual(json.load(open(self.settings_file())), {"enabled": True})
        status, d = self.post("/api/location/settings", {"enabled": False})        # off never needs allow_open
        self.assertEqual((status, d["ok"], d["enabled"], d["status"]), (200, True, False, "off"))

    def test_a_gated_dashboard_switches_on_without_allow_open(self):
        server.set_dashboard_password("test-password")
        status, d = self.post("/api/location/settings", {"enabled": True}, "sid=" + server.make_session())
        self.assertEqual((status, d["enabled"], d["gated"]), (200, True, True))

    def test_the_switch_outlives_a_creds_rewrite(self):
        server.set_dashboard_password("test-password")
        sid = "sid=" + server.make_session()
        self.post("/api/location/settings", {"enabled": True}, sid)
        self.creds(location=False)                         # what railway_start.sh does to creds.json on every boot
        self.assertTrue(self.get("/api/location", sid)[1]["enabled"])
        self.creds(location=True)
        self.post("/api/location/settings", {"enabled": False}, sid)
        self.assertFalse(self.get("/api/location", sid)[1]["enabled"])

    def test_demo_refuses_both_and_stays_off(self):
        with patch.object(server, "DEMO", True):
            self.assertEqual(self.post("/api/location/settings", {"enabled": True}), (409, {"error": "demo"}))
            self.assertEqual(self.post("/api/location/erase", {}), (409, {"error": "demo"}))
            self.assertEqual(self.get("/api/location")[1]["status"], "off")
        self.assertFalse(os.path.exists(self.settings_file()))

    def test_erase_counts_what_it_deleted_and_works_with_location_off(self):
        self.assertEqual(self.post("/api/location/erase", {}), (200, {"ok": True, "deleted": 0}))   # no table at all
        self.seed([(self.now - 300, 1.0, 2.0, 1), (self.now - 200, 1.1, 2.1, 1), (self.now - 100, 1.2, 2.2, 0)])
        self.assertFalse(self.get("/api/location")[1]["enabled"])                  # location is off
        self.assertEqual(self.post("/api/location/erase", {}), (200, {"ok": True, "deleted": 3}))
        self.assertEqual(self.post("/api/location/erase", {}), (200, {"ok": True, "deleted": 0}))
        conn = sqlite3.connect(server.DB)
        self.assertEqual(conn.execute("select count(*) from positions").fetchone()[0], 0)
        conn.close()

    def test_a_lock_that_outlasts_the_wait_is_not_reported_as_zero(self):
        self.seed([(self.now - 100, 1.2, 2.2, 0)])
        with patch.object(server, "location_erase", side_effect=sqlite3.OperationalError("database is locked")):
            self.assertEqual(self.post("/api/location/erase", {}), (503, {"error": "busy"}))

    def test_switching_on_forgets_a_50052(self):
        self.creds(location=True)
        location_settings.mark_unsupported(self.data.name, self.now)
        self.assertEqual(self.get("/api/location")[1]["status"], "unsupported")
        self.post("/api/location/settings", {"enabled": True, "allow_open": True})
        self.assertEqual(self.get("/api/location")[1]["status"], "waiting")


class LoggerSwitchTest(unittest.TestCase):
    """The location thread follows the switch live: idle while off, lazy table, 50052 idles it."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.d = self.dir.name
        for name, value in (("_DATA", self.d), ("LOC_PARKED", 0)):
            p = patch.object(logger, name, value)
            p.start()
            self.addCleanup(p.stop)
        self.locate = MagicMock(return_value=(3.139, 101.6869))
        p = patch.object(logger, "locate", self.locate)
        p.start()
        self.addCleanup(p.stop)
        self.conn = sqlite3.connect(":memory:")
        self.conn.executescript(logger.SCHEMA)
        self.addCleanup(self.conn.close)
        self.t = 1_800_000_000.0
        self.out = io.StringIO()

    def tick(self, capture, dt=5):
        self.t += dt
        with contextlib.redirect_stdout(self.out):
            return logger._loc_tick(self.conn, capture, self.t)

    def has_table(self):
        return bool(self.conn.execute("select 1 from sqlite_master where name='positions'").fetchone())

    def test_the_decision_table(self):
        for on in (False, True):
            for blocked in (False, True):
                for running in (False, True):
                    want = (("run" if running else "start") if on and not blocked
                            else ("stop" if running else "idle"))
                    self.assertEqual(logger._loc_tick_action(on, blocked, running), want, (on, blocked, running))

    def test_off_does_nothing_then_on_starts_lazily_then_off_stops_at_once(self):
        cap = None
        for _ in range(3):
            cap = self.tick(cap)
        self.assertIsNone(cap)
        self.assertFalse(self.has_table())                                       # no table while off
        self.locate.assert_not_called()                                          # and no request
        location_settings.set_enabled(self.d, True)
        cap = self.tick(cap)
        self.assertIsNotNone(cap)
        self.assertTrue(self.has_table())                                        # created on switching on
        self.locate.assert_not_called()                                          # the start tick only arms it
        cap = self.tick(cap)
        self.assertEqual(self.locate.call_count, 1)                              # the owed parked fix
        self.assertEqual(self.conn.execute("select moving from positions").fetchall(), [(0,)])
        cap = self.tick(cap)
        self.assertEqual(self.locate.call_count, 1)                              # parked, nothing owed any more
        location_settings.set_enabled(self.d, False)
        cap = self.tick(cap)
        self.assertIsNone(cap)
        cap = self.tick(cap, dt=600)
        self.assertEqual(self.locate.call_count, 1)                              # nothing after off
        self.assertEqual(self.conn.execute("select count(*) from positions").fetchone()[0], 1)   # data kept

    def test_creds_alone_still_switches_it_on_as_the_default(self):
        with open(os.path.join(self.d, "creds.json"), "w") as f:
            json.dump({"location": True}, f)
        cap = self.tick(None)
        self.assertIsNotNone(cap)
        location_settings.set_enabled(self.d, False)                             # the dashboard switch beats it
        self.assertIsNone(self.tick(cap))

    def drive(self, cap, dt=60, km=10):
        """A tick while the car is driving: fresh frames with an advancing odometer, so a fix is due."""
        odo = self.conn.execute("select coalesce(max(odo_guess), 1000) from telemetry").fetchone()[0]
        self.conn.execute("insert or replace into telemetry(ts, odo_guess) values (?, ?)",
                          (int(self.t + dt) - 200, odo))
        self.conn.execute("insert or replace into telemetry(ts, odo_guess) values (?, ?)",
                          (int(self.t + dt) - 5, odo + km))
        return self.tick(cap, dt=dt)
    def stored(self):
        return self.conn.execute("select count(*) from positions").fetchone()[0]
    def test_a_car_that_never_had_a_fix_idles_after_three_50052s_in_a_row(self):
        location_settings.set_enabled(self.d, True)
        cap = self.tick(None)
        self.locate.return_value = "unsupported"
        for read in (1, 2):                                                      # the J5: it is asked three times...
            cap = self.tick(cap, dt=61)
            self.assertIsNotNone(cap, f"still trying after read {read}")
            self.assertFalse(location_settings.unsupported(self.d))
        cap = self.tick(cap, dt=61)                                              # ...and then goes quiet
        self.assertIsNone(cap)
        self.assertTrue(location_settings.unsupported(self.d))
        self.assertEqual(self.locate.call_count, 3)
        self.locate.reset_mock()
        for _ in range(4):
            cap = self.tick(cap, dt=120)
        self.assertIsNone(cap)
        self.locate.assert_not_called()                                          # idle although still switched on
        location_settings.set_enabled(self.d, False)
        location_settings.set_enabled(self.d, True)                              # the owner tries again
        self.locate.return_value = (3.139, 101.6869)
        cap = self.tick(cap)
        self.assertIsNotNone(cap)
        cap = self.tick(cap)
        self.assertEqual(self.locate.call_count, 1)
        self.assertEqual(self.stored(), 1)
    def test_a_good_read_before_the_third_50052_means_the_car_has_a_position(self):
        location_settings.set_enabled(self.d, True)
        cap = self.tick(None)
        self.locate.return_value = "unsupported"
        cap = self.tick(cap, dt=61)
        cap = self.tick(cap, dt=61)                                              # two misses...
        self.locate.return_value = (3.139, 101.6869)
        cap = self.tick(cap, dt=61)                                              # ...then a fix
        self.assertEqual(self.stored(), 1)
        self.locate.return_value = "unsupported"
        for _ in range(8):                                                       # never idle again
            cap = self.drive(cap)
        self.assertIsNotNone(cap)
        self.assertFalse(location_settings.unsupported(self.d))
    def test_a_50052_mid_drive_is_a_gap_not_the_end_of_location(self):
        # Seen on a Tiggo 7 in Malaysia: 5 in two days, the next read 20 s later always worked.
        location_settings.set_enabled(self.d, True)
        cap = self.tick(None)
        cap = self.tick(cap)                                                     # a fix is stored
        self.assertEqual(self.stored(), 1)
        self.locate.return_value = "unsupported"
        for _ in range(5):                                                       # more than LOC_GIVE_UP in a row
            cap = self.drive(cap)
            self.assertIsNotNone(cap)
        self.assertFalse(location_settings.unsupported(self.d))
        self.assertEqual(self.stored(), 1)                                       # nothing invented for the gap
        self.locate.return_value = (3.14, 101.69)
        cap = self.drive(cap)
        self.assertEqual(self.stored(), 2)                                       # and the drive carries on
        self.assertIn("no fix this time (50052)", self.out.getvalue())
    def test_the_log_never_carries_a_coordinate(self):
        location_settings.set_enabled(self.d, True)
        cap = self.tick(None)                                                    # on
        cap = self.tick(cap)                                                     # a fix is stored
        self.locate.return_value = "unsupported"
        cap = self.drive(cap)                                                    # the cloud says 50052 mid-drive
        self.locate.return_value = (3.139, 101.6869)
        cap = self.drive(cap)
        self.locate.return_value = (48.1, 11.5)                                  # then a fix that cannot be right
        cap = self.drive(cap)
        self.assertEqual(self.stored(), 2)
        out = self.out.getvalue()
        for needle in ("3.139", "101.68", "48.1", "11.5"):
            self.assertNotIn(needle, out)
        self.assertIn("50052", out)
        self.assertIn("dropped a fix", out)
    def test_a_fix_the_car_could_not_have_driven_to_is_dropped(self):
        location_settings.set_enabled(self.d, True)
        cap = self.tick(None)
        cap = self.tick(cap)                                                     # (3.139, 101.6869) stored
        self.locate.return_value = (48.1, 11.5)                                  # Europe, a minute later
        cap = self.drive(cap)
        self.assertEqual(self.stored(), 1)
        self.assertIn("dropped a fix", self.out.getvalue())
    def test_three_rejected_fixes_that_agree_win_because_the_car_did_move(self):
        location_settings.set_enabled(self.d, True)
        cap = self.tick(None)
        cap = self.tick(cap)
        self.locate.return_value = (5.9, 116.1)                                  # Kota Kinabalu, 1,600 km away
        cap = self.drive(cap)
        cap = self.drive(cap)
        self.assertEqual(self.stored(), 1)                                       # two agreeing rejects: not yet
        cap = self.drive(cap)
        self.assertEqual(self.stored(), 2)                                       # the third wins
        self.assertEqual(self.conn.execute("select lat from positions order by ts desc").fetchone()[0], 5.9)
        self.assertIn("agree on a new place", self.out.getvalue())
    def test_rejects_that_disagree_with_each_other_start_over(self):
        location_settings.set_enabled(self.d, True)
        cap = self.tick(None)
        cap = self.tick(cap)
        for fix in ((48.1, 11.5), (35.7, 139.7), (48.1, 11.5), (35.7, 139.7), (48.1, 11.5)):
            self.locate.return_value = fix
            cap = self.drive(cap)
        self.assertEqual(self.stored(), 1)                                       # never three alike in a row
    def test_a_longitude_one_digit_short_is_repaired_when_it_fits_the_last_fix(self):
        # The region repair is the first line; this is the other, for a region with no known box.
        location_settings.set_enabled(self.d, True)
        with patch.object(logger, "_loc_region_lng", lambda lng, region: lng):
            cap = self.tick(None)
            cap = self.tick(cap)
            self.locate.return_value = (3.139, 10.16869)                         # 101.6869 lost its first digit
            cap = self.drive(cap)
        self.assertEqual(self.stored(), 2)
        self.assertAlmostEqual(self.conn.execute("select lng from positions order by ts desc").fetchone()[0],
                               101.6869, places=3)
        self.assertIn("one digit short", self.out.getvalue())
class GateTest(unittest.TestCase):
    """The jump check on its own: the last good fix against a new one."""
    REF = (1_800_000_000, 3.139, 101.6869, 1000)         # ts, lat, lng, odometer
    def gate(self, p, dt=60, odo=1000, ref=None):
        ref = ref or self.REF
        return logger._loc_gate(ref, p, ref[0] + dt, odo)
    def test_the_first_fix_has_nothing_to_be_judged_against(self):
        self.assertEqual(logger._loc_gate(None, (48.1, 11.5), 1_800_000_000, None), ("ok", (48.1, 11.5)))
    def test_a_short_drive_passes(self):
        self.assertEqual(self.gate((3.15, 101.70), odo=1001), ("ok", (3.15, 101.70)))
    def test_a_jump_no_car_could_make_is_dropped(self):
        self.assertEqual(self.gate((48.1, 11.5)), ("drop", None))
    def test_the_odometer_caps_what_a_long_parked_gap_allows(self):
        # A week parked at 200 km/h allows 33,000 km; the odometer says it did not move, so 3 km at most.
        week = 7 * 86400
        self.assertEqual(self.gate((3.20, 101.69), dt=week, odo=1000)[0], "drop")        # ~6 km away
        self.assertEqual(self.gate((3.145, 101.69), dt=week, odo=1000)[0], "ok")         # ~1 km: GPS jitter
    def test_a_digit_short_longitude_is_repaired_even_after_a_long_gap(self):
        self.assertEqual(self.gate((3.139, 10.16869), dt=7 * 86400, odo=1000), ("repaired", (3.139, 101.6869)))
        # ...and with no odometer at all (the logger was down), where the allowance is huge:
        ref = (self.REF[0], self.REF[1], self.REF[2], None)
        verdict, fix = self.gate((3.139, 10.16869), dt=7 * 86400, odo=None, ref=ref)
        self.assertEqual((verdict, round(fix[1], 4)), ("repaired", 101.6869))
    def test_a_real_drive_near_longitude_zero_is_never_repaired(self):
        london = (1_800_000_000, 51.5, -0.12, 500)
        self.assertEqual(logger._loc_gate(london, (51.5, -0.012), london[0] + 1800, 520)[0], "ok")
    def test_the_allowance_is_speed_for_the_time_but_never_more_than_the_odometer(self):
        ref = self.REF
        self.assertAlmostEqual(logger._loc_allow_km(ref, ref[0] + 3600, None), 200 + logger.LOC_SLACK_KM)
        self.assertAlmostEqual(logger._loc_allow_km(ref, ref[0] + 3600, 1010), 11 + logger.LOC_SLACK_KM)
        self.assertAlmostEqual(logger._loc_allow_km(ref, ref[0] - 100, None), logger.LOC_SLACK_KM)   # a clock step
    def test_distance_is_great_circle(self):
        self.assertAlmostEqual(logger._loc_km((0, 0), (0, 1)), 111.2, delta=0.3)
        self.assertAlmostEqual(logger._loc_km((3.139, 101.6869), (3.139, 101.6869)), 0.0)
class IntervalFloorTest(unittest.TestCase):
    """The car uploads about every 30 s, so reading faster only repeats a fix and loads CarLinko."""
    def test_the_floors(self):
        self.assertEqual((logger.LOC_MIN_EVERY, logger.LOC_MIN_PARKED), (30, 300))
        self.assertGreaterEqual(logger.LOC_EVERY, 30)
        self.assertTrue(logger.LOC_PARKED == 0 or logger.LOC_PARKED >= 300)
    def test_a_lower_interval_is_raised_and_says_so(self):
        out = io.StringIO()
        with patch.dict(logger._C, {"location_interval": 10}), contextlib.redirect_stdout(out):
            self.assertEqual(logger._loc_int("location_interval", 30, logger.LOC_MIN_EVERY, 86400), 30)
        self.assertIn("location_interval=10 is below the minimum, using 30", out.getvalue())
    def test_a_value_in_range_is_left_alone_and_silent(self):
        out = io.StringIO()
        with patch.dict(logger._C, {"location_interval": 40}), contextlib.redirect_stdout(out):
            self.assertEqual(logger._loc_int("location_interval", 30, logger.LOC_MIN_EVERY, 86400), 40)
        self.assertEqual(out.getvalue(), "")
if __name__ == "__main__":
    unittest.main()

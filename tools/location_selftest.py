#!/usr/bin/env python3
"""Checks for the opt-in car location feature (#23): the logger's cached-position reader and the
server's two read-only views. Nothing here touches the network or the owner's real data."""
import atexit
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
        self.assertFalse(logger._loc_flag("false"))
        self.assertTrue(logger._loc_flag("true"))
        self.assertFalse(logger._loc_flag(None))


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


class ServerTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()

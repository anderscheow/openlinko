#!/usr/bin/env python3
"""A Google key that Google refuses must not pass for one that works: the log names the reason once, and
/api/trip stops saying "google" while the stations really come from OpenStreetMap. No network, no real key.
Run from the repo root:  python3 tools/google_key_selftest.py
"""
import io
import json
import os
import sys
import unittest
import urllib.error
from unittest.mock import patch
sys.path.insert(0, os.path.dirname(__file__))
import server
KEY = "AIzaSy-not-a-real-key"
URL = "https://places.googleapis.com/v1/places:searchText"
def refusal(code=403, status="PERMISSION_DENIED", reason=None, raw=None):
    """The HTTPError urllib raises when Google answers with an error body."""
    err = {"code": code, "message": "mentions %s" % KEY, "status": status}
    if reason:
        err["details"] = [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": reason}]
    body = raw if raw is not None else json.dumps({"error": err}).encode()
    return urllib.error.HTTPError(URL, code, "refused", {}, io.BytesIO(body))
class Answer:
    def __init__(self, payload):
        self.payload = payload
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        return False
    def read(self):
        return json.dumps(self.payload).encode()
class GoogleKeyHealth(unittest.TestCase):
    def setUp(self):
        server._g_health.update(ok=None, reason=None)
        keyed = patch.object(server, "_gkey", return_value=KEY)
        keyed.start()
        self.addCleanup(keyed.stop)
    def post(self, outcome):
        failing = isinstance(outcome, Exception)
        with patch.object(server.urllib.request, "urlopen", side_effect=outcome if failing else None,
                          return_value=None if failing else Answer(outcome)):
            try:
                return server._g_post(URL, {"textQuery": "klcc"}, "places.location")
            except urllib.error.HTTPError as e:
                e.close()
                raise
    def test_before_any_call_a_keyed_server_reports_google(self):
        self.assertEqual(server._trip_source(), "google")
        self.assertIsNone(server._g_error())
    def test_without_a_key_it_is_osm_whatever_happened_before(self):
        server._g_health.update(ok=True, reason=None)
        with patch.object(server, "_gkey", return_value=None):
            self.assertEqual(server._trip_source(), "osm")
            self.assertIsNone(server._g_error())
    def test_a_refused_call_raises_and_turns_the_source_to_osm(self):
        with self.assertRaises(urllib.error.HTTPError), self.assertLogs(server.LOG, "WARNING"):
            self.post(refusal(reason="API_KEY_IP_ADDRESS_BLOCKED"))
        self.assertEqual(server._trip_source(), "osm")
        self.assertEqual(server._g_error(), "API_KEY_IP_ADDRESS_BLOCKED")
    def test_the_reason_falls_back_to_the_status_then_the_http_code(self):
        for outcome, want in ((refusal(status="PERMISSION_DENIED"), "PERMISSION_DENIED"),
                              (refusal(code=502, status="", raw=b"<html>bad gateway</html>"), "HTTP 502"),
                              (refusal(code=429, status="", raw=b"{}"), "HTTP 429")):
            with self.subTest(want=want), self.assertRaises(urllib.error.HTTPError), self.assertLogs(server.LOG, "WARNING"):
                self.post(outcome)
            self.assertEqual(server._g_error(), want)
    def test_a_network_failure_is_named_by_its_type(self):
        with self.assertRaises(OSError), self.assertLogs(server.LOG, "WARNING"):
            self.post(urllib.error.URLError("no route"))
        self.assertEqual(server._g_error(), "URLError")
    def test_the_log_never_carries_the_key_or_google_s_message(self):
        with self.assertRaises(urllib.error.HTTPError), self.assertLogs(server.LOG, "WARNING") as logs:
            self.post(refusal(reason="API_KEY_HTTP_REFERRER_BLOCKED"))
        text = "\n".join(logs.output)
        self.assertIn("API_KEY_HTTP_REFERRER_BLOCKED", text)
        self.assertNotIn(KEY, text)
        self.assertNotIn("mentions", text)
    def test_the_same_refusal_is_logged_once_not_per_request(self):
        with self.assertLogs(server.LOG, "WARNING") as logs:
            for _ in range(3):
                with self.assertRaises(urllib.error.HTTPError):
                    self.post(refusal(reason="API_KEY_SERVICE_BLOCKED"))
        self.assertEqual(len(logs.output), 1)
    def test_a_different_refusal_is_logged_again(self):
        with self.assertLogs(server.LOG, "WARNING") as logs:
            for reason in ("API_KEY_SERVICE_BLOCKED", "API_KEY_IP_ADDRESS_BLOCKED"):
                with self.assertRaises(urllib.error.HTTPError):
                    self.post(refusal(reason=reason))
        self.assertEqual(len(logs.output), 2)
    def test_an_answer_after_a_refusal_restores_google_and_says_so(self):
        with self.assertRaises(urllib.error.HTTPError), self.assertLogs(server.LOG, "WARNING"):
            self.post(refusal(reason="API_KEY_IP_ADDRESS_BLOCKED"))
        with self.assertLogs(server.LOG, "INFO") as logs:
            self.assertEqual(self.post({"places": []}), {"places": []})
        self.assertEqual(server._trip_source(), "google")
        self.assertIsNone(server._g_error())
        self.assertIn("answering again", "\n".join(logs.output))
    def test_an_answer_with_no_places_is_still_an_answer(self):
        self.post({})
        self.assertEqual(server._trip_source(), "google")
if __name__ == "__main__":
    unittest.main()

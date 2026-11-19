#!/usr/bin/env python3
"""Place search and charger lookup: worldwide, ranked around a point, and honest about an outage."""
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))
import server

PHOTON = "https://photon.komoot.io/api/"
NOMINATIM = "https://nominatim.openstreetmap.org/search"


def feature(name, lat, lon, country="Malaysia", code="MY", **props):
    properties = {"name": name, "country": country, "countrycode": code, "city": "Kuala Lumpur"}
    properties.update(props)
    return {"geometry": {"coordinates": [lon, lat]}, "properties": properties}


class Calls:
    """Stands in for `_http_get`: answers by URL and remembers what it was asked."""

    def __init__(self, photon=None, nominatim=None):
        self.photon, self.nominatim, self.asked = photon, nominatim, []

    def __call__(self, url, params=None, timeout=25):
        self.asked.append((url, dict(params or {})))
        if url == PHOTON:
            if isinstance(self.photon, Exception):
                raise self.photon
            return {"features": self.photon or []}
        if url == NOMINATIM:
            if isinstance(self.nominatim, Exception):
                raise self.nominatim
            return self.nominatim or []
        raise AssertionError("unexpected " + url)

    def params(self, url):
        return [p for u, p in self.asked if u == url]


class SuggestTest(unittest.TestCase):
    def setUp(self):
        for patcher in (patch.object(server, "_gkey", return_value=None),
                        patch.dict(os.environ, {}, clear=False)):
            patcher.start()
            self.addCleanup(patcher.stop)
        os.environ.pop("GEOCODE_COUNTRIES", None)

    def test_a_mall_in_malaysia_is_found_and_says_where_it_is(self):
        http = Calls(photon=[feature("Pavilion Bukit Jalil", 3.0553, 101.6983)])
        with patch.object(server, "_http_get", http):
            out = server._suggest("Pavilion Bukit Jalil")
        self.assertEqual(out[0]["name"], "Pavilion Bukit Jalil, Kuala Lumpur, Malaysia")
        self.assertAlmostEqual(out[0]["lat"], 3.0553)
        self.assertNotIn("bbox", http.params(PHOTON)[0], "no Indonesia-shaped box any more")

    def test_results_from_both_countries_stay(self):
        http = Calls(photon=[feature("Grand Indonesia", -6.19, 106.82, "Indonesia", "ID", city="Jakarta"),
                             feature("Suria KLCC", 3.1579, 101.7116)])
        with patch.object(server, "_http_get", http):
            names = [r["name"] for r in server._suggest("grand")]
        self.assertEqual(len(names), 2)
        self.assertTrue(any(n.endswith("Indonesia") for n in names))
        self.assertTrue(any(n.endswith("Malaysia") for n in names))

    def test_an_address_without_a_name_is_its_house_number_and_street(self):
        http = Calls(photon=[feature("", 3.16, 101.71, street="Jalan Ampang", housenumber="12")])
        with patch.object(server, "_http_get", http):
            out = server._suggest("12 jalan ampang")
        self.assertEqual(out[0]["name"], "12 Jalan Ampang, Kuala Lumpur, Malaysia")

    def test_a_repeated_part_is_said_once(self):
        http = Calls(photon=[feature("Kuala Lumpur", 3.14, 101.69, state="Kuala Lumpur")])
        with patch.object(server, "_http_get", http):
            out = server._suggest("kuala lumpur")
        self.assertEqual(out[0]["name"], "Kuala Lumpur, Malaysia")

    def test_the_point_to_rank_around_reaches_both_services(self):
        http = Calls(photon=[feature("Starbucks", 3.1, 101.7)], nominatim=[])
        with patch.object(server, "_http_get", http):
            server._suggest("starbucks", near=(3.139, 101.687))
        self.assertEqual((http.params(PHOTON)[0]["lat"], http.params(PHOTON)[0]["lon"]), (3.139, 101.687))
        viewbox = http.params(NOMINATIM)[0]["viewbox"].split(",")
        self.assertAlmostEqual(float(viewbox[0]), 101.687 - 1.5)
        self.assertNotIn("bounded", http.params(NOMINATIM)[0], "a preference, not a fence")

    def test_no_point_means_no_ranking_parameters(self):
        http = Calls(photon=[feature("Starbucks", 3.1, 101.7)], nominatim=[])
        with patch.object(server, "_http_get", http):
            server._suggest("starbucks")
        self.assertNotIn("lat", http.params(PHOTON)[0])
        self.assertNotIn("viewbox", http.params(NOMINATIM)[0])

    def test_nominatim_is_not_asked_when_photon_filled_the_list(self):
        http = Calls(photon=[feature("Place %d" % i, 3 + i / 100, 101.7) for i in range(6)])
        with patch.object(server, "_http_get", http):
            self.assertEqual(len(server._suggest("place")), 6)
        self.assertEqual(http.params(NOMINATIM), [])

    def test_nominatim_tops_up_a_short_list_and_is_not_limited_to_a_country(self):
        http = Calls(photon=[feature("A", 3.0, 101.0)],
                     nominatim=[{"display_name": "B, Selangor, Malaysia", "lat": "3.5", "lon": "101.5"}])
        with patch.object(server, "_http_get", http):
            out = server._suggest("something")
        self.assertEqual([r["name"] for r in out], ["A, Kuala Lumpur, Malaysia", "B, Selangor, Malaysia"])
        self.assertEqual(http.params(NOMINATIM)[0]["limit"], 5)
        self.assertNotIn("countrycodes", http.params(NOMINATIM)[0])

    def test_nominatim_answers_when_photon_is_down(self):
        http = Calls(photon=OSError("down"),
                     nominatim=[{"display_name": "B, Malaysia", "lat": "3.5", "lon": "101.5"}])
        with patch.object(server, "_http_get", http):
            self.assertEqual(server._suggest("something")[0]["name"], "B, Malaysia")

    def test_keeping_to_some_countries_is_opt_in(self):
        http = Calls(photon=[feature("Grand Indonesia", -6.19, 106.82, "Indonesia", "ID"),
                             feature("Suria KLCC", 3.1579, 101.7116)], nominatim=[])
        with patch.dict(os.environ, {"GEOCODE_COUNTRIES": "id"}), patch.object(server, "_http_get", http):
            names = [r["name"] for r in server._suggest("anything")]
        self.assertEqual(len(names), 1)
        self.assertIn("Indonesia", names[0])
        self.assertEqual(http.params(NOMINATIM)[0]["countrycodes"], "id")

    def test_one_place_for_a_typed_name_is_not_limited_to_indonesia(self):
        http = Calls(nominatim=[{"display_name": "Suria KLCC, Kuala Lumpur", "lat": "3.1579", "lon": "101.7116"}])
        with patch.object(server, "_http_get", http), patch.dict(server._trip_cache, {}, clear=True):
            lat, lon, name = server._geocode("Suria KLCC")
        self.assertEqual((lat, lon), (3.1579, 101.7116))
        self.assertNotIn("countrycodes", http.params(NOMINATIM)[0])

    def test_a_bad_point_is_no_point(self):
        self.assertIsNone(server._near("x", "101"))
        self.assertIsNone(server._near("95", "101"))
        self.assertEqual(server._near("3.1", "101.7"), (3.1, 101.7))


class GoogleSuggestTest(unittest.TestCase):
    def test_no_country_is_forced_and_a_point_biases_the_search(self):
        sent = {}

        def post(url, body, mask):
            sent.update(body)
            return {"places": []}

        with patch.object(server, "_g_post", post), patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GEOCODE_REGION", None)
            server._g_suggest("pavilion", 6, (3.139, 101.687))
        self.assertNotIn("regionCode", sent)
        self.assertEqual(sent["locationBias"]["circle"]["center"], {"latitude": 3.139, "longitude": 101.687})

    def test_a_region_is_opt_in(self):
        sent = {}
        with patch.object(server, "_g_post", lambda u, b, m: sent.update(b) or {"places": []}), \
                patch.dict(os.environ, {"GEOCODE_REGION": "MY"}):
            server._g_suggest("pavilion")
        self.assertEqual(sent["regionCode"], "MY")
        self.assertNotIn("locationBias", sent)


class ChargersTest(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(server, "_gkey", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)

    @staticmethod
    def overpass(elements):
        return {"elements": elements}

    def test_a_site_mapped_as_an_area_is_a_charger_too(self):
        els = [{"type": "node", "lat": 3.10, "lon": 101.60, "tags": {"name": "Gentari Mid Valley"}},
               {"type": "way", "center": {"lat": 3.12, "lon": 101.61}, "tags": {"operator": "ChargEV"}},
               {"type": "way", "tags": {"name": "no centre, no place"}}]
        with patch.object(server, "_http_post", lambda url, data, timeout=40: self.overpass(els)):
            out = server._spklu_list(3.139, 101.687, 12000)
        self.assertEqual([c["name"] for c in out], ["Gentari Mid Valley", "ChargEV"])
        self.assertEqual((out[1]["lat"], out[1]["lon"]), (3.12, 101.61))

    def test_the_query_asks_for_areas_and_not_only_points(self):
        asked = []
        with patch.object(server, "_http_post",
                          lambda url, data, timeout=40: asked.append(data["data"]) or self.overpass([])):
            server._spklu_list(3.139, 101.687, 12000)
        self.assertIn("nwr[", asked[0])
        self.assertIn("out center", asked[0])

    def test_a_brand_names_a_charger_that_has_no_name(self):
        els = [{"type": "node", "lat": 3.1, "lon": 101.6, "tags": {"brand": "Shell Recharge"}},
               {"type": "node", "lat": 3.2, "lon": 101.6, "tags": {}}]
        with patch.object(server, "_http_post", lambda url, data, timeout=40: self.overpass(els)):
            names = [c["name"] for c in server._spklu_list(3.139, 101.687)]
        self.assertEqual(names, ["Shell Recharge", "SPKLU"])

    def test_the_next_instance_answers_when_the_first_is_down(self):
        asked = []

        def post(url, data, timeout=40):
            asked.append(url)
            if url == server._OVERPASS[0]:
                raise OSError("502 Bad Gateway")
            return self.overpass([{"type": "node", "lat": 3.1, "lon": 101.6, "tags": {"name": "X"}}])

        with patch.object(server, "_http_post", post):
            out = server._spklu_list(3.139, 101.687, strict=True)
        self.assertEqual([c["name"] for c in out], ["X"])
        self.assertEqual(asked[:2], list(server._OVERPASS[:2]))

    def test_a_timed_out_partial_answer_is_a_failure(self):
        def post(url, data, timeout=40):
            if url == server._OVERPASS[0]:
                return {"elements": [], "remark": "runtime error: Query timed out in \"query\" at line 1"}
            return self.overpass([{"type": "node", "lat": 3.1, "lon": 101.6, "tags": {"name": "X"}}])

        with patch.object(server, "_http_post", post):
            self.assertEqual(len(server._spklu_list(3.139, 101.687, strict=True)), 1)

    def test_an_outage_is_an_error_when_the_list_must_be_honest(self):
        with patch.object(server, "_http_post", side_effect=OSError("502")):
            with self.assertRaises(RuntimeError):
                server._spklu_list(3.139, 101.687, strict=True)

    def test_an_outage_is_no_candidates_where_a_plan_can_do_without(self):
        with patch.object(server, "_http_post", side_effect=OSError("502")):
            self.assertEqual(server._spklu_list(3.139, 101.687), [])
            self.assertIsNone(server._nearest_spklu(3.139, 101.687))

    def test_the_nearest_charger_can_be_an_area(self):
        els = [{"type": "node", "lat": 3.30, "lon": 101.7, "tags": {"name": "far"}},
               {"type": "way", "center": {"lat": 3.14, "lon": 101.69}, "tags": {"name": "near"}}]
        with patch.object(server, "_http_post", lambda url, data, timeout=40: self.overpass(els)):
            best = server._nearest_spklu(3.139, 101.687)
        self.assertEqual(best[1], "near")


class HttpTest(unittest.TestCase):
    def setUp(self):
        self.data = tempfile.TemporaryDirectory()
        self.addCleanup(self.data.cleanup)
        for patcher in (patch.object(server, "_DATA", self.data.name), patch.object(server, "DEMO", False),
                        patch.object(server, "_gkey", return_value=None)):
            patcher.start()
            self.addCleanup(patcher.stop)
        server._trip_cache.clear()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.H)
        thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.base = "http://127.0.0.1:%d" % self.httpd.server_port

    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=10) as response:
            return json.load(response)

    def test_geocode_passes_the_point_to_rank_around(self):
        seen = {}

        def suggest(q, limit=6, near=None):
            seen.update(q=q, near=near)
            return []

        with patch.object(server, "_suggest", suggest):
            self.get("/api/geocode?q=starbucks&lat=3.1&lon=101.7")
            self.assertEqual(seen, {"q": "starbucks", "near": (3.1, 101.7)})
            self.get("/api/geocode?q=starbucks")
            self.assertIsNone(seen["near"], "older apps send no point")

    def test_an_empty_charger_list_is_not_remembered(self):
        calls = []

        def spklu(lat, lon, r=35000, strict=False):
            calls.append(strict)
            return []

        with patch.object(server, "_spklu_list", spklu):
            self.assertEqual(self.get("/api/spklu?lat=3.139&lon=101.687"), [])
            self.assertEqual(self.get("/api/spklu?lat=3.139&lon=101.687"), [])
        self.assertEqual(calls, [True, True])

    def test_chargers_are_remembered_for_a_while(self):
        calls = []

        def spklu(lat, lon, r=35000, strict=False):
            calls.append(1)
            return [{"name": "X", "lat": 3.14, "lon": 101.69}]

        with patch.object(server, "_spklu_list", spklu):
            self.get("/api/spklu?lat=3.139&lon=101.687")
            self.get("/api/spklu?lat=3.139&lon=101.687")
        self.assertEqual(len(calls), 1)

    def test_an_outage_reaches_the_app_as_an_error_not_as_no_chargers(self):
        with patch.object(server, "_spklu_list", side_effect=RuntimeError("Overpass unavailable")):
            body = self.get("/api/spklu?lat=3.139&lon=101.687")
        self.assertIsInstance(body, dict)
        self.assertIn("Overpass unavailable", body["error"])
        self.assertEqual(server._trip_cache, {}, "and the failure is not cached")


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""The `control` log line says how a command was framed and what came back, without vendor access.

A refusal (`...44`, a bare `__7404`) reads differently for an AES frame, a plain 74xx and an init
command, and the gateway reply alone does not say which one went out. The line also must not carry
the device serial the reply is prefixed with, or the value of a reply field it does not know.
"""

import json
import os
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(__file__))
import auth
import server

TIGGO = {"vehicle_id": "V1", "device_sn": "SN-SECRET", "user_id": "42",
         "vehicle": {"model": "TIGGO 7 CSH", "vin": "LVVDB11B0TD000001"}}
OTHER = {**TIGGO, "vehicle": {"model": "Some Other Car", "vin": "LVVDB11B0TD000001"}}


class ControlLogTest(unittest.TestCase):
    def setUp(self):
        for target, kwargs in ((server, {"_read_token": {"return_value": "tok"}}),
                               (auth, {"api_base": {"return_value": "https://example.invalid"}})):
            for name, opts in kwargs.items():
                p = patch.object(target, name, **opts)
                p.start()
                self.addCleanup(p.stop)

    def fire(self, op, reply, creds=TIGGO):
        """Send `op`, return (log line, the `data` the POST carried)."""
        with patch.object(server, "_creds", return_value=creds), \
             patch("requests.post", return_value=Mock(json=Mock(return_value=reply))) as post, \
             self.assertLogs(server.LOG, "INFO") as logs:
            server.send_control(op)
        sent = post.call_args.kwargs["data"]
        return logs.output[-1], json.loads(sent)["data"]

    def test_frame_kind_names_each_way_a_command_can_leave(self):
        self.assertEqual(server._frame_kind("741001", "66abcdef"), "enc")
        self.assertEqual(server._frame_kind("741001", "741001"), "plain")
        for init in ("2301", "24", "77"):
            self.assertEqual(server._frame_kind(init, init), "init")

    def test_verified_model_logs_enc_and_sends_the_aes_frame(self):
        line, sent = self.fire("741001", {"code": "0000", "msg": "OK", "data": "SN-SECRET__74100144"})
        self.assertIn("frame=enc", line)
        self.assertTrue(sent.startswith("66") and sent != "741001")
        self.assertIn("reply=74100144", line)

    def test_unverified_model_logs_plain(self):
        line, sent = self.fire("741001", {"code": "0000", "msg": "OK", "data": "SN-SECRET__7404"},
                               creds=OTHER)
        self.assertIn("frame=plain", line)
        self.assertEqual(sent, "741001")

    def test_init_command_logs_init(self):
        line, sent = self.fire("77", {"code": "0000", "msg": "OK", "data": "SN-SECRET__77" + "00" * 23})
        self.assertIn("frame=init", line)
        self.assertEqual(sent, "77")

    def test_the_device_serial_never_reaches_the_log(self):
        line, _ = self.fire("741001", {"code": "0000", "msg": "OK", "data": "SN-SECRET__74100144"})
        self.assertNotIn("SN-SECRET", line)

    def test_a_state_frame_sized_reply_is_logged_whole(self):
        payload = "AB" * 73                                     # 73 bytes: past the old 48 and 128 cuts
        line, _ = self.fire("77", {"code": "0000", "msg": "OK", "data": "SN-SECRET__" + payload})
        self.assertIn("reply=" + payload + " ", line)

    def test_a_runaway_reply_is_still_bounded(self):
        line, _ = self.fire("77", {"code": "0000", "msg": "OK", "data": "SN-SECRET__" + "AB" * 2000})
        self.assertLess(len(line), 800)

    def test_an_unknown_reply_field_is_named_but_its_value_is_not_logged(self):
        line, _ = self.fire("741001", {"code": "0000", "msg": "OK", "data": "SN-SECRET__74100100",
                                       "requestId": "do-not-log-me"})
        self.assertIn("extra=requestId", line)
        self.assertNotIn("do-not-log-me", line)

    def test_a_plain_three_field_reply_adds_no_extra_marker(self):
        line, _ = self.fire("741001", {"code": "0000", "msg": "OK", "data": "SN-SECRET__74100100"})
        self.assertNotIn("extra=", line)


if __name__ == "__main__":
    unittest.main()

"""Stored, opt-in Voltmoss push bindings. Delivery lives in the dispatcher.

The dashboard never receives an FCM installation ID. It stores only the relay's
opaque installation ID and a sender secret for that one destination.
"""

import hashlib
import json
import os
import re
import sqlite3
import time
from contextlib import closing
from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import charge_reminders


# charge_started arrived after the binding contract shipped, so a phone only names it once
# /api/status advertises push_charge_started: an older dashboard refuses the whole binding.
KINDS = frozenset((
    "charge_started", "charge_complete", "charge_stopped", "soc_below", "left_unlocked",
    "panel_open", "tyre_pressure", "volt12_low", "service_due",
))
THRESHOLDS = {"charge_complete": (80, 90, 100), "soc_below": (10, 20, 30)}
LOCALES = frozenset(("en", "ms", "id", "zh"))
_ID = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
_SECRET = re.compile(r"^[0-9a-fA-F]{64}$")


def valid_id(installation_id):
    return isinstance(installation_id, str) and bool(_ID.fullmatch(installation_id))


FIELDS = frozenset(("sender_secret", "rules", "locale", "service", "plus", "time_zone"))


def validate(installation_id, body):
    """Return a small canonical binding or raise ValueError before any write."""
    if not valid_id(installation_id):
        raise ValueError("invalid installation ID")
    # charge_activity is optional and named only once /api/status lists push_charge_activity:
    # true asks the dispatcher to keep the phone's charging Live Activity current.
    # charge_reminders is optional and named only once it lists push_charge_reminders: when to remind
    # the phone to unplug after a charge. Omitted, not null, when the phone wants none.
    if not isinstance(body, dict) or set(body) - {"charge_activity", "charge_reminders"} != FIELDS:
        raise ValueError("invalid binding fields")
    if body.get("charge_activity", True) is not True:
        raise ValueError("invalid charge activity")
    reminders = charge_reminders.validate(body["charge_reminders"]) if "charge_reminders" in body else None
    time_zone = body["time_zone"]
    if (not isinstance(time_zone, str) or len(time_zone) > 64 or
            not re.fullmatch(r"[A-Za-z0-9_+\-/]+", time_zone)):
        raise ValueError("invalid time zone")
    try:
        ZoneInfo(time_zone)
    except (ZoneInfoNotFoundError, ValueError) as e:
        raise ValueError("invalid time zone") from e
    secret = body["sender_secret"]
    if not isinstance(secret, str) or not _SECRET.fullmatch(secret):
        raise ValueError("invalid sender secret")
    locale = body["locale"]
    if not isinstance(locale, str) or locale not in LOCALES:
        raise ValueError("invalid locale")
    if not isinstance(body["plus"], bool):
        raise ValueError("invalid entitlement flag")
    rule_set = body["rules"]
    if (not isinstance(rule_set, dict) or set(rule_set) != {"v", "rules"} or
            type(rule_set["v"]) is not int or rule_set["v"] != 1):
        raise ValueError("invalid rule version")
    rules = rule_set["rules"]
    if not isinstance(rules, dict) or not set(rules) <= KINDS:
        raise ValueError("invalid rules")
    for kind, rule in rules.items():
        if not isinstance(rule, dict) or set(rule) - {"on", "t"} or rule.get("on") is not True:
            raise ValueError("invalid rule")
        threshold = rule.get("t")
        if threshold is not None and (kind not in THRESHOLDS or
                                      type(threshold) not in (int, float) or
                                      threshold not in THRESHOLDS[kind]):
            raise ValueError("invalid threshold")
    service = body["service"]
    if not isinstance(service, dict) or set(service) != {"last_odo", "last_date", "interval_km", "interval_months"}:
        raise ValueError("invalid service settings")
    for name in ("last_odo", "interval_km", "interval_months"):
        value = service[name]
        ceiling = 1200 if name == "interval_months" else 1000000
        if value is not None and (type(value) is not int or not 0 <= value <= ceiling):
            raise ValueError("invalid service settings")
    last_date = service["last_date"]
    if last_date is not None:
        if not isinstance(last_date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", last_date):
            raise ValueError("invalid service date")
        try:
            date.fromisoformat(last_date)
        except ValueError as e:
            raise ValueError("invalid service date") from e
    return {"installation_id": installation_id, "charge_activity": False, **body,
            "charge_reminders": reminders}


def _restrict(path, create=False):
    """Protect database and any crash-left journal before SQLite opens them."""
    flags = os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    if create:
        flags |= os.O_CREAT
    try:
        fd = os.open(path, flags, 0o600)
    except FileNotFoundError:
        if create:
            raise
        return
    try:
        os.fchmod(fd, 0o600)
    finally:
        os.close(fd)


def _connect(db):
    os.makedirs(os.path.dirname(os.path.abspath(db)), exist_ok=True)
    _restrict(db, create=True)
    # SQLite's default DELETE rollback journal inherits the protected main
    # file's mode. A crash may leave a journal (or an older WAL) behind, so
    # restrict those too before the connection can read or replay them.
    for suffix in ("-journal", "-wal", "-shm"):
        _restrict(db + suffix)
    conn = sqlite3.connect(db, timeout=5)
    conn.execute("""CREATE TABLE IF NOT EXISTS push_installations (
        installation_id TEXT PRIMARY KEY,
        sender_secret TEXT NOT NULL,
        rules_json TEXT NOT NULL,
        locale TEXT NOT NULL,
        time_zone TEXT NOT NULL DEFAULT 'UTC',
        service_json TEXT NOT NULL,
        plus INTEGER NOT NULL,
        updated_at INTEGER NOT NULL,
        memory_json TEXT
    )""")
    columns = {row[1] for row in conn.execute("PRAGMA table_info(push_installations)")}
    if "time_zone" not in columns:
        conn.execute("ALTER TABLE push_installations ADD COLUMN time_zone TEXT NOT NULL DEFAULT 'UTC'")
    # The charging Live Activity: the phone's setting (NULL = not driven from here) and what the
    # activity was last sent, which the planner diffs the next frame against.
    for column in ("activity_json", "activity_memory_json"):
        if column not in columns:
            conn.execute(f"ALTER TABLE push_installations ADD COLUMN {column} TEXT")
    # Unplug reminders: the phone's schedule (NULL = none) and what the last frame left of it
    # (whether it was charging, when the charge ended, how many reminders it has queued).
    for column in ("reminders_json", "reminders_memory_json"):
        if column not in columns:
            conn.execute(f"ALTER TABLE push_installations ADD COLUMN {column} TEXT")
    conn.execute("""CREATE TABLE IF NOT EXISTS push_dispatcher_state (
        singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
        cursor_ts INTEGER NOT NULL DEFAULT 0,
        cursor_digest TEXT NOT NULL DEFAULT '',
        owner TEXT NOT NULL DEFAULT '',
        lease_until INTEGER NOT NULL DEFAULT 0,
        heartbeat_at INTEGER NOT NULL DEFAULT 0
    )""")
    conn.execute("""INSERT OR IGNORE INTO push_dispatcher_state(singleton) VALUES (1)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS push_outbox (
        event_id TEXT PRIMARY KEY,
        installation_id TEXT NOT NULL,
        kind TEXT NOT NULL,
        value REAL,
        occurred_at INTEGER NOT NULL,
        expires_at INTEGER NOT NULL,
        attempts INTEGER NOT NULL DEFAULT 0,
        next_attempt INTEGER NOT NULL,
        state TEXT NOT NULL DEFAULT 'pending'
    )""")
    conn.execute("""CREATE INDEX IF NOT EXISTS push_outbox_due
        ON push_outbox(state, next_attempt)""")
    # One waiting Live Activity state per phone: only the newest is worth sending.
    conn.execute("""CREATE TABLE IF NOT EXISTS push_activity_outbox (
        installation_id TEXT PRIMARY KEY,
        event_id TEXT NOT NULL,
        event TEXT NOT NULL,
        content_json TEXT NOT NULL,
        alert_minute INTEGER,
        occurred_at INTEGER NOT NULL,
        expires_at INTEGER NOT NULL,
        attempts INTEGER NOT NULL DEFAULT 0,
        next_attempt INTEGER NOT NULL,
        state TEXT NOT NULL DEFAULT 'pending'
    )""")
    conn.commit()
    return conn


def put(db, binding):
    reminders = binding.get("charge_reminders")
    reminders_json = json.dumps(reminders, sort_keys=True) if reminders else None
    with closing(_connect(db)) as conn, conn:
        before = conn.execute("""SELECT reminders_json,sender_secret FROM push_installations
            WHERE installation_id=?""", (binding["installation_id"],)).fetchone()
        conn.execute("""INSERT INTO push_installations
            (installation_id, sender_secret, rules_json, locale, time_zone, service_json, plus,
             activity_json, reminders_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(installation_id) DO UPDATE SET
              sender_secret=excluded.sender_secret,
              rules_json=excluded.rules_json,
              locale=excluded.locale,
              time_zone=excluded.time_zone,
              service_json=excluded.service_json,
              plus=excluded.plus,
              activity_json=excluded.activity_json,
              reminders_json=excluded.reminders_json,
              memory_json=CASE WHEN sender_secret<>excluded.sender_secret
                THEN NULL ELSE memory_json END,
              activity_memory_json=CASE WHEN sender_secret<>excluded.sender_secret
                OR excluded.activity_json IS NULL THEN NULL ELSE activity_memory_json END,
              reminders_memory_json=CASE WHEN sender_secret<>excluded.sender_secret
                OR excluded.reminders_json IS NULL THEN NULL ELSE reminders_memory_json END,
              updated_at=excluded.updated_at""", (
            binding["installation_id"], binding["sender_secret"],
            json.dumps(binding["rules"], sort_keys=True), binding["locale"], binding["time_zone"],
            json.dumps(binding["service"], sort_keys=True), int(binding["plus"]),
            "true" if binding["charge_activity"] else None, reminders_json, int(time.time()),
        ))
        # A queued event from an older rule set or car must not outlive a PUT -- except the unplug
        # reminders of a schedule that has not changed. The app registers again whenever it opens,
        # which is exactly when an owner standing at a charger looks at it, and that must not quietly
        # delete the reminders it exists to send. A schedule that changed, was switched off, or now
        # belongs to a different sender is dropped like the rest.
        unchanged = (before is not None and before[0] == reminders_json and
                     before[1] == binding["sender_secret"])
        conn.execute("""DELETE FROM push_outbox WHERE installation_id=?
            AND state IN ('pending','sending') AND (kind<>'charge_unplug' OR ?)""",
                     (binding["installation_id"], int(not unchanged)))
        if not binding["charge_activity"]:
            conn.execute("DELETE FROM push_activity_outbox WHERE installation_id=?",
                         (binding["installation_id"],))


def _reminder_id(installation_id, *parts):
    text = ":".join([installation_id, *map(str, parts)])
    return "e_" + hashlib.sha256(text.encode()).hexdigest()[:40]


def cancel_reminders(db):
    """The owner said the car is unplugged: drop every pending unplug reminder of every phone on this
    dashboard -- the cable is the car's, not one phone's -- and forget when the charge ended, so a
    late snooze has nothing to attach to. Returns how many were dropped."""
    with closing(_connect(db)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        dropped = conn.execute("""UPDATE push_outbox SET state='cancelled'
            WHERE kind='charge_unplug' AND state IN ('pending','sending')""").rowcount
        for installation_id, memory_json in conn.execute("""SELECT installation_id,
                reminders_memory_json FROM push_installations
                WHERE reminders_memory_json IS NOT NULL""").fetchall():
            memory = json.loads(memory_json)
            memory["ended_at"], memory["queued"] = None, 0
            conn.execute("UPDATE push_installations SET reminders_memory_json=? WHERE installation_id=?",
                         (json.dumps(memory), installation_id))
        return dropped


def snooze_reminders(db, now=None, minutes=charge_reminders.SNOOZE_MIN):
    """The owner asked to be reminded again: drop what is pending and queue one more reminder,
    `minutes` from now, for each phone with reminders on whose charge ended in the last few hours and
    that has not used up what one charge may send. Returns (dropped, queued)."""
    now = int(time.time() if now is None else now)
    queued = 0
    with closing(_connect(db)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        dropped = conn.execute("""UPDATE push_outbox SET state='cancelled'
            WHERE kind='charge_unplug' AND state IN ('pending','sending')""").rowcount
        rows = conn.execute("""SELECT installation_id,reminders_memory_json FROM push_installations
            WHERE reminders_json IS NOT NULL AND reminders_memory_json IS NOT NULL
            AND plus=1""").fetchall()
        for installation_id, memory_json in rows:
            memory = json.loads(memory_json)
            if not charge_reminders.snoozable(memory, now):
                continue
            due = now + minutes * 60
            conn.execute("""INSERT OR IGNORE INTO push_outbox
                (event_id,installation_id,kind,value,occurred_at,expires_at,next_attempt)
                VALUES (?,?,?,?,?,?,?)""", (
                _reminder_id(installation_id, memory["ended_at"], "snooze", memory["queued"]),
                installation_id, "charge_unplug", (due - memory["ended_at"]) // 60, due,
                due + charge_reminders.TTL, due))
            memory["queued"] += 1
            conn.execute("UPDATE push_installations SET reminders_memory_json=? WHERE installation_id=?",
                         (json.dumps(memory), installation_id))
            queued += 1
    return dropped, queued


def delete(db, installation_id):
    with closing(_connect(db)) as conn, conn:
        removed = conn.execute("DELETE FROM push_installations WHERE installation_id=?",
                               (installation_id,)).rowcount > 0
        conn.execute("DELETE FROM push_outbox WHERE installation_id=?", (installation_id,))
        conn.execute("DELETE FROM push_activity_outbox WHERE installation_id=?", (installation_id,))
        return removed


def count(db):
    with closing(_connect(db)) as conn:
        return conn.execute("SELECT COUNT(*) FROM push_installations").fetchone()[0]

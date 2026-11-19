"""Where "is car location switched on?" is kept, shared by the logger and the dashboard.

Two small files in the data directory:
  location.json        {"enabled": true}       written by the dashboard when the owner flips the switch
  location_state.json  {"unsupported_at": 123} written by the logger when CarLinko answers 50052

The switch cannot live in creds.json: on Railway, railway_start.sh rewrites that file from CREDS_JSON on
every boot, which would quietly undo a toggle at the next deploy. creds.json's own `location` key still
works, as the default for a dashboard whose owner has never touched the switch. The intervals and the
retention (location_interval, location_parked_interval, location_keep_days) stay creds.json-only.

Both processes read these files on every use (they hold a few bytes), so a change takes effect without
restarting anything."""
import json
import os

SETTINGS_FILE = "location.json"
STATE_FILE = "location_state.json"
KEEP_DAYS_DEFAULT = 90


def flag(v):
    """A switch written by hand may be true, 1, "true", "yes" or "on"; anything else is off."""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    return str(v or "").strip().lower() in ("1", "true", "yes", "on")


def _read(path):
    """The file's JSON object, or {} for a missing, unreadable or non-object file."""
    try:
        with open(path) as f:
            d = json.load(f)
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def _write(path, obj):
    """Atomic: the other process never reads half a file. Owner-only, like creds.json."""
    tmp = f"{path}.{os.getpid()}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(obj, f)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def enabled(data_dir, creds=None):
    """location.json's `enabled` when it says so, else creds.json's `location`, else off. A value in
    location.json that is not a recognisable switch counts as off, never as the creds.json default."""
    s = _read(os.path.join(data_dir, SETTINGS_FILE))
    if "enabled" in s:
        return flag(s["enabled"])
    if creds is None:
        creds = _read(os.path.join(data_dir, "creds.json"))
    return flag(creds.get("location"))


def set_enabled(data_dir, on):
    """Flip the switch. Switching on also forgets a 50052, so the logger asks CarLinko again."""
    _write(os.path.join(data_dir, SETTINGS_FILE), {"enabled": bool(on)})
    if on:
        clear_unsupported(data_dir)


def unsupported(data_dir):
    """True while CarLinko's last answer was 50052 (no position for this car)."""
    at = _read(os.path.join(data_dir, STATE_FILE)).get("unsupported_at")
    return isinstance(at, (int, float)) and not isinstance(at, bool) and at > 0


def mark_unsupported(data_dir, now):
    _write(os.path.join(data_dir, STATE_FILE), {"unsupported_at": int(now)})


def clear_unsupported(data_dir):
    try:
        os.unlink(os.path.join(data_dir, STATE_FILE))
    except OSError:
        pass


def keep_days(creds):
    """Retention in days from creds.json: 90 by default, 0 = forever, a typo or a negative is 90."""
    v = (creds or {}).get("location_keep_days")
    if v is None or v == "":
        return KEEP_DAYS_DEFAULT
    try:
        n = int(float(v))
    except (TypeError, ValueError, OverflowError):
        return KEEP_DAYS_DEFAULT
    return KEEP_DAYS_DEFAULT if n < 0 else min(n, 36500)

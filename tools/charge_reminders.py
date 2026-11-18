"""Unplug reminders: telling a phone its charge has finished and the car may still be plugged in.

The car reports a charge ending the same way whether or not the cable comes out (docs/api-map.md,
"Negative results": AC left plugged past the limit goes 1 -> 0 directly), so nothing here can know it
is still plugged in. A reminder is a schedule measured from the moment the charge ended, and what
stops it is the car *moving*, a new charge, or the owner saying so (POST /api/chargereminders).
Unlocking is not a stop -- owners open the door to fetch a bag with the cable still in -- and neither
is dismissing a notification.

Pure, like charge_activity.py; push_dispatcher.py does the I/O. Mirrors the app's `ChargeReminders`
(lib/entities/charge_reminders.dart): the offsets and the eta choices are the same lists; keep them so.
"""

import push_evaluator

# Minutes after the charge ended that a reminder may be set for, and how many.
OFFSETS = (0, 5, 10, 20, 30, 60)
MAX_OFFSETS = 3
# Minutes before the car expects to finish that a heads-up may be set for.
ETA_MINUTES = (5, 10, 15)
# A snooze: how long it waits, how recently the charge must have ended, and the most reminders one
# charge may send however often it is snoozed.
SNOOZE_MIN = 10
SNOOZE_HORIZON = 3 * 3600
MAX_PER_CHARGE = 6
# How long past its time a reminder is still worth sending; the relay lets an event live 15 minutes.
TTL = 10 * 60


def validate(config):
    """The canonical config, or ValueError. `config` is the binding's `charge_reminders` object."""
    if not isinstance(config, dict) or set(config) != {"offsets_min", "before_eta_min"}:
        raise ValueError("invalid charge reminders")
    offsets, eta = config["offsets_min"], config["before_eta_min"]
    if (not isinstance(offsets, list) or len(offsets) > MAX_OFFSETS or
            any(type(o) is not int or o not in OFFSETS for o in offsets) or
            offsets != sorted(set(offsets))):
        raise ValueError("invalid reminder offsets")
    if eta is not None and (type(eta) is not int or eta not in ETA_MINUTES):
        raise ValueError("invalid reminder lead")
    if not offsets and eta is None:
        raise ValueError("charge reminders with nothing to remind")
    return {"offsets_min": list(offsets), "before_eta_min": eta}


def plan(config, memory, snapshot, ts, *, complete, charge_complete_sent):
    """What to do for one phone on one frame: (actions, next memory).

    `config` is a validated config; `memory` is what the last frame left (`charging`, `ended_at`,
    `queued`, `eta_sent`); `complete` is whether a charge that ended just now ended complete rather
    than stopped -- a breaker or an owner who unplugged is never a reminder; `charge_complete_sent`
    is whether the charge-complete alert went out for this same frame, in which case "when it
    finishes" is skipped rather than buzzing twice.

    actions: `cancel` -- drop this phone's pending reminders; `schedule` -- [(offset, due ts)] to
    queue; `eta` -- the minutes left to announce, or None."""
    charging = bool(snapshot.get("charging"))
    moving = bool(snapshot.get("moving"))
    nxt = dict(memory)
    actions = {"cancel": False, "schedule": [], "eta": None}

    if moving or charging:
        # Driving away answers it; so does a new charge. The next charge starts from nothing.
        actions["cancel"] = True
        nxt["ended_at"], nxt["queued"] = None, 0

    if charging:
        lead = config.get("before_eta_min")
        elapsed, remaining = snapshot.get("charge_elapsed_min"), snapshot.get("charge_remaining_min")
        # The car's first estimate is taken before the charger ramps up, so it is quoted only once
        # it has settled -- the same rule as charge_started and the Live Activity.
        if (lead and not memory.get("eta_sent") and
                type(elapsed) is int and elapsed >= push_evaluator.CHARGE_SETTLE_MIN and
                type(remaining) is int and 0 < remaining <= lead):
            actions["eta"] = remaining
            nxt["eta_sent"] = True
    else:
        nxt["eta_sent"] = False

    ended = memory.get("charging") is True and not charging
    if ended and complete and not moving and config["offsets_min"]:
        actions["schedule"] = [(o, ts + o * 60) for o in config["offsets_min"]
                               if not (o == 0 and charge_complete_sent)]
        nxt["ended_at"], nxt["queued"] = ts, len(actions["schedule"])

    nxt["charging"] = charging
    return actions, nxt


def snoozable(memory, now):
    """Whether a snooze may queue another reminder for this phone: its charge ended recently, was
    scheduled, and has not used up the most one charge may send."""
    ended_at = memory.get("ended_at")
    return (type(ended_at) is int and now - ended_at <= SNOOZE_HORIZON and
            memory.get("queued", 0) < MAX_PER_CHARGE)

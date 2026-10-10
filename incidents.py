import math
import threading
import db
from config import (MERGE_DIST, DEFAULT_MERGE_DIST, CAND_GAP, RESOLVE_AFTER,
                    MIN_ALERT_CONF, FP_SUPPRESS_SECONDS)

# seconds an event must keep happening before we raise an alert
BASE_PERSIST = {"stopped_vehicle": 6.0, "congestion": 8.0, "collision": 1.5, "wrong_way": 2.0}
BASE_CONF = {"stopped_vehicle": 0.90, "congestion": 0.85, "collision": 0.80, "wrong_way": 0.85}


def severity(kind, n_vehicles):
    if kind in ("collision", "wrong_way"):
        return "HIGH"
    if kind == "congestion":
        return "HIGH" if n_vehicles >= 10 else "MEDIUM"
    return "MEDIUM"


class IncidentEngine:
    """Turns noisy per-frame events into ONE incident with a lifecycle:
       candidate -> ACTIVE -> (ACKNOWLEDGED) -> RESOLVED   or   FALSE_POSITIVE"""

    def __init__(self, camera="cam-1"):
        self.camera = camera
        self.lock = threading.Lock()
        self.candidates = []     # events not yet proven (still in memory only)
        self.open = {}           # incident_id -> live incident
        self.suppressed = []     # spots the operator called false positives
        self.tuning = {k: 1.0 for k in BASE_PERSIST}   # per-camera persistence multiplier
        self.stats = {"raw": 0, "alerts": 0, "merged": 0}
        self.now = 0.0

    def _near(self, item, ev, dist=None):
        d = dist or MERGE_DIST.get(ev["type"], DEFAULT_MERGE_DIST)
        return math.hypot(item["x"] - ev["x"], item["y"] - ev["y"]) <= d

    def _match(self, items, ev):
        for it in items:
            if it["type"] == ev["type"] and self._near(it, ev):
                return it
        return None

    def process(self, events, t, vis):
        """Call once per frame. Returns the list of NEW incidents (usually empty)."""
        new = []
        with self.lock:
            self.now = t
            for ev in events:
                self.stats["raw"] += 1

                # 1) already an open incident here? merge, do not alert again
                inc = self._match(self.open.values(), ev)
                if inc:
                    inc["last_seen"], inc["x"], inc["y"] = t, ev["x"], ev["y"]
                    inc["detections"] += 1
                    self.stats["merged"] += 1
                    if inc["detections"] % 10 == 0:
                        db.touch(inc["id"], t, inc["detections"])
                    continue

                # 2) a stopped car right after a crash / inside a queue is the SAME story
                if ev["type"] == "stopped_vehicle" and any(
                        i["type"] in ("collision", "congestion") and self._near(i, ev, 250)
                        for i in self.open.values()):
                    self.stats["merged"] += 1
                    continue

                # 3) operator said "false positive" here recently? stay quiet
                if any(s["type"] == ev["type"] and s["until"] > t and self._near(s, ev, 200)
                       for s in self.suppressed):
                    continue

                # 4) candidate: must persist long enough (longer if visibility is poor)
                cand = self._match(self.candidates, ev)
                if not cand:
                    cand = {"type": ev["type"], "first": t, "hits": 0}
                    self.candidates.append(cand)
                cand.update(x=ev["x"], y=ev["y"], last=t, why=ev["why"],
                            n=len(ev["ids"]))
                cand["hits"] += 1
                need = BASE_PERSIST[ev["type"]] * self.tuning[ev["type"]] * (1 + (1 - vis))
                conf = BASE_CONF[ev["type"]] * (0.5 + 0.5 * vis)
                if t - cand["first"] >= need and conf >= MIN_ALERT_CONF:
                    new.append(self._confirm(cand, t, conf, vis))
                    self.candidates.remove(cand)

            # housekeeping
            self.candidates = [c for c in self.candidates if t - c["last"] <= CAND_GAP]
            for iid, inc in list(self.open.items()):
                if t - inc["last_seen"] > RESOLVE_AFTER:
                    if inc["status"] == "ACTIVE":
                        db.set_status(iid, "RESOLVED")
                    db.touch(iid, inc["last_seen"], inc["detections"])
                    del self.open[iid]
            self.suppressed = [s for s in self.suppressed if s["until"] > t]
        return new

    def _confirm(self, cand, t, conf, vis):
        why = cand["why"] + f" Picture visibility {vis:.0%}, alert confidence {conf:.0%}."
        iid = db.create_incident({
            "camera": self.camera, "type": cand["type"], "severity": severity(cand["type"], cand["n"]),
            "confidence": round(conf, 2), "x": cand["x"], "y": cand["y"], "vehicles": cand["n"],
            "detections": cand["hits"], "why": why, "first_seen": cand["first"], "last_seen": t})
        inc = {"id": iid, "type": cand["type"], "x": cand["x"], "y": cand["y"],
               "last_seen": t, "status": "ACTIVE", "detections": cand["hits"]}
        self.open[iid] = inc
        self.stats["alerts"] += 1
        return inc

    # ----- operator feedback (called from the API thread) -----
    def acknowledge(self, iid):
        with self.lock:
            if iid in self.open:
                self.open[iid]["status"] = "ACKNOWLEDGED"

    def false_positive(self, row):
        """Operator says this alert was wrong: close it, ignore the spot, be stricter next time."""
        with self.lock:
            self.open.pop(row["id"], None)
            kind = row["type"]
            self.tuning[kind] = min(2.5, self.tuning[kind] * 1.25)
            self.suppressed.append({"type": kind, "x": row["x"], "y": row["y"],
                                    "until": self.now + FP_SUPPRESS_SECONDS})

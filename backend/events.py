import math
from collections import deque
from config import (CLASS_NAMES, FLOWING_SPEED, MIN_TRACK_AGE, STOP_ABS, STOP_RATIO,
                    CONGESTION_RATIO, CONGESTION_MIN, COLLISION_IOU, WRONG_WAY_DOT,
                    WRONG_WAY_MIN_COHERENCE, MIN_MOVING_SPEED)


class Track:
    """One vehicle followed over time (the ID comes from ByteTrack)."""

    def __init__(self, tid, cls):
        self.id, self.cls = tid, cls
        self.hist = deque()        # (t, x, y) of the last ~1 second
        self.speeds = deque()      # (t, speed) of the last ~2.5 seconds
        self.speed, self.dir = 0.0, (0.0, 0.0)
        self.box, self.gx, self.gy = None, 0.0, 0.0
        self.first_t = self.last_t = None

    @property
    def age(self):
        return self.last_t - self.first_t

    def update(self, t, box):
        self.box = box
        self.gx, self.gy = (box[0] + box[2]) / 2, box[3]     # ground point = bottom centre
        if self.first_t is None:
            self.first_t = t
        self.last_t = t
        self.hist.append((t, self.gx, self.gy))
        while t - self.hist[0][0] > 1.0:
            self.hist.popleft()
        t0, x0, y0 = self.hist[0]
        if t - t0 >= 0.4:
            dx, dy = self.gx - x0, self.gy - y0
            dist = math.hypot(dx, dy)
            self.speed = 0.5 * self.speed + 0.5 * (dist / (t - t0))   # smoothed px/s
            if dist > 1e-6:
                self.dir = (dx / dist, dy / dist)
        self.speeds.append((t, self.speed))
        while t - self.speeds[0][0] > 2.5:
            self.speeds.popleft()

    def drop(self):
        """How much speed was lost recently (0 = none, 1 = came to a full stop)."""
        peak = max((s for _, s in self.speeds), default=0.0)
        return 0.0 if peak < 30 else max(0.0, 1 - self.speed / peak)


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def find_events(seen, flow, t):
    """Compare every vehicle with the learned flow and return raw event detections."""
    events = []
    base = {s.id: flow.baseline(s.gx, s.gy) for s in seen}
    mature = [s for s in seen if s.age >= MIN_TRACK_AGE]

    # 1) CONGESTION: many vehicles far slower than normal, close together
    slow = [s for s in mature if base[s.id] and base[s.id]["speed"] > FLOWING_SPEED
            and s.speed < CONGESTION_RATIO * base[s.id]["speed"]]
    if len(slow) >= CONGESTION_MIN:
        events.append({
            "type": "congestion",
            "x": sum(s.gx for s in slow) / len(slow),
            "y": sum(s.gy for s in slow) / len(slow),
            "ids": [s.id for s in slow],
            "why": f"{len(slow)} vehicles are moving below {int(CONGESTION_RATIO * 100)}% "
                   f"of the normal speed for this part of the road."})
    queue = {s.id for s in slow} if len(slow) >= CONGESTION_MIN else set()

    # 2) STOPPED VEHICLE: almost no movement where traffic normally flows
    for s in mature:
        b = base[s.id]
        if not b or b["speed"] <= FLOWING_SPEED or s.id in queue:
            continue
        if s.speed < max(STOP_ABS, STOP_RATIO * b["speed"]):
            events.append({
                "type": "stopped_vehicle", "x": s.gx, "y": s.gy, "ids": [s.id],
                "why": f"Vehicle #{s.id} ({CLASS_NAMES.get(s.cls, 'vehicle')}) is almost "
                       f"stationary ({s.speed:.0f} px/s) where traffic normally moves "
                       f"at {b['speed']:.0f} px/s."})

    # 3) WRONG-WAY: moving against the learned direction of a one-way flow
    for s in mature:
        b = base[s.id]
        if not b or b["coherence"] < WRONG_WAY_MIN_COHERENCE or s.speed < MIN_MOVING_SPEED * 2:
            continue
        dot = s.dir[0] * b["dir"][0] + s.dir[1] * b["dir"][1]
        if dot < WRONG_WAY_DOT:
            events.append({
                "type": "wrong_way", "x": s.gx, "y": s.gy, "ids": [s.id],
                "why": f"Vehicle #{s.id} is travelling against the normal direction of "
                       f"traffic here (alignment {dot:.2f}, normal is +1)."})

    # 4) COLLISION: two boxes overlap AND both lost most of their speed
    for i in range(len(mature)):
        for j in range(i + 1, len(mature)):
            a, c = mature[i], mature[j]
            if iou(a.box, c.box) >= COLLISION_IOU and a.drop() > 0.5 and c.drop() > 0.5:
                events.append({
                    "type": "collision", "x": (a.gx + c.gx) / 2, "y": (a.gy + c.gy) / 2,
                    "ids": [a.id, c.id],
                    "why": f"Vehicles #{a.id} and #{c.id} overlap and both lost over 50% "
                           f"of their speed within 2 seconds."})
    return events

import sqlite3
import threading
import datetime
from config import DB_PATH

_lock = threading.Lock()
_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
_conn.row_factory = sqlite3.Row
_conn.execute("PRAGMA journal_mode=WAL")
_conn.execute("PRAGMA synchronous=NORMAL")


def init():
    with _lock:
        _conn.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                camera      TEXT,
                type        TEXT,
                status      TEXT DEFAULT 'ACTIVE',  -- ACTIVE, ACKNOWLEDGED, RESOLVED, FALSE_POSITIVE
                severity    TEXT,
                confidence  REAL,
                x           REAL,
                y           REAL,
                vehicles    INTEGER,
                detections  INTEGER DEFAULT 1,      -- how many raw detections were merged
                why         TEXT,                   -- the 'why flagged' sentence
                keyframe    TEXT,
                clip        TEXT,
                first_seen  REAL,
                last_seen   REAL,
                created_at  TEXT
            )""")
        # incidents left ACTIVE by a previous run cannot be live any more
        _conn.execute("UPDATE incidents SET status='RESOLVED' WHERE status='ACTIVE'")
        _conn.commit()


def create_incident(d):
    with _lock:
        cur = _conn.execute(
            """INSERT INTO incidents (camera, type, severity, confidence, x, y, vehicles,
                   detections, why, first_seen, last_seen, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (d["camera"], d["type"], d["severity"], d["confidence"], d["x"], d["y"],
             d["vehicles"], d["detections"], d["why"], d["first_seen"], d["last_seen"],
             datetime.datetime.now().isoformat(timespec="seconds")))
        _conn.commit()
        return cur.lastrowid


def touch(iid, last_seen, detections):
    with _lock:
        _conn.execute("UPDATE incidents SET last_seen=?, detections=? WHERE id=?",
                      (last_seen, detections, iid))
        _conn.commit()


def set_status(iid, status):
    with _lock:
        _conn.execute("UPDATE incidents SET status=? WHERE id=?", (status, iid))
        _conn.commit()


def set_evidence(iid, keyframe=None, clip=None):
    with _lock:
        _conn.execute("UPDATE incidents SET keyframe=COALESCE(?, keyframe), "
                      "clip=COALESCE(?, clip) WHERE id=?", (keyframe, clip, iid))
        _conn.commit()


def get(iid):
    with _lock:
        row = _conn.execute("SELECT * FROM incidents WHERE id=?", (iid,)).fetchone()
        return dict(row) if row else None


def list_incidents(status=None):
    with _lock:
        if status:
            rows = _conn.execute("SELECT * FROM incidents WHERE status=? ORDER BY id DESC",
                                 (status,)).fetchall()
        else:
            rows = _conn.execute("SELECT * FROM incidents ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]


def clear_all():
    with _lock:
        _conn.execute("DELETE FROM incidents")
        _conn.commit()

import threading
from collections import deque
import cv2
import numpy as np
import imageio
import db
from config import EVIDENCE, PRE_SECONDS, POST_SECONDS


class EvidenceRecorder:
    """Keeps the last few seconds of annotated frames so an alert can ship with a video clip."""

    def __init__(self, fps):
        self.fps = fps
        self.buffer = deque(maxlen=max(1, int(fps * PRE_SECONDS)))   # JPEG bytes, not raw frames
        self.pending = []                                            # clips still recording

    def push(self, jpg):
        self.buffer.append(jpg)
        for p in self.pending[:]:
            p["frames"].append(jpg)
            p["left"] -= 1
            if p["left"] <= 0:
                self.pending.remove(p)
                self._write_async(p)

    def start_clip(self, incident_id):
        self.pending.append({"id": incident_id, "frames": list(self.buffer),
                             "left": int(self.fps * POST_SECONDS)})

    def save_keyframe(self, incident_id, annotated_frame):
        name = f"incident_{incident_id}.jpg"
        cv2.imwrite(str(EVIDENCE / name), annotated_frame)
        db.set_evidence(incident_id, keyframe=name)

    def flush(self):
        """Video ended: save clips that were still recording."""
        for p in self.pending:
            self._write_async(p)
        self.pending = []

    def _write_async(self, p):
        threading.Thread(target=self._write, args=(p["id"], p["frames"]), daemon=True).start()

    def _write(self, incident_id, frames):
        name = f"incident_{incident_id}.mp4"
        try:
            writer = imageio.get_writer(str(EVIDENCE / name), fps=self.fps,
                                        codec="libx264", macro_block_size=2)
            for jpg in frames:
                bgr = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
                writer.append_data(bgr[:, :, ::-1])      # BGR -> RGB
            writer.close()
            db.set_evidence(incident_id, clip=name)
        except Exception as e:
            print("clip writing failed:", e)

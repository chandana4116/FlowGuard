import threading
import time
from pathlib import Path
import cv2
from ultralytics import YOLO
import config as C
from flowmap import FlowMap
from events import Track, find_events
from incidents import IncidentEngine
from visibility import visibility_score
from evidence import EvidenceRecorder


class Processor(threading.Thread):
    """Background worker: reads video -> detects -> tracks -> learns flow -> finds incidents."""

    def __init__(self):
        super().__init__(daemon=True)
        self.model = YOLO(C.MODEL_NAME)          # downloads weights on first run
        self.source = None
        self.new_source = False
        self.latest = None                       # latest annotated frame as JPEG bytes
        self.lock = threading.Lock()
        self.engine = IncidentEngine()
        self.flow = None
        self.processed = 0
        self.time_offset = 0.0
        self.vis = 1.0
        self.status = {"source": None, "calibrating": True, "progress": 0.0,
                       "visibility": 1.0, "vehicles": 0, "fps": 0.0}

    # ---------- called by the API ----------
    def set_source(self, path):
        # Publish the new source and clear the old frame immediately so the
        # dashboard cannot keep presenting the previous video as if it were live.
        with self.lock:
            self.source = path
            self.new_source = True
            self.latest = None
            self.status.update(source=Path(path).name, calibrating=True,
                               progress=0.0, visibility=1.0, vehicles=0, fps=0.0)

    def get_frame(self):
        with self.lock:
            return self.latest

    # ---------- thread body ----------
    def run(self):
        while True:
            if not self.source:
                time.sleep(0.3)
                continue
            try:
                self._play(self.source)
            except Exception as e:
                print("processor error:", repr(e))
                time.sleep(1)

    def _play(self, path):
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            print("cannot open video:", path)
            self.source = None
            return
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        stride = max(1, round(fps / C.TARGET_FPS))        # skip frames to stay real-time
        eff_fps = fps / stride

        if self.new_source:                               # a new camera = a new baseline
            self.flow, self.engine = None, IncidentEngine()
            self.processed, self.time_offset = 0, 0.0
            self.new_source = False
        self.model.predictor = None                       # fresh ByteTrack for this pass
        tracks, rec, idx = {}, EvidenceRecorder(eff_fps), 0

        while not self.new_source:
            if not cap.grab():
                break
            idx += 1
            if idx % stride:
                continue
            ok, frame = cap.retrieve()
            if not ok:
                break
            t_start = time.time()

            h0, w0 = frame.shape[:2]
            H = int(h0 * C.PROC_WIDTH / w0) // 2 * 2
            frame = cv2.resize(frame, (C.PROC_WIDTH, H))
            if self.flow is None:
                self.flow = FlowMap(C.PROC_WIDTH, H)
            t = self.time_offset + idx / fps

            # 1) detect + track vehicles (YOLOv8 + ByteTrack)
            res = self.model.track(frame, persist=True, tracker="bytetrack.yaml",
                                   classes=C.VEHICLE_CLASSES, conf=0.3, imgsz=640,
                                   verbose=False)[0]
            seen = []
            if res.boxes is not None and res.boxes.id is not None:
                ids = res.boxes.id.int().cpu().tolist()
                boxes = res.boxes.xyxy.cpu().numpy().tolist()
                clss = res.boxes.cls.int().cpu().tolist()
                for tid, box, cls in zip(ids, boxes, clss):
                    tr = tracks.get(tid)
                    if tr is None:
                        tr = tracks[tid] = Track(tid, cls)
                    tr.update(t, box)
                    seen.append(tr)
                    self.flow.learn(tr.gx, tr.gy, tr.dir, tr.speed)   # learn normal flow
            if idx % (stride * 50) == 0:                               # forget old tracks
                tracks = {k: v for k, v in tracks.items() if t - v.last_t < 5}

            # 2) visibility + incident logic
            self.processed += 1
            calibrated = self.processed >= C.CALIBRATION_FRAMES
            if self.processed % 5 == 0:
                self.vis = 0.8 * self.vis + 0.2 * visibility_score(frame)
            new_incidents = []
            if calibrated:
                new_incidents = self.engine.process(find_events(seen, self.flow, t), t, self.vis)

            # 3) draw, stream, collect evidence
            annotated = self._draw(frame, seen, calibrated)
            jpg = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 75])[1].tobytes()
            with self.lock:
                self.latest = jpg
            rec.push(jpg)
            for inc in new_incidents:
                rec.save_keyframe(inc["id"], annotated)
                rec.start_clip(inc["id"])

            elapsed = time.time() - t_start
            self.status.update(
                source=Path(path).name, calibrating=not calibrated,
                progress=round(min(1.0, self.processed / C.CALIBRATION_FRAMES), 2),
                visibility=round(self.vis, 2), vehicles=len(seen),
                fps=round(1 / max(elapsed, 1e-3), 1))
            time.sleep(max(0.0, 1.0 / eff_fps - elapsed))             # play at real speed

        cap.release()
        rec.flush()
        self.time_offset += idx / fps + C.RESOLVE_AFTER + 1           # video loop = clean break
        if not C.LOOP_VIDEO and not self.new_source:
            self.source = None

    # ---------- drawing ----------
    def _draw(self, frame, seen, calibrated):
        img = frame.copy()
        if C.SHOW_FLOW and self.flow is not None:
            f = self.flow
            cw, ch = f.w / C.GRID_COLS, f.h / C.GRID_ROWS
            for r in range(C.GRID_ROWS):
                for c in range(C.GRID_COLS):
                    if f.count[r, c] >= C.MIN_CELL_SAMPLES:
                        cx, cy = int((c + .5) * cw), int((r + .5) * ch)
                        end = (int(cx + f.vx[r, c] * cw * .4), int(cy + f.vy[r, c] * ch * .4))
                        cv2.arrowedLine(img, (cx, cy), end, (255, 200, 0), 1, tipLength=0.4)
        for s in seen:
            x1, y1, x2, y2 = map(int, s.box)
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 200, 0), 2)
            cv2.putText(img, f"#{s.id} {int(s.speed)}px/s", (x1, max(12, y1 - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 200, 0), 1)
        with self.engine.lock:
            for inc in self.engine.open.values():
                col = (0, 0, 255) if inc["status"] == "ACTIVE" else (0, 165, 255)
                p = (int(inc["x"]), int(inc["y"]))
                cv2.circle(img, p, 45, col, 3)
                cv2.putText(img, f"INCIDENT {inc['id']}: {inc['type']}", (p[0] - 60, p[1] - 55),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2)
        if calibrated:
            hud = f"MONITORING | visibility {self.vis:.0%}"
        else:
            hud = f"LEARNING NORMAL FLOW {self.processed * 100 // C.CALIBRATION_FRAMES}%"
        cv2.putText(img, hud, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        return img

from pathlib import Path

# ---------- folders ----------
BASE = Path(__file__).parent
DATA = BASE / "data"
VIDEOS = DATA / "videos"          # sample footage goes here
EVIDENCE = DATA / "evidence"      # keyframes + clips are saved here
DB_PATH = DATA / "flowguard.db"
VIDEOS.mkdir(parents=True, exist_ok=True)
EVIDENCE.mkdir(parents=True, exist_ok=True)

# ---------- detector ----------
MODEL_NAME = "yolov8n.pt"         # small + fast. Try yolov8s.pt for better accuracy
VEHICLE_CLASSES = [2, 3, 5, 7]    # COCO ids: car, motorcycle, bus, truck
CLASS_NAMES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
PROC_WIDTH = 960                  # every frame is resized to this width
TARGET_FPS = 10                   # we analyse ~10 frames per second (fast on a laptop)
LOOP_VIDEO = True                 # replay the video forever (handy for demos)
SHOW_FLOW = True                  # draw the learned flow arrows on the video

# ---------- flow map ----------
GRID_COLS, GRID_ROWS = 16, 9      # the image is cut into 16 x 9 cells
CALIBRATION_FRAMES = 150          # frames used to learn "normal" (about 15 s)
MIN_CELL_SAMPLES = 15             # a cell needs this many samples to be trusted
MIN_MOVING_SPEED = 12.0           # px/s: slower than this is not used for learning

# ---------- event rules (speeds are in pixels per second) ----------
FLOWING_SPEED = 30.0              # a cell is "normally flowing" above this
MIN_TRACK_AGE = 1.5               # seconds a track must exist before we judge it
STOP_ABS = 8.0                    # below this speed a vehicle is "stopped"
STOP_RATIO = 0.15                 # ...or below 15% of the cell's normal speed
CONGESTION_RATIO = 0.30           # "slow" = under 30% of normal speed
CONGESTION_MIN = 5                # this many slow vehicles together = congestion
COLLISION_IOU = 0.10              # boxes overlap more than this
WRONG_WAY_DOT = -0.5              # direction opposite to normal flow
WRONG_WAY_MIN_COHERENCE = 0.6     # only judge cells where traffic goes one way

# ---------- incident lifecycle ----------
MERGE_DIST = {"congestion": 300}  # px: detections this close = same incident
DEFAULT_MERGE_DIST = 130
CAND_GAP = 1.5                    # seconds a candidate may vanish (bus passes) and survive
RESOLVE_AFTER = 8.0               # seconds of no detection -> incident RESOLVED
MIN_ALERT_CONF = 0.45             # below this confidence we stay silent
FP_SUPPRESS_SECONDS = 90          # after "False positive", ignore that spot this long

# ---------- evidence ----------
PRE_SECONDS = 5                   # clip = 5 s before + 5 s after the alert
POST_SECONDS = 5

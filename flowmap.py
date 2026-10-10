import numpy as np
from config import GRID_COLS, GRID_ROWS, MIN_CELL_SAMPLES, MIN_MOVING_SPEED


class FlowMap:
    """Learns, for every cell of the image, the normal speed and direction of traffic."""

    def __init__(self, width, height):
        self.w, self.h = width, height
        shape = (GRID_ROWS, GRID_COLS)
        self.count = np.zeros(shape)   # samples seen
        self.vx = np.zeros(shape)      # mean unit direction (x)
        self.vy = np.zeros(shape)      # mean unit direction (y)
        self.speed = np.zeros(shape)   # mean speed in px/s

    def cell(self, x, y):
        c = min(GRID_COLS - 1, max(0, int(x / self.w * GRID_COLS)))
        r = min(GRID_ROWS - 1, max(0, int(y / self.h * GRID_ROWS)))
        return r, c

    def learn(self, x, y, direction, speed):
        if speed < MIN_MOVING_SPEED:          # only moving vehicles define "normal"
            return
        r, c = self.cell(x, y)
        n = self.count[r, c]
        a = 1.0 / min(n + 1, 500)             # running average
        self.vx[r, c] += a * (direction[0] - self.vx[r, c])
        self.vy[r, c] += a * (direction[1] - self.vy[r, c])
        self.speed[r, c] += a * (speed - self.speed[r, c])
        self.count[r, c] = n + 1

    def baseline(self, x, y):
        """Normal behaviour at this point, or None if we have not learned it yet."""
        r, c = self.cell(x, y)
        if self.count[r, c] < MIN_CELL_SAMPLES:
            return None
        coherence = float(np.hypot(self.vx[r, c], self.vy[r, c]))  # 1 = one-way, ~0 = mixed
        d = (self.vx[r, c] / coherence, self.vy[r, c] / coherence) if coherence > 1e-6 else (0.0, 0.0)
        return {"speed": float(self.speed[r, c]), "dir": d, "coherence": coherence}

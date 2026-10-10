import cv2


def visibility_score(frame):
    """Return 0.0 (very poor: dark, hazy, glare) to 1.0 (clear picture)."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (320, 180))
    contrast = min(small.std() / 60.0, 1.0)                        # haze lowers contrast
    sharpness = min(cv2.Laplacian(small, cv2.CV_64F).var() / 300.0, 1.0)  # rain/blur
    brightness = 1.0 - min(abs(small.mean() - 110) / 110.0, 1.0)   # night or glare
    return round(0.40 * contrast + 0.35 * sharpness + 0.25 * brightness, 3)

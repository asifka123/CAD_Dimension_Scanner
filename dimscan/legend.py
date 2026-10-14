"""
legend.py — Detect and mask out the title/legend box at the bottom of
            engineering drawings so OCR does not pick up metadata numbers.
"""

import cv2
import numpy as np


def detect_legend_box(img_bgr):
    """
    Return (x1, y1, x2, y2) bounding box of the title block, or None.

    Strategy
    --------
    1. Look at the bottom 45 % of the image (title blocks live there).
    2. Threshold → Hough for long horizontal lines.
    3. The first wide horizontal line that is clearly inside the image marks
       the top of the title block.
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    roi_y0 = int(h * 0.55)
    roi = gray[roi_y0:, :]

    _, thresh = cv2.threshold(roi, 150, 255, cv2.THRESH_BINARY_INV)
    lines = cv2.HoughLinesP(
        thresh, 1, np.pi / 180,
        threshold=80,
        minLineLength=int(w * 0.35),
        maxLineGap=10,
    )
    if lines is None:
        return None

    # HoughLinesP may return shape (N,1,4) or (N,4) depending on OpenCV build
    def _unpack(l):
        return np.array(l).flatten().astype(int)

    # Keep only near-horizontal lines, map Y back to full-image coords
    h_lines = sorted(
        [
            (int(_unpack(l)[1]) + roi_y0, int(min(_unpack(l)[0], _unpack(l)[2])), int(max(_unpack(l)[0], _unpack(l)[2])))
            for l in lines
            if abs(int(_unpack(l)[3]) - int(_unpack(l)[1])) < 5
        ],
        key=lambda x: x[0],
    )

    for y_abs, x_left, x_right in h_lines:
        span = x_right - x_left
        if span > w * 0.4 and x_left > w * 0.05:
            return (x_left, y_abs, w, h)

    for y_abs, x_left, x_right in h_lines:
        if (x_right - x_left) > w * 0.5:
            return (0, y_abs, w, h)

    return None


def mask_legend(img_bgr):
    """
    Return (cleaned_image, legend_box).
    The legend region is painted white so subsequent OCR ignores it.
    """
    box = detect_legend_box(img_bgr)
    if box is None:
        return img_bgr, None

    x1, y1, x2, y2 = box
    cleaned = img_bgr.copy()
    cleaned[y1:y2, x1:x2] = 255
    print(f"  [legend] excluded: y>{y1}, x>{x1}")
    return cleaned, box

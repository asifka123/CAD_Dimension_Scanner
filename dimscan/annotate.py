"""
annotate.py — Draw dimension labels, lines and arrows on a copy of the
              input image and save it as a PNG.
"""

import cv2
from pathlib import Path

from . import config as cfg


def annotate_image(img_bgr, matched, segs, legend_box, out_path):
    """
    Parameters
    ----------
    img_bgr     : original BGR image (not modified in-place)
    matched     : list of {number, line, score, label}
    segs        : all detected line segments (drawn in green)
    legend_box  : (x1,y1,x2,y2) or None
    out_path    : output file path string

    Returns
    -------
    Path to the saved annotated image.
    """
    out = img_bgr.copy()
    H, W = out.shape[:2]

    # Faint grid to help visual inspection
    for r in range(1, 4):
        cv2.line(out, (0, r * H // 4), (W, r * H // 4), (220, 220, 220), 1)
    for c in range(1, 4):
        cv2.line(out, (c * W // 4, 0), (c * W // 4, H), (220, 220, 220), 1)

    # Legend outline
    if legend_box:
        x1, y1, x2, y2 = legend_box
        cv2.rectangle(out, (x1, y1), (x2 - 1, y2 - 1), (180, 180, 180), 2)
        cv2.putText(
            out, "LEGEND (excluded)", (x1 + 5, min(y1 + 20, y2 - 5)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (120, 120, 120), 1,
        )

    # All detected segments in green
    for seg in segs:
        cv2.line(out, seg[0], seg[1], cfg.GREEN, 1, cv2.LINE_AA)

    # Matched dimensions in orange
    for m in matched:
        cx, cy = m["number"]["x"], m["number"]["y"]

        if m["line"]:
            p1, p2 = m["line"]
            mp = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
            cv2.line(out, p1, p2, cfg.ORANGE, 2, cv2.LINE_AA)
            cv2.arrowedLine(out, mp, p1, cfg.ORANGE, 2, tipLength=0.25)
            cv2.arrowedLine(out, mp, p2, cfg.ORANGE, 2, tipLength=0.25)

        cv2.circle(out, (cx, cy), 18, cfg.ORANGE, 1, cv2.LINE_AA)

        font = cv2.FONT_HERSHEY_SIMPLEX
        fs   = 0.38
        lbl  = m["label"]
        (tw, th), _ = cv2.getTextSize(lbl, font, fs, 1)
        tx = cx - tw // 2
        ty = max(th + 4, cy - 22)
        cv2.rectangle(out, (tx - 2, ty - th - 3), (tx + tw + 3, ty + 2),
                      cfg.ORANGE, -1)
        cv2.putText(out, lbl, (tx + 1, ty - 1), font, fs,
                    cfg.BLACK, 1, cv2.LINE_AA)

    cv2.imwrite(str(out_path), out)
    print(f"  [annotate] saved → {Path(out_path).name}")
    return out_path

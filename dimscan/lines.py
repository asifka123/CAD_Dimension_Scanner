"""
lines.py — Detect dimension lines in an engineering drawing using
           OpenCV HoughLinesP, then match each detected number to its
           nearest line.
"""

import string
import numpy as np
import cv2

from . import config as cfg


# ─────────────────────────────────────────────────────────────────────────────
# Geometry helpers
# ─────────────────────────────────────────────────────────────────────────────

def pt_dist(a, b):
    return float(np.hypot(a[0] - b[0], a[1] - b[1]))


def seg_dist(pt, p1, p2):
    """Perpendicular distance from pt to line segment p1-p2."""
    px, py = float(pt[0]), float(pt[1])
    x1, y1, x2, y2 = float(p1[0]), float(p1[1]), float(p2[0]), float(p2[1])
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return pt_dist(pt, p1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return pt_dist(pt, (x1 + t * dx, y1 + t * dy))


def midpt(p1, p2):
    return ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)


# ─────────────────────────────────────────────────────────────────────────────
# Line detection
# ─────────────────────────────────────────────────────────────────────────────

def detect_lines(gray, legend_box=None):
    """
    Detect all line segments in a grayscale image.

    Parameters
    ----------
    gray        : np.ndarray  grayscale image
    legend_box  : (x1,y1,x2,y2) or None — region to blank before detection

    Returns
    -------
    list of ((x1,y1),(x2,y2)) tuples (deduplicated)
    """
    H, W = gray.shape
    work = gray.copy()

    if legend_box:
        x1, y1, x2, y2 = legend_box
        work[y1:y2, x1:x2] = 255

    _, bw    = cv2.threshold(work, 200, 255, cv2.THRESH_BINARY_INV)
    edges    = cv2.Canny(bw, 30, 120, apertureSize=3)
    raw      = cv2.HoughLinesP(
        edges, 1, np.pi / 180,
        threshold=cfg.HOUGH_THRESHOLD,
        minLineLength=cfg.HOUGH_MIN_LENGTH,
        maxLineGap=cfg.HOUGH_MAX_GAP,
    )
    if raw is None:
        return []

    # HoughLinesP may return shape (N,1,4) or (N,4) depending on OpenCV build
    def _unpack(r):
        r = np.array(r).flatten()
        return int(r[0]), int(r[1]), int(r[2]), int(r[3])

    segs = [((x1, y1), (x2, y2)) for x1, y1, x2, y2 in (_unpack(r) for r in raw)]
    # Remove very short or image-spanning segments
    segs = [s for s in segs if 15 < pt_dist(s[0], s[1]) < W * 0.85]

    # Deduplicate
    uniq = []
    tol  = 8
    for l in segs:
        if not any(
            (pt_dist(l[0], u[0]) < tol and pt_dist(l[1], u[1]) < tol)
            or (pt_dist(l[0], u[1]) < tol and pt_dist(l[1], u[0]) < tol)
            for u in uniq
        ):
            uniq.append(l)

    return uniq


# ─────────────────────────────────────────────────────────────────────────────
# Reading-order sort
# ─────────────────────────────────────────────────────────────────────────────

def reading_order(items, y_tol=None):
    """
    Sort dimension dicts (with 'x' and 'y') in natural reading order:
    top-to-bottom, then left-to-right within each horizontal band.
    """
    y_tol = y_tol or cfg.ROW_Y_TOLERANCE
    if not items:
        return []

    by_y     = sorted(items, key=lambda d: d["y"])
    clusters = [[by_y[0]]]
    for item in by_y[1:]:
        if item["y"] - min(c["y"] for c in clusters[-1]) <= y_tol:
            clusters[-1].append(item)
        else:
            clusters.append([item])

    clusters.sort(key=lambda c: sum(i["y"] for i in c) / len(c))
    result = []
    for cluster in clusters:
        result.extend(sorted(cluster, key=lambda d: d["x"]))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Label generator
# ─────────────────────────────────────────────────────────────────────────────

def make_label(i):
    """
    Generate dimension labels: A-B, C-D, …, Y-Z, AA-AB, …
    Never cycles back past 26 pairs.
    """
    L = string.ascii_uppercase
    if i < 13:
        return f"{L[i * 2]}-{L[i * 2 + 1]}"
    prefix = L[(i // 13) - 1]
    j      = i % 13
    return f"{prefix}{L[j * 2]}-{prefix}{L[j * 2 + 1]}"


# ─────────────────────────────────────────────────────────────────────────────
# Number ↔ line matching + label assignment
# ─────────────────────────────────────────────────────────────────────────────

def match_and_label(numbers, segs):
    """
    For each detected number find the nearest dimension line, then assign
    labels in reading order (top→bottom, left→right).

    Parameters
    ----------
    numbers : list of {value, x, y}
    segs    : list of ((x1,y1),(x2,y2))

    Returns
    -------
    list of {number, line, score, label}  in reading order
    """
    matched = []
    for num in numbers:
        nc             = (num["x"], num["y"])
        best_score     = 1e9
        best_seg       = None
        for seg in segs:
            score = min(
                seg_dist(nc, seg[0], seg[1]),
                pt_dist(nc, midpt(seg[0], seg[1])),
            )
            if score < best_score:
                best_score, best_seg = score, seg
        matched.append({
            "number": num,
            "line":   best_seg if best_score < cfg.LINE_MATCH_DIST else None,
            "score":  round(best_score, 1),
        })

    # Sort into reading order
    ordered_nums  = reading_order([m["number"] for m in matched])
    id_to_match   = {id(m["number"]): m for m in matched}
    ordered       = [id_to_match[id(n)] for n in ordered_nums]

    for i, m in enumerate(ordered):
        m["label"] = make_label(i)

    return ordered

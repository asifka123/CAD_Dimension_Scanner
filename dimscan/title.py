"""
title.py — Extract the drawing title/identity from the title block using
           Tesseract OCR (PSM 11, word-level).

Returns a clean string like "Brake Caliper NO. 1" that is used as the
grouping key in the Excel output.  If no title block is found, falls back
to a hash of the dimension values.
"""

import re
import hashlib

import cv2
import numpy as np
import pytesseract

from . import config as cfg


# Words to ignore when scanning the title block
_SKIP_WORDS = {
    "orthogonal", "drawing", "dept", "scale", "sheet", "rev",
    "date", "issue", "created", "approved", "by", "document",
    "type", "status", "complete", "new", "title", "dwg", "technical",
    "reference", "knox", "tas",
}


def extract_title(img_bgr, legend_box):
    """
    OCR the title block and return a human-readable identity string.

    Strategy
    --------
    1. Crop the legend / title block region.
    2. Upscale 3× and run Tesseract PSM 11 (word-level, sparse).
    3. Find the "NO." token; take all words on the same pixel row (±25 px).
    4. Prepend the component name words found above "NO.".
    5. Return e.g. "Brake Caliper NO. 1".

    Falls back to a hash fingerprint when no title block exists.
    """
    if not cfg.USE_TESS_FOR_TITLE or legend_box is None:
        return None   # caller will use fingerprint fallback

    x1, y1, x2, y2 = legend_box
    crop = img_bgr[y1:y2, x1:x2]
    if crop.size == 0:
        return None

    # Use the right-third of the title block (that's where "Brake Caliper / NO." is)
    h, w = crop.shape[:2]
    crop = crop[:, w * 2 // 3:]

    scale = 3
    big   = cv2.resize(crop, None, fx=scale, fy=scale,
                       interpolation=cv2.INTER_CUBIC)
    gray  = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255,
                              cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    data = pytesseract.image_to_data(
        thresh,
        config="--oem 3 --psm 11",
        output_type=pytesseract.Output.DICT,
    )

    words = []
    for i, text in enumerate(data["text"]):
        t = text.strip()
        if not t or int(data["conf"][i]) < 5:
            continue
        words.append({
            "text": t,
            "x":    data["left"][i]   // scale,
            "y":    data["top"][i]    // scale,
            "conf": int(data["conf"][i]),
        })

    if not words:
        return None

    # Find "NO." anchor
    no_word = None
    for w in words:
        if re.match(r"^NO\.?$", w["text"], re.IGNORECASE):
            no_word = w
            break

    if no_word is None:
        return None

    no_y = no_word["y"]

    # Collect words on the same row as "NO." (±25 px)
    row_words = sorted(
        [w for w in words if abs(w["y"] - no_y) <= 25
         and w["text"].lower() not in _SKIP_WORDS],
        key=lambda w: w["x"],
    )

    # Collect title words from rows above "NO."
    title_words = sorted(
        [w for w in words if w["y"] < no_y - 5
         and w["text"].lower() not in _SKIP_WORDS
         and re.match(r"^[A-Za-z]", w["text"])],
        key=lambda w: w["x"],
    )

    title_part  = " ".join(w["text"] for w in title_words).strip()
    number_part = " ".join(w["text"] for w in row_words).strip()

    if title_part and number_part:
        identity = f"{title_part} {number_part}"
    elif number_part:
        identity = number_part
    else:
        return None

    # Normalise whitespace
    identity = re.sub(r"\s+", " ", identity).strip()
    print(f"  [title] detected: '{identity}'")
    return identity


def fingerprint(matched):
    """
    MD5 hash of sorted unique dimension values.
    Used when no title block is found.
    """
    values = sorted({m["number"]["value"] for m in matched})
    h      = hashlib.md5(str(values).encode()).hexdigest()[:8]
    return f"drawing_{h}"


def get_drawing_identity(img_bgr, legend_box, matched):
    """
    Return the identity string used to group drawings in Excel.
    Tries title-block OCR first; falls back to fingerprint.
    """
    identity = extract_title(img_bgr, legend_box)
    if identity:
        return identity
    fp = fingerprint(matched)
    print(f"  [title] no title block — using fingerprint: {fp}")
    return fp

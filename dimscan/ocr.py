"""
ocr.py — Tesseract-first OCR pipeline for reading dimension numbers from
         engineering drawings.

Primary backend : Tesseract (pytesseract)
  - Multi-pass: full image (normal) + full image (rotated 90°) to catch
    vertical dimension text.
  - Each pass upscales + Otsu-thresholds for best accuracy.

Fallback backends: EasyOCR, Gemini (selected via config.OCR_BACKEND).
"""

import os
import re
import json
import base64
import time

import cv2
import numpy as np
import pytesseract

from pathlib import Path
from . import config as cfg


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_dim(value, x, y):
    return {"value": int(value), "x": int(x), "y": int(y)}


def _dedup(dims, grid=30):
    """Remove spatial duplicates; keep highest-confidence entry."""
    seen = []
    for d in dims:
        if not any(
            d["value"] == s["value"]
            and abs(d["x"] - s["x"]) < grid
            and abs(d["y"] - s["y"]) < grid
            for s in seen
        ):
            seen.append(d)
    return seen


# ─────────────────────────────────────────────────────────────────────────────
# Tesseract backend  (primary)
# ─────────────────────────────────────────────────────────────────────────────

def _tess_pass(gray, scale=None, psm=None, rotate_cw=False):
    """
    Run Tesseract on a grayscale image (or ROI).

    Returns list of dicts: {value, conf, ox, oy, ow, oh}
    Coordinates are in the *original* (un-rotated, un-scaled) image space.
    """
    scale = scale or cfg.TESS_SCALE
    psm   = psm   or cfg.TESS_PSM

    orig_h, orig_w = gray.shape[:2]
    proc = cv2.rotate(gray, cv2.ROTATE_90_CLOCKWISE) if rotate_cw else gray

    # Upscale
    big = cv2.resize(proc, None, fx=scale, fy=scale,
                     interpolation=cv2.INTER_CUBIC)
    # Binarise
    _, thresh = cv2.threshold(big, 0, 255,
                              cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    data = pytesseract.image_to_data(
        thresh,
        config=f"--oem 3 --psm {psm}",
        output_type=pytesseract.Output.DICT,
    )

    results = []
    for i, text in enumerate(data["text"]):
        t = text.strip()
        if not re.match(r"^\d+$", t):
            continue
        val = int(t)
        if val == 0:
            continue
        conf = int(data["conf"][i])
        if conf < cfg.TESS_MIN_CONF:
            continue

        # Scale bounding box back to pre-upscale coords
        bx = data["left"][i]  // scale
        by = data["top"][i]   // scale
        bw = data["width"][i] // scale
        bh = data["height"][i] // scale

        if rotate_cw:
            # Inverse of ROTATE_90_CLOCKWISE:
            #   rotated_x → orig_y, rotated_y → orig_H-1-orig_x
            ox = by
            oy = orig_h - 1 - bx
            ow, oh = bh, bw
        else:
            ox, oy, ow, oh = bx, by, bw, bh

        results.append((val, conf, ox, oy, ow, oh))

    return results


def run_tesseract(img_path):
    """
    Full Tesseract pipeline on one image file.

    Two passes:
      Pass 1 — normal orientation  (catches horizontal dims)
      Pass 2 — rotated 90° CW      (catches vertical dims on the right side)

    Returns list of {value, x, y}.
    """
    img  = cv2.imread(img_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    all_dims = []

    # ── Pass 1: normal ────────────────────────────────────────────────────────
    for val, conf, ox, oy, ow, oh in _tess_pass(gray, psm=6):
        if cfg.TESS_MIN_VALUE <= val <= cfg.TESS_MAX_VALUE:
            all_dims.append(_make_dim(val, ox + ow // 2, oy + oh // 2))

    # ── Pass 2: rotated 90° (vertical text) ──────────────────────────────────
    for val, conf, ox, oy, ow, oh in _tess_pass(gray, psm=6, rotate_cw=True):
        if cfg.TESS_MIN_VALUE <= val <= cfg.TESS_MAX_VALUE:
            all_dims.append(_make_dim(val, ox + ow // 2, oy + oh // 2))

    deduped = _dedup(all_dims)
    print(f"  [tesseract] found {len(deduped)}: {[d['value'] for d in deduped]}")
    return deduped


# ─────────────────────────────────────────────────────────────────────────────
# EasyOCR backend  (optional fallback)
# ─────────────────────────────────────────────────────────────────────────────

_easyocr_reader = None


def run_easyocr(img_path):
    global _easyocr_reader
    import easyocr

    if _easyocr_reader is None:
        print("  [easyocr] loading (first time only)...")
        _easyocr_reader = easyocr.Reader(["en"], gpu=False)

    img   = cv2.imread(img_path)
    gray  = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w  = gray.shape
    scale = 2
    gray  = cv2.resize(gray, (w * scale, h * scale),
                       interpolation=cv2.INTER_CUBIC)
    gray  = cv2.filter2D(gray, -1, np.array([[0,-1,0],[-1,5,-1],[0,-1,0]]))

    pre = img_path.replace(".png", "_pre.png").replace(".jpg", "_pre.jpg")
    cv2.imwrite(pre, gray)

    try:
        results = _easyocr_reader.readtext(
            pre, detail=1, paragraph=False,
            allowlist="0123456789.", width_ths=0.4, min_size=5,
        )
    finally:
        if os.path.exists(pre):
            os.remove(pre)

    dims = []
    for bbox, text, conf in results:
        if conf < 0.2:
            continue
        cleaned = (text.strip()
                   .replace("O", "0").replace("o", "0")
                   .replace(" ", "").replace(",", "."))
        try:
            val = int(float(cleaned))
        except ValueError:
            continue
        if val <= 0 or val > cfg.TESS_MAX_VALUE:
            continue
        pts = np.array(bbox)
        cx  = int(pts[:, 0].mean() / scale)
        cy  = int(pts[:, 1].mean() / scale)
        dims.append(_make_dim(val, cx, cy))

    deduped = _dedup(dims)
    print(f"  [easyocr] found {len(deduped)}: {[d['value'] for d in deduped]}")
    return deduped


# ─────────────────────────────────────────────────────────────────────────────
# Gemini backend  (optional cloud fallback)
# ─────────────────────────────────────────────────────────────────────────────

_VLM_PROMPT = """You are reading an engineering technical drawing.
List EVERY dimension number you can see (measurements with arrows).
Numbers may be horizontal or rotated 90 degrees.
Strip any Ø prefix (Ø15 → 15). IGNORE title blocks, legend boxes, scale labels, dates.
Reply with ONLY a JSON array — no text before or after, no markdown:
[{"value":10,"x":185,"y":75},{"value":15,"x":292,"y":55}]"""


def _encode(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _parse_vlm_json(raw):
    raw = raw.strip()
    raw = re.sub(r"```[a-zA-Z]*", "", raw).replace("```", "").strip()
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if m:
        try:
            return _extract_vlm(json.loads(m.group()))
        except json.JSONDecodeError:
            pass
    objects = re.findall(r"\{[^{}]*\}", raw)
    if objects:
        items = []
        for obj in objects:
            try:
                items.append(json.loads(obj))
            except Exception:
                pass
        return _extract_vlm(items)
    raise ValueError(f"Cannot parse VLM response:\n{raw[:300]}")


def _extract_vlm(items):
    out = []
    for it in items:
        if "value" in it and "x" in it and "y" in it:
            try:
                v = str(it["value"]).replace("Ø", "").replace("ø", "").strip()
                out.append(_make_dim(int(float(v)), it["x"], it["y"]))
            except (ValueError, TypeError):
                pass
    return out


def run_gemini(img_path, max_retries=4):
    import requests
    if not cfg.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set in config.py")
    b64  = _encode(img_path)
    ext  = Path(img_path).suffix.lower().lstrip(".")
    mime = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
    url  = ("https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.0-flash-lite:generateContent?key={cfg.GEMINI_API_KEY}")
    body = {
        "contents": [{"parts": [
            {"inline_data": {"mime_type": mime, "data": b64}},
            {"text": _VLM_PROMPT},
        ]}],
        "generationConfig": {"temperature": 0.0, "maxOutputTokens": 2048},
    }
    wait = 20
    for attempt in range(1, max_retries + 1):
        print(f"  [gemini] attempt {attempt}/{max_retries}...")
        r = requests.post(url, json=body, timeout=60)
        if r.status_code == 429 and attempt < max_retries:
            time.sleep(wait); wait = min(wait * 2, 120); continue
        r.raise_for_status()
        raw = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        return _parse_vlm_json(raw)


# ─────────────────────────────────────────────────────────────────────────────
# Unified entry point
# ─────────────────────────────────────────────────────────────────────────────

def run_ocr(img_path):
    """Dispatch to the backend selected in config.OCR_BACKEND."""
    backend = cfg.OCR_BACKEND.lower()
    if backend == "tesseract":
        return run_tesseract(img_path)
    if backend == "easyocr":
        return run_easyocr(img_path)
    if backend == "gemini":
        return run_gemini(img_path)
    raise ValueError(
        f"OCR_BACKEND must be 'tesseract' | 'easyocr' | 'gemini', "
        f"got '{cfg.OCR_BACKEND}'"
    )

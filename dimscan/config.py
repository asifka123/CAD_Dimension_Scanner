"""
config.py — All user-editable settings in one place.
Edit this file before running DimScan.
"""

from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR     = Path(__file__).parent.parent.resolve()
INPUT_IMAGE  = ""          # single image filename  e.g. "drawing1.png"
INPUT_FOLDER = "input"     # folder of images, or "" to use INPUT_IMAGE
OUTPUT_DIR   = BASE_DIR / "output"
OUTPUT_EXCEL = str(OUTPUT_DIR / "dimensions_master.xlsx")

# ── OCR backend ──────────────────────────────────────────────────────────────
# "tesseract"  — free, local, default  (pip install pytesseract)
# "easyocr"    — free, local           (pip install easyocr)
# "gemini"     — free API, 1500 req/day
OCR_BACKEND    = "tesseract"
GEMINI_API_KEY = ""          # https://aistudio.google.com/apikey

# ── Tesseract settings ────────────────────────────────────────────────────────
TESS_SCALE      = 3          # upscale factor before OCR (3–5 recommended)
TESS_PSM        = 6          # page-segmentation mode  (6 = uniform block)
TESS_MIN_CONF   = 10         # minimum confidence to keep a detection
TESS_MIN_VALUE  = 5          # smallest dimension value accepted (mm)
TESS_MAX_VALUE  = 9999       # largest  dimension value accepted (mm)

# ── Drawing identity via pytesseract ─────────────────────────────────────────
USE_TESS_FOR_TITLE = True    # read title block with pytesseract PSM-11

# ── Line-detection (HoughLinesP) ─────────────────────────────────────────────
HOUGH_THRESHOLD   = 30
HOUGH_MIN_LENGTH  = 20
HOUGH_MAX_GAP     = 8
LINE_MATCH_DIST   = 200      # max px distance from number to its line

# ── Reading-order clustering ──────────────────────────────────────────────────
ROW_Y_TOLERANCE   = 30       # px — numbers within this band = same row

# ── Colours (BGR) ────────────────────────────────────────────────────────────
ORANGE = (0, 165, 255)
GREEN  = (0, 170,   0)
BLACK  = (0,   0,   0)

# ── File types accepted in batch mode ────────────────────────────────────────
SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif"}

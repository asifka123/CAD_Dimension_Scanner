"""
agent.py — Top-level pipeline that wires all modules together.

Single-image:  run_agent(img_path)
Batch folder:  run_folder(folder_path)
"""

import os
import cv2
from pathlib import Path

from . import config as cfg
from .legend   import mask_legend
from .ocr      import run_ocr
from .lines    import detect_lines, match_and_label
from .title    import get_drawing_identity
from .annotate import annotate_image
from .excel    import update as excel_update


# ─────────────────────────────────────────────────────────────────────────────
# Single-image pipeline
# ─────────────────────────────────────────────────────────────────────────────

def run_agent(img_path):
    """
    Full DimScan pipeline on one image.

    Steps
    -----
    1. Load image
    2. Detect & mask legend/title box
    3. OCR dimension numbers (Tesseract by default)
    4. Filter noise + deduplicate detections
    5. Detect dimension lines; match & label numbers
    6. Read drawing identity from title block
    7. Save annotated image + update master Excel
    """
    img_path = str(img_path)
    name     = Path(img_path).name

    print(f"\n{'='*56}")
    print(f"  DimScan  |  {name}")
    print(f"  OCR      |  {cfg.OCR_BACKEND}")
    print(f"{'='*56}")

    # ── Step 1: Load ──────────────────────────────────────────────────────────
    img_bgr = cv2.imread(img_path)
    if img_bgr is None:
        raise FileNotFoundError(
            f"\n  Cannot open: {img_path}\n"
            f"  Place your image in: {cfg.BASE_DIR}\n"
        )
    H, W = img_bgr.shape[:2]
    print(f"\n[1/6] Loaded {W}×{H} px")

    # ── Step 2: Legend masking ────────────────────────────────────────────────
    print(f"\n[2/6] Legend detection...")
    img_clean, legend_box = mask_legend(img_bgr)
    gray_clean = cv2.cvtColor(img_clean, cv2.COLOR_BGR2GRAY)

    # Write cleaned image to a temp file for OCR backends that take a path
    tmp = str(cfg.BASE_DIR / ("_tmp_" + name))
    cv2.imwrite(tmp, img_clean)

    # ── Step 3: OCR ───────────────────────────────────────────────────────────
    print(f"\n[3/6] OCR ({cfg.OCR_BACKEND})...")
    try:
        raw_nums = run_ocr(tmp)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    # ── Step 4: Filter + deduplicate ─────────────────────────────────────────
    nums = []
    for n in raw_nums:
        # Exclude legend zone
        if legend_box:
            lx1, ly1, lx2, ly2 = legend_box
            if lx1 <= n["x"] <= lx2 and ly1 <= n["y"] <= ly2:
                continue
        # Exclude out-of-bounds
        if not (0 < n["x"] < W and 0 < n["y"] < H):
            continue
        nums.append(n)

    # Spatial dedup
    deduped = []
    for n in nums:
        if not any(
            n["value"] == k["value"]
            and abs(n["x"] - k["x"]) < 40
            and abs(n["y"] - k["y"]) < 40
            for k in deduped
        ):
            deduped.append(n)

    # Outlier filter: keep values within 20× of the median
    if len(deduped) > 3:
        values = [n["value"] for n in deduped]
        median = sorted(values)[len(values) // 2]
        deduped = [n for n in deduped
                   if median / 20 <= n["value"] <= median * 20]

    print(f"       {len(deduped)} dimensions: {[n['value'] for n in deduped]}")

    # ── Step 5: Lines + labels ────────────────────────────────────────────────
    print(f"\n[4/6] Line detection + labelling...")
    segs    = detect_lines(gray_clean, legend_box)
    matched = match_and_label(deduped, segs)
    print(f"       {len(segs)} lines | {len(matched)} labels:")
    for m in matched:
        tick = "✓" if m["line"] else "✗"
        print(f"         {m['label']:6} = {m['number']['value']:>5} mm  {tick}")

    # ── Step 6: Drawing identity ──────────────────────────────────────────────
    print(f"\n[5/6] Reading title block (Tesseract)...")
    identity = get_drawing_identity(img_bgr, legend_box, matched)

    # ── Step 7: Save ──────────────────────────────────────────────────────────
    print(f"\n[6/6] Saving outputs...")
    cfg.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    out_img = cfg.OUTPUT_DIR / (Path(img_path).stem + "_annotated.png")
    annotate_image(img_bgr, matched, segs, legend_box, out_img)
    excel_update(matched, img_path, identity)

    print(f"\n  ✓ Done: {name}")
    print(f"    Dimensions   : {len(matched)}")
    print(f"    Identity     : {identity}")
    print(f"    Annotated    : {out_img.name}")
    print(f"    Excel        : {Path(cfg.OUTPUT_EXCEL).name}\n")
    return matched


# ─────────────────────────────────────────────────────────────────────────────
# Batch runner
# ─────────────────────────────────────────────────────────────────────────────

def run_folder(folder_path):
    """Process every supported image in folder_path."""
    folder = Path(folder_path)
    if not folder.is_dir():
        raise NotADirectoryError(f"Folder not found: {folder}")

    images = sorted([
        f for f in folder.iterdir()
        if f.suffix.lower() in cfg.SUPPORTED_EXTS
        and not f.name.startswith("_")
        and "_annotated" not in f.name
    ])

    if not images:
        print(f"  No images found in: {folder}")
        return

    print(f"\n{'='*56}")
    print(f"  BATCH  |  {len(images)} image(s) in '{folder.name}'")
    print(f"  OCR    |  {cfg.OCR_BACKEND}")
    print(f"{'='*56}")
    for i, img in enumerate(images, 1):
        print(f"  {i:>2}. {img.name}")

    ok, failed = [], []
    for i, img_path in enumerate(images, 1):
        print(f"\n── {i}/{len(images)}: {img_path.name} ──")
        try:
            run_agent(str(img_path))
            ok.append(img_path.name)
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            failed.append((img_path.name, str(e)))

    print(f"\n{'='*56}")
    print(f"  BATCH COMPLETE  |  ✓ {len(ok)}  ✗ {len(failed)}")
    for fname, err in failed:
        print(f"    - {fname}: {err}")
    print(f"  Excel → {Path(cfg.OUTPUT_EXCEL).name}")
    print(f"{'='*56}\n")

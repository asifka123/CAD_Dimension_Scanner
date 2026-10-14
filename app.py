"""
app.py — DimScan Streamlit Web App
===================================
Run with:  streamlit run app.py

Features
--------
• Upload one or more engineering drawing images
• Choose OCR backend (Tesseract / EasyOCR / Gemini)
• See annotated output image side-by-side with detected dimensions table
• Download annotated PNG and master Excel file
"""

import os
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
import streamlit as st
from PIL import Image

# ── Make sure the package is importable ──────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from dimscan import config as cfg
from dimscan.legend   import mask_legend
from dimscan.ocr      import run_ocr
from dimscan.lines    import detect_lines, match_and_label
from dimscan.title    import get_drawing_identity
from dimscan.annotate import annotate_image
from dimscan.excel    import update as excel_update


# ─────────────────────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="DimScan",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# Custom CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Header bar */
    .dimscan-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    .dimscan-header h1 {
        color: #ff8c00;
        font-size: 2.2rem;
        font-weight: 800;
        margin: 0;
        letter-spacing: 2px;
    }
    .dimscan-header p {
        color: #aab4be;
        margin: 0;
        font-size: 0.9rem;
    }

    /* Metric cards */
    .metric-card {
        background: #1e1e2e;
        border: 1px solid #2a2a3e;
        border-radius: 10px;
        padding: 1rem 1.2rem;
        text-align: center;
    }
    .metric-card .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #ff8c00;
    }
    .metric-card .metric-label {
        font-size: 0.8rem;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    /* Dimension table */
    .dim-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.9rem;
    }
    .dim-table th {
        background: #2f2f2f;
        color: #ff8c00;
        padding: 8px 12px;
        text-align: center;
        font-weight: 600;
        border: 1px solid #444;
    }
    .dim-table td {
        padding: 6px 12px;
        text-align: center;
        border: 1px solid #333;
        color: #e0e0e0;
    }
    .dim-table tr:nth-child(even) td { background: #1a1a1a; }
    .dim-table tr:nth-child(odd)  td { background: #222; }
    .dim-table tr:hover td { background: #2a2a40; }

    /* Status badges */
    .badge-ok   { color: #4caf50; font-weight: 700; }
    .badge-miss { color: #f44336; font-weight: 700; }

    /* Upload area */
    [data-testid="stFileUploader"] {
        border: 2px dashed #ff8c00 !important;
        border-radius: 12px !important;
        background: #1a1a1a !important;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: #0d0d1a;
    }
    .sidebar-section {
        background: #1a1a2e;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 1rem;
        border-left: 3px solid #ff8c00;
    }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="dimscan-header">
    <div>
        <h1>📐 DimScan</h1>
        <p>Automated Dimension Detection from Engineering CAD Drawings</p>
    </div>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar — Settings
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Settings")

    st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    st.markdown("**OCR Backend**")
    ocr_backend = st.radio(
        "Select OCR engine",
        options=["tesseract", "easyocr", "gemini"],
        index=0,
        help="Tesseract: free local, best default.\nEasyOCR: handles noisy images.\nGemini: cloud API, most accurate.",
        label_visibility="collapsed",
    )
    st.markdown('</div>', unsafe_allow_html=True)

    if ocr_backend == "gemini":
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        gemini_key = st.text_input(
            "Gemini API Key",
            type="password",
            help="Get a free key at https://aistudio.google.com/apikey",
        )
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        gemini_key = ""

    st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    st.markdown("**Tesseract Settings**")
    tess_scale = st.slider("Upscale factor", 2, 6, 3,
                           help="Higher = better accuracy on small text, slower")
    min_value  = st.number_input("Min dimension value (mm)", 1, 50, 5)
    max_value  = st.number_input("Max dimension value (mm)", 100, 9999, 9999)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    st.markdown("**About**")
    st.caption("DimScan v1.0.0")
    #st.caption("Brakes India Internship Project")
    st.caption("Author: Asif")
    st.markdown('</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Apply sidebar settings to config
# ─────────────────────────────────────────────────────────────────────────────
cfg.OCR_BACKEND    = ocr_backend
cfg.GEMINI_API_KEY = gemini_key
cfg.TESS_SCALE     = tess_scale
cfg.TESS_MIN_VALUE = min_value
cfg.TESS_MAX_VALUE = max_value


# ─────────────────────────────────────────────────────────────────────────────
# Session state
# ─────────────────────────────────────────────────────────────────────────────
if "results" not in st.session_state:
    st.session_state.results = []   # list of processed result dicts
if "excel_path" not in st.session_state:
    st.session_state.excel_path = None


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline (runs inside a temp dir so original files are untouched)
# ─────────────────────────────────────────────────────────────────────────────

def process_image(uploaded_file):
    """
    Run the full DimScan pipeline on one uploaded file.
    Returns a result dict or raises an exception.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir = Path(tmp_dir)

        # Save upload to temp file
        img_path = tmp_dir / uploaded_file.name
        img_path.write_bytes(uploaded_file.getbuffer())

        # Override output paths to temp dir
        excel_path = tmp_dir / "dimensions_master.xlsx"
        cfg.OUTPUT_DIR   = tmp_dir
        cfg.OUTPUT_EXCEL = str(excel_path)
        cfg.BASE_DIR     = tmp_dir

        # ── Pipeline ─────────────────────────────────────────────────────────
        img_bgr = cv2.imread(str(img_path))
        if img_bgr is None:
            raise ValueError("Cannot read image — unsupported format?")

        H, W = img_bgr.shape[:2]

        img_clean, legend_box = mask_legend(img_bgr)
        gray_clean = cv2.cvtColor(img_clean, cv2.COLOR_BGR2GRAY)

        tmp_ocr = tmp_dir / ("_tmp_" + uploaded_file.name)
        cv2.imwrite(str(tmp_ocr), img_clean)
        try:
            raw_nums = run_ocr(str(tmp_ocr))
        finally:
            tmp_ocr.unlink(missing_ok=True)

        # Filter + dedup
        nums = []
        for n in raw_nums:
            if legend_box:
                lx1, ly1, lx2, ly2 = legend_box
                if lx1 <= n["x"] <= lx2 and ly1 <= n["y"] <= ly2:
                    continue
            if not (0 < n["x"] < W and 0 < n["y"] < H):
                continue
            nums.append(n)

        deduped = []
        for n in nums:
            if not any(
                n["value"] == k["value"]
                and abs(n["x"] - k["x"]) < 40
                and abs(n["y"] - k["y"]) < 40
                for k in deduped
            ):
                deduped.append(n)

        if len(deduped) > 3:
            values = [n["value"] for n in deduped]
            median = sorted(values)[len(values) // 2]
            deduped = [n for n in deduped
                       if median / 20 <= n["value"] <= median * 20]

        segs    = detect_lines(gray_clean, legend_box)
        matched = match_and_label(deduped, segs)
        identity = get_drawing_identity(img_bgr, legend_box, matched)

        # Annotate
        out_img_path = tmp_dir / (Path(uploaded_file.name).stem + "_annotated.png")
        annotate_image(img_bgr, matched, segs, legend_box, out_img_path)
        excel_update(matched, str(img_path), identity, str(excel_path))

        # Read outputs back into memory so temp dir can be deleted
        annotated_bgr  = cv2.imread(str(out_img_path))
        annotated_rgb  = cv2.cvtColor(annotated_bgr, cv2.COLOR_BGR2RGB)
        excel_bytes    = excel_path.read_bytes() if excel_path.exists() else None
        original_rgb   = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

        return {
            "filename":     uploaded_file.name,
            "identity":     identity,
            "matched":      matched,
            "original":     original_rgb,
            "annotated":    annotated_rgb,
            "excel_bytes":  excel_bytes,
            "w": W, "h": H,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Upload section
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("### 📂 Upload Drawing(s)")
uploaded_files = st.file_uploader(
    "Drop engineering drawing images here",
    type=["png", "jpg", "jpeg", "bmp", "tiff"],
    accept_multiple_files=True,
    label_visibility="collapsed",
)

if uploaded_files:
    run_btn = st.button(
        f"🔍 Detect Dimensions  ({len(uploaded_files)} image{'s' if len(uploaded_files)>1 else ''})",
        type="primary",
        use_container_width=True,
    )

    if run_btn:
        st.session_state.results = []
        st.session_state.excel_path = None

        for i, uf in enumerate(uploaded_files):
            with st.spinner(f"Processing {uf.name}  ({i+1}/{len(uploaded_files)})…"):
                try:
                    result = process_image(uf)
                    st.session_state.results.append(result)
                    st.success(f"✓ {uf.name}  —  {len(result['matched'])} dimensions detected")
                except Exception as e:
                    st.error(f"✗ {uf.name}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Results
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.results:
    st.markdown("---")
    st.markdown("## 📊 Results")

    # ── Summary metrics ───────────────────────────────────────────────────────
    total_dims  = sum(len(r["matched"]) for r in st.session_state.results)
    total_imgs  = len(st.session_state.results)
    identities  = list({r["identity"] for r in st.session_state.results})

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Images Processed", total_imgs)
    with c2:
        st.metric("Total Dimensions", total_dims)
    with c3:
        st.metric("Drawing Types", len(identities))

    st.markdown("---")

    # ── Per-image results ─────────────────────────────────────────────────────
    for result in st.session_state.results:
        with st.expander(f"📄 {result['filename']}  —  {result['identity']}", expanded=True):

            col_orig, col_ann = st.columns(2)

            with col_orig:
                st.markdown("**Original Drawing**")
                st.image(result["original"], use_container_width=True)

            with col_ann:
                st.markdown("**Annotated Output**")
                st.image(result["annotated"], use_container_width=True)

            # Dimensions table
            st.markdown("**Detected Dimensions**")
            matched = result["matched"]

            table_html = """<table class="dim-table">
<thead><tr>
  <th>#</th><th>Label</th><th>Value (mm)</th>
  <th>X (px)</th><th>Y (px)</th><th>Line Found</th>
</tr></thead><tbody>"""

            for i, m in enumerate(matched, 1):
                tick  = '<span class="badge-ok">✓</span>' if m["line"] else '<span class="badge-miss">✗</span>'
                table_html += (
                    f"<tr>"
                    f"<td>{i}</td>"
                    f"<td><b>{m['label']}</b></td>"
                    f"<td>{m['number']['value']}</td>"
                    f"<td>{m['number']['x']}</td>"
                    f"<td>{m['number']['y']}</td>"
                    f"<td>{tick}</td>"
                    f"</tr>"
                )

            table_html += "</tbody></table>"
            st.markdown(table_html, unsafe_allow_html=True)

            # Per-image annotated download
            annotated_pil = Image.fromarray(result["annotated"])
            import io
            buf = io.BytesIO()
            annotated_pil.save(buf, format="PNG")
            st.download_button(
                label="⬇️ Download Annotated Image",
                data=buf.getvalue(),
                file_name=Path(result["filename"]).stem + "_annotated.png",
                mime="image/png",
                key=f"dl_img_{result['filename']}",
            )

    # ── Excel download ────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📥 Export")

    # Rebuild a combined Excel from all results in memory
    import tempfile as _tmp
    with _tmp.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        combined_excel = f.name

    cfg.OUTPUT_EXCEL = combined_excel
    # Remove stale file so excel.py creates fresh
    Path(combined_excel).unlink(missing_ok=True)

    for result in st.session_state.results:
        # Write a fake temp image path (only the name matters for row id)
        fake_path = str(Path(combined_excel).parent / result["filename"])
        excel_update(result["matched"], fake_path,
                     result["identity"], combined_excel)

    with open(combined_excel, "rb") as f:
        excel_data = f.read()
    Path(combined_excel).unlink(missing_ok=True)

    st.download_button(
        label="⬇️ Download Master Excel (all images)",
        data=excel_data,
        file_name="dimensions_master.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Empty state
# ─────────────────────────────────────────────────────────────────────────────
else:
    st.markdown("""
    <div style="text-align:center; padding:3rem; color:#555;">
        <div style="font-size:4rem;">📐</div>
        <div style="font-size:1.1rem; margin-top:0.5rem;">
            Upload engineering drawings above to get started
        </div>
        <div style="font-size:0.85rem; margin-top:0.5rem; color:#444;">
            Supported: PNG · JPG · BMP · TIFF
        </div>
    </div>
    """, unsafe_allow_html=True)

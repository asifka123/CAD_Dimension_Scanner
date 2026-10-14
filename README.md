# DimScan 🔍
**Automated Dimension Detection from Engineering CAD Drawings**

> Internship project — Brakes India | Author: Asif

DimScan takes engineering drawing images, detects all dimension numbers using
Tesseract OCR + OpenCV, labels them (A-B, C-D, …), annotates the image in
orange, and exports results to a smart Excel file that groups readings by
drawing type.

---

## Project Structure

```
dimscan/
├── dimscan/               ← Python package
│   ├── __init__.py
│   ├── config.py          ← ALL settings — edit this before running
│   ├── legend.py          ← Title block / legend box detection & masking
│   ├── ocr.py             ← Tesseract OCR pipeline (+ EasyOCR / Gemini fallbacks)
│   ├── lines.py           ← HoughLinesP line detection, label assignment
│   ├── title.py           ← Title block reader → drawing identity string
│   ├── annotate.py        ← Draw labels + arrows on image
│   ├── excel.py           ← Smart Excel updater (group by drawing type)
│   └── agent.py           ← Main pipeline (single image + batch)
├── tests/
│   ├── test_lines.py      ← Unit tests: geometry + reading-order
│   └── test_excel.py      ← Integration tests: Excel grouping logic
├── input/                 ← Put your drawing images here
├── output/                ← Annotated images + Excel file written here
├── main.py                ← Entry point (terminal + Jupyter)
├── requirements.txt
└── README.md
```

---

## Streamlit Web App (recommended)

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open **http://localhost:8501** — upload drawings, pick your OCR engine,
and download the annotated images + Excel in one click.

---

## CLI Quick Start

### 1. Install dependencies

```bash
# OS-level Tesseract (required)
sudo apt install tesseract-ocr        # Ubuntu/Debian
# brew install tesseract              # macOS

# Python packages
pip install -r requirements.txt
```

### 2. Configure

Edit **`dimscan/config.py`** — the only file you need to change:

```python
INPUT_IMAGE  = ""            # single image, e.g. "drawing1.png"
INPUT_FOLDER = "input"       # or process a whole folder
OCR_BACKEND  = "tesseract"   # "tesseract" | "easyocr" | "gemini"
```

### 3. Run

```bash
# Batch — process all images in input/
python main.py

# Single image
python main.py path/to/drawing.png

# Whole folder
python main.py path/to/folder/
```

**Jupyter:** paste `main.py` into one cell and run. Config values are
always read from `config.py` (Jupyter's `-f` flag is ignored automatically).

---

## OCR Backends

| Backend | Type | Best for |
|---|---|---|
| `tesseract` *(default)* | Free, local | Clean / simple drawings |
| `easyocr` | Free, local | Noisy / low-res drawings |
| `gemini` | Free API (1500 req/day) | Complex multi-view drawings |

---

## Excel Output Format

```
Row 1 (META, hidden): identity string per column group
Row 2 (HEADERS):  Reading No | Drawing Type | A-B | C-D | E-F | … | A-B | C-D | …
Row 3+ (DATA):    1          | Brake Caliper NO. 1 | 10 | 15 | 84 | …
                  2          | Brake Caliper NO. 1 | 12 | 20 | 90 | …
                  3          | Brake Caliper NO. 2 |   |    |    | … | 78 | 95 | …
```

- **Same drawing type** → new row appended to the same column group
- **Different drawing type** → new column group added to the right
- **Same image re-processed** → existing row updated (no duplicates)

---

## Run Tests

```bash
python -m pytest tests/ -v
```

---

## Technologies Used

| Technology | Purpose |
|---|---|
| Python | Core language |
| OpenCV | Image preprocessing, line detection, annotation |
| Tesseract / pytesseract | Primary OCR engine |
| EasyOCR | Optional OCR fallback |
| HoughLinesP | Dimension line detection |
| openpyxl | Excel generation and smart update |
| NumPy | Image & coordinate math |
| pytest | Unit and integration testing |

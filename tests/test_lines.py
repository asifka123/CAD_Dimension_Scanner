"""
tests/test_lines.py — Unit tests for geometry helpers and reading-order logic.
Run with:  python -m pytest tests/
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from dimscan.lines import pt_dist, seg_dist, reading_order, make_label


# ── Geometry ─────────────────────────────────────────────────────────────────

def test_pt_dist_horizontal():
    assert pt_dist((0, 0), (3, 4)) == pytest.approx(5.0)


def test_seg_dist_midpoint():
    # Point directly above the midpoint of a horizontal segment
    d = seg_dist((50, 0), (0, 10), (100, 10))
    assert d == pytest.approx(10.0)


def test_seg_dist_endpoint():
    # Point beyond the end of the segment → distance to endpoint
    d = seg_dist((200, 0), (0, 0), (100, 0))
    assert d == pytest.approx(100.0)


# ── Reading order ─────────────────────────────────────────────────────────────

def test_reading_order_simple():
    items = [
        {"value": 3, "x": 300, "y": 10},
        {"value": 1, "x": 100, "y": 10},
        {"value": 2, "x": 200, "y": 10},
    ]
    result = reading_order(items)
    assert [r["value"] for r in result] == [1, 2, 3]


def test_reading_order_two_rows():
    items = [
        {"value": 3, "x": 100, "y": 100},   # row 2, left
        {"value": 1, "x": 100, "y": 10},    # row 1, left
        {"value": 4, "x": 200, "y": 100},   # row 2, right
        {"value": 2, "x": 200, "y": 10},    # row 1, right
    ]
    result = reading_order(items)
    assert [r["value"] for r in result] == [1, 2, 3, 4]


def test_reading_order_empty():
    assert reading_order([]) == []


# ── Labels ────────────────────────────────────────────────────────────────────

def test_labels_first_13():
    expected = ["A-B", "C-D", "E-F", "G-H", "I-J", "K-L",
                "M-N", "O-P", "Q-R", "S-T", "U-V", "W-X", "Y-Z"]
    assert [make_label(i) for i in range(13)] == expected


def test_label_14_onward():
    # Index 13 → second set, prefix "A"
    assert make_label(13) == "AA-AB"
    assert make_label(14) == "AC-AD"

#!/usr/bin/env python3
"""
extract_asc606_excel.py

Extracts ASC-606 checklist data (Question / Yes-No / Analysis) from an Excel workbook
into a single JSON file. Designed for workbooks with multiple "Step" sheets.

Features
- Auto-detect sheets whose names contain "step" (configurable).
- Heuristic detection of 'question', 'answer (yes/no)', and 'analysis' columns.
- Preserves any explicit 'Step' column if present; otherwise uses sheet name.
- Optional OCR fallback for embedded screenshots/images (requires Tesseract).
- Outputs a normalized JSON you can feed to other tools.

Usage
------
python extract_asc606_excel.py /path/to/workbook.xlsm -o out.json
python extract_asc606_excel.py workbook.xlsm -o out.json --include-sheets "Step 1,Step 2"
python extract_asc606_excel.py workbook.xlsm -o out.json --ocr-images

Notes
- OCR mode extracts images from the Excel zip (xl/media/*) and runs pytesseract.
  Mapping an image back to a specific sheet is non-trivial in OOXML; we attach OCR
  text under a best-effort 'sheet_hint' and filename. (See MS Open XML package
  structure docs.) 
"""

from __future__ import annotations
import argparse
import json
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

# Optional imports (only used if --ocr-images is passed)
try:
    from PIL import Image
    import pytesseract  # wrapper for the Tesseract OCR engine
except Exception:
    Image = None
    pytesseract = None


QUESTION_SYNONYMS = {
    "question", "questions", "checklist question", "description", "prompt", "query", "requirement"
}
ANSWER_SYNONYMS = {
    "answer", "yes/no", "yes_no", "yesno", "decision", "response", "result", "y/n"
}
ANALYSIS_SYNONYMS = {
    "analysis", "rationale", "explanation", "comment", "comments", "note", "notes", "observation", "observations", "justification"
}
STEP_SYNONYMS = {
    "step", "asc 606 step", "asc606 step", "asc-606 step", "section", "phase"
}


def norm(s: Optional[str]) -> str:
    if s is None:
        return ""
    s = str(s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def header_to_key(h: str) -> str:
    """Normalize a column header for fuzzy matching."""
    h = norm(h).lower()
    h = h.replace(":", "").replace("-", " ").replace("/", " ").replace("\\", " ")
    h = re.sub(r"[\s_]+", " ", h)
    return h


def choose_column(headers: List[str], synonyms: set) -> Optional[str]:
    """Pick the best-matching column name from headers given a set of synonyms."""
    scored: List[Tuple[int, str]] = []
    for col in headers:
        key = header_to_key(col)
        score = 0
        for syn in synonyms:
            if syn == key:
                score += 100
            if syn in key:
                score += 10
        if score:
            scored.append((score, col))
    if not scored:
        return None
    scored.sort(reverse=True)
    return scored[0][1]


def detect_columns(df: pd.DataFrame) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    headers = [str(c) for c in df.columns]

    q_col = choose_column(headers, QUESTION_SYNONYMS)
    a_col = choose_column(headers, ANSWER_SYNONYMS)
    an_col = choose_column(headers, ANALYSIS_SYNONYMS)
    step_col = choose_column(headers, STEP_SYNONYMS)

    # Fallbacks
    if q_col is None and headers:
        q_col = headers[0]
    if a_col is None and len(headers) >= 2:
        a_col = headers[1]
    if an_col is None and len(headers) >= 3:
        an_col = headers[2]

    return q_col, a_col, an_col, step_col


def coerce_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Convert everything to strings (preserves visuals), dropping fully empty rows/cols
    df = df.replace({pd.NA: None})
    df = df.dropna(axis=0, how="all")
    df = df.dropna(axis=1, how="all")
    # Fill down headers if merged cells created NaNs in first row
    df.columns = [norm(c) if norm(c) else f"col_{i}" for i, c in enumerate(df.columns)]
    return df


def extract_from_sheet(sheet_name: str, df: pd.DataFrame) -> List[Dict]:
    out: List[Dict] = []
    df = coerce_dataframe(df)
    q_col, a_col, an_col, step_col = detect_columns(df)

    for idx, row in df.iterrows():
        q = norm(row.get(q_col)) if q_col in df.columns else ""
        a = norm(row.get(a_col)) if a_col in df.columns else ""
        an = norm(row.get(an_col)) if an_col in df.columns else ""
        step_val = norm(row.get(step_col)) if step_col and (step_col in df.columns) else ""

        # signal 'Unknown' if answer field empty but question exists
        if q and not a:
            # simple heuristic: if row has a lone 'yes' or 'no' token
            tokens = {norm(v).lower() for v in row.values if isinstance(v, str)}
            if "yes" in tokens and "no" not in tokens:
                a = "Yes"
            elif "no" in tokens and "yes" not in tokens:
                a = "No"

        if q or a or an:
            out.append({
                "step": step_val or sheet_name,
                "row": int(idx) if isinstance(idx, (int, float)) else str(idx),
                "question": q or None,
                "yes_no": a or None,
                "analysis": an or None,
                "source": {
                    "sheet": sheet_name
                },
                "confidence": "table"
            })
    return out


def iter_excel_tables(path: Path, include_sheets: Optional[List[str]], step_pattern: Optional[re.Pattern]) -> List[Dict]:
    items: List[Dict] = []

    # Pandas will select openpyxl engine for .xlsm/.xlsx if installed.
    with pd.ExcelFile(path) as xls:  # pandas supports .xlsm via openpyxl
        names = xls.sheet_names

        def wants(name: str) -> bool:
            if include_sheets:
                return any(name.strip().lower() == s.strip().lower() for s in include_sheets)
            if step_pattern:
                return bool(step_pattern.search(name))
            return True

        for name in names:
            if not wants(name):
                continue
            try:
                df = xls.parse(name, dtype=str)
            except Exception:
                continue
            items.extend(extract_from_sheet(name, df))
    return items


def ocr_from_excel_images(path: Path) -> List[Dict]:
    """Best-effort OCR of embedded images in the workbook zip (xl/media/*).
    Returns a list of OCR text blocks as items with minimal metadata.
    """
    if pytesseract is None or Image is None:
        return []

    results: List[Dict] = []
    with zipfile.ZipFile(path, "r") as zf:
        media_files = [n for n in zf.namelist() if n.lower().startswith("xl/media/")]
        for n in media_files:
            try:
                with zf.open(n) as f:
                    im = Image.open(f).convert("RGB")
                    text = pytesseract.image_to_string(im)
                    text = norm(text)
                    if not text:
                        continue
                results.append({
                    "step": None,
                    "row": None,
                    "question": None,
                    "yes_no": None,
                    "analysis": text,
                    "source": {"image_path_in_xlsx": n},
                    "confidence": "ocr"
                })
            except Exception:
                continue
    return results


def main():
    ap = argparse.ArgumentParser(description="Extract ASC-606 checklist Q/A/Analysis from Excel to JSON.")
    ap.add_argument("excel", type=Path, help="Path to .xlsm/.xlsx workbook")
    ap.add_argument("-o", "--output", type=Path, default=None, help="Path to output JSON (default: print to stdout)")
    ap.add_argument("--include-sheets", type=str, default=None,
                    help="Comma-separated sheet names to include. Default: sheets whose names match --step-regex.")
    ap.add_argument("--step-regex", type=str, default=r"(?i)\bstep\b",
                    help="Regex for sheet name matching (default: '(?i)\\bstep\\b').")
    ap.add_argument("--ocr-images", action="store_true",
                    help="Also OCR embedded images (requires Tesseract + pytesseract).")
    args = ap.parse_args()

    excel_path: Path = args.excel
    if not excel_path.exists():
        print(f"ERROR: File not found: {excel_path}", file=sys.stderr)
        sys.exit(2)

    include_sheets = [s.strip() for s in args.include_sheets.split(",")] if args.include_sheets else None
    step_pattern = re.compile(args.step_regex) if args.step_regex else None

    items = iter_excel_tables(excel_path, include_sheets, step_pattern)

    # Optional OCR fallback
    ocr_items: List[Dict] = []
    if args.ocr_images:
        ocr_items = ocr_from_excel_images(excel_path)
        # Only add OCR results if we didn't find anything in tables
        if items and ocr_items:
            # attach OCR text as supplemental "analysis_blobs" at the top-level
            pass

    output = {
        "workbook": excel_path.name,
        "sheets_processed": sorted({it["source"]["sheet"] for it in items if it.get("source", {}).get("sheet")}),
        "items": items,
    }
    if ocr_items:
        output["ocr_analysis_blobs"] = ocr_items  # unstructured OCR text blocks for manual review

    # Write or print
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"Wrote {args.output} with {len(items)} items"
              f"{' + ' + str(len(ocr_items)) + ' OCR blobs' if ocr_items else ''}.")
    else:
        print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

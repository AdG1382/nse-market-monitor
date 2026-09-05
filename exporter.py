"""Exports market summary data tables to CSV and Excel (.xlsx) formats."""

import csv
import io
import pandas as pd
from config import RETURN_WINDOWS, BENCHMARK_CATALOG


def _format_row_dict(r: dict, name_map: dict = None, show_from: bool = True, show_abs: bool = True, show_pct: bool = True) -> dict:
    symbol = r.get("symbol") or r.get("key", "")
    if r.get("is_highlighted"):
        name = f"{r.get('display_name', symbol)} (Highlighted Benchmark)"
    else:
        name = (name_map or {}).get(symbol, BENCHMARK_CATALOG.get(symbol, {}).get("name", symbol))
    price = r.get("price")

    row = {
        "Symbol": name,
        "Level (Price)": round(price, 2) if isinstance(price, (int, float)) else "-",
    }

    for label, _ in RETURN_WINDOWS:
        if show_from:
            from_val = r.get(f"{label}_from")
            row[f"{label} From Price"] = round(from_val, 2) if isinstance(from_val, (int, float)) else "-"
        if show_abs:
            val = r.get(f"{label}_abs")
            row[f"{label} Change (±)"] = round(val, 2) if isinstance(val, (int, float)) else "-"
        if show_pct:
            pct = r.get(label)
            row[f"{label} % Return"] = f"{pct:+.2f}%" if isinstance(pct, (int, float)) else "-"

    return row


def export_to_csv(sections: dict, show_from: bool = True, show_abs: bool = True, show_pct: bool = True) -> str:
    """Returns a merged CSV string for all requested market sections."""
    output = io.StringIO()
    writer = csv.writer(output)

    for section_name, (rows, name_map) in sections.items():
        writer.writerow([f"=== {section_name.upper()} ==="])
        if not rows:
            writer.writerow(["No data available"])
            writer.writerow([])
            continue

        formatted_rows = [_format_row_dict(r, name_map, show_from=show_from, show_abs=show_abs, show_pct=show_pct) for r in rows if r]
        if formatted_rows:
            headers = list(formatted_rows[0].keys())
            writer.writerow(headers)
            for f_row in formatted_rows:
                writer.writerow([f_row[h] for h in headers])
        writer.writerow([])

    return output.getvalue()


def export_to_excel(sections: dict, show_from: bool = True, show_abs: bool = True, show_pct: bool = True) -> bytes:
    """Returns a multi-sheet Excel (.xlsx) file as bytes."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for section_name, (rows, name_map) in sections.items():
            if not rows:
                df = pd.DataFrame({"Message": ["No data available"]})
            else:
                formatted_rows = [_format_row_dict(r, name_map, show_from=show_from, show_abs=show_abs, show_pct=show_pct) for r in rows if r]
                df = pd.DataFrame(formatted_rows)
            
            # Clean sheet name (max 31 chars)
            sheet_title = section_name[:31]
            df.to_excel(writer, sheet_name=sheet_title, index=False)

    return output.getvalue()

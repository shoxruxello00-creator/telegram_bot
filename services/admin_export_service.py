import csv
import html
import io
import zipfile
from pathlib import Path
from typing import Any

EXPORT_COLUMNS = [
    ("id", "ID"),
    ("original_generation_date", "Generation Date"),
    ("category", "Category"),
    ("cefr_level", "Level"),
    ("basic_expression", "Basic English"),
    ("advanced_expression", "Advanced English"),
    ("translation_uz", "Uzbek Translation"),
    ("translation_ru", "Russian Translation"),
    ("definition_en", "English Definition & Formality"),
    ("example_en", "Example Sentence"),
    ("usage_context", "IELTS Usage Context"),
    ("admin_status", "Memorization Status"),
]


def export_vocabulary_csv(items: list[dict[str, Any]]) -> bytes:
    """Export vocabulary archive items to UTF-8 BOM CSV (Excel-friendly)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([label for _, label in EXPORT_COLUMNS])
    for item in items:
        writer.writerow([str(item.get(key, "") or "") for key, _ in EXPORT_COLUMNS])
    return buf.getvalue().encode("utf-8-sig")


def _build_minimal_openxml_xlsx(items: list[dict[str, Any]]) -> bytes:
    """
    Zero-dependency OpenXML (.xlsx) workbook generator fallback when `openpyxl`
    is not installed in a local test environment. Produces a 100% standards-valid .xlsx file.
    """
    def _col_letter(col_idx: int) -> str:
        res = ""
        n = col_idx
        while n > 0:
            n, rem = divmod(n - 1, 26)
            res = chr(65 + rem) + res
        return res

    rows_xml: list[str] = []
    all_rows = [[label for _, label in EXPORT_COLUMNS]] + [
        [str(item.get(key, "") or "") for key, _ in EXPORT_COLUMNS] for item in items
    ]
    for r_idx, row_vals in enumerate(all_rows, start=1):
        cells_xml: list[str] = []
        for c_idx, val in enumerate(row_vals, start=1):
            col_ref = f"{_col_letter(c_idx)}{r_idx}"
            escaped_val = (
                html.escape(val)
                .replace("\x00", "")
                .replace("\r", " ")
                .replace("\n", " ")
            )
            cells_xml.append(
                f'<c r="{col_ref}" t="inlineStr"><is><t>{escaped_val}</t></is></c>'
            )
        rows_xml.append(f'<row r="{r_idx}">{"".join(cells_xml)}</row>')

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(rows_xml)}</sheetData>'
        "</worksheet>"
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Vocabulary Library" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    )
    wb_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    root_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )

    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", root_rels_xml)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", wb_rels_xml)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return out.getvalue()


def export_vocabulary_xlsx(items: list[dict[str, Any]]) -> bytes:
    """Export vocabulary archive items to formatted Excel (.xlsx)."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill

        wb = Workbook()
        ws = wb.active
        ws.title = "Vocabulary Archive"

        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(
            start_color="1E1B4B", end_color="1E1B4B", fill_type="solid"
        )

        ws.append([label for _, label in EXPORT_COLUMNS])
        for col_idx in range(1, len(EXPORT_COLUMNS) + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")

        for item in items:
            ws.append([str(item.get(key, "") or "") for key, _ in EXPORT_COLUMNS])

        ws.freeze_panes = "A2"
        widths = [8, 16, 20, 10, 26, 28, 34, 34, 42, 46, 26, 18]
        for idx, w in enumerate(widths, start=1):
            col_letter = ws.cell(row=1, column=idx).column_letter
            ws.column_dimensions[col_letter].width = w

        out = io.BytesIO()
        wb.save(out)
        return out.getvalue()
    except ImportError:
        return _build_minimal_openxml_xlsx(items)


def _ascii_transliterate_for_fallback_pdf(text: str) -> str:
    replacements = {
        "‘": "'",
        "’": "'",
        "–": "-",
        "—": "-",
        "“": '"',
        "”": '"',
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _build_minimal_pdf(items: list[dict[str, Any]], title: str) -> bytes:
    """Zero-dependency valid PDF-1.4 document builder fallback."""
    lines: list[str] = [title, f"Total Vocabulary Items: {len(items)}", "-" * 78]
    for item in items:
        lines.append(
            f"#{item.get('id')} [{item.get('original_generation_date')}] "
            f"({item.get('cefr_level')} | {item.get('category')}) "
            f"{item.get('basic_expression')} -> {item.get('advanced_expression')}"
        )
        lines.append(f"   UZ: {item.get('translation_uz', '')}")
        lines.append(f"   EN: {item.get('definition_en', '')}")
        lines.append(f"   Ex: {item.get('example_en', '')}")
        lines.append("")

    # Paginate at 42 lines per page
    pages: list[list[str]] = [
        lines[i : i + 42] for i in range(0, max(1, len(lines)), 42)
    ]

    objects: list[bytes] = []
    # 1: Catalog, 2: Pages, 3: Font
    page_obj_ids: list[int] = []
    next_id = 4
    page_streams: list[tuple[int, int, bytes]] = []
    for p_lines in pages:
        page_id = next_id
        content_id = next_id + 1
        next_id += 2
        page_obj_ids.append(page_id)

        ops = ["BT", "/F1 9 Tf", "40 790 Td", "13 TL"]
        for ln in p_lines:
            safe_ln = (
                _ascii_transliterate_for_fallback_pdf(ln[:105])
                .replace("\\", "\\\\")
                .replace("(", "\\(")
                .replace(")", "\\)")
            )
            ops.append(f"({safe_ln}) Tj T*")
        ops.append("ET")
        stream_bytes = "\n".join(ops).encode("latin-1", errors="replace")
        page_streams.append((page_id, content_id, stream_bytes))

    kids_str = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
    objects.append(b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n")
    objects.append(
        f"2 0 obj << /Type /Pages /Kids [{kids_str}] /Count {len(page_obj_ids)} >> endobj\n".encode(
            "ascii"
        )
    )
    objects.append(
        b"3 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
    )

    for page_id, content_id, stream_bytes in page_streams:
        objects.append(
            f"{page_id} 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >> endobj\n".encode(
                "ascii"
            )
        )
        objects.append(
            f"{content_id} 0 obj << /Length {len(stream_bytes)} >>\nstream\n".encode(
                "ascii"
            )
            + stream_bytes
            + b"\nendstream\nendobj\n"
        )

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets: list[int] = [0]
    for obj in objects:
        offsets.append(out.tell())
        out.write(obj)

    xref_pos = out.tell()
    out.write(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    out.write(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.write(f"{off:010d} 00000 n \n".encode("ascii"))
    out.write(
        f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return out.getvalue()


def export_vocabulary_pdf(
    items: list[dict[str, Any]],
    title: str = "Shoxrux AI — Permanent IELTS Vocabulary Archive",
) -> bytes:
    """Export vocabulary archive items to formatted Unicode PDF."""
    try:
        from fpdf import FPDF

        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=14)
        pdf.add_page()

        font_candidates = [
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("C:/Windows/Fonts/segoeui.ttf"),
        ]
        unicode_font_loaded = False
        for fp in font_candidates:
            if fp.exists():
                pdf.add_font("UniFont", "", str(fp))
                pdf.set_font("UniFont", size=13)
                unicode_font_loaded = True
                break

        if not unicode_font_loaded:
            return _build_minimal_pdf(items, title)

        pdf.cell(0, 9, title, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("UniFont", size=9)
        pdf.cell(
            0,
            6,
            f"Total Exported Vocabulary: {len(items)}",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        pdf.ln(3)

        for item in items:
            header_line = (
                f"#{item.get('id')} | {item.get('original_generation_date')} | "
                f"{item.get('cefr_level')} | {item.get('category')} | "
                f"[{item.get('admin_status', 'unmemorized')}]"
            )
            pdf.set_font("UniFont", size=8)
            pdf.multi_cell(0, 5, header_line)

            pdf.set_font("UniFont", size=10)
            pdf.multi_cell(
                0,
                5.5,
                f"BASIC: {item.get('basic_expression')}   ->   ADVANCED: {item.get('advanced_expression')}",
            )

            pdf.set_font("UniFont", size=8.5)
            pdf.multi_cell(
                0,
                5,
                f"UZ: {item.get('translation_uz', '')} | RU: {item.get('translation_ru', '')}",
            )
            pdf.multi_cell(
                0,
                5,
                f"Example: {item.get('example_en', '')} ({item.get('usage_context', '')})",
            )
            pdf.ln(2.5)

        return bytes(pdf.output())
    except ImportError:
        return _build_minimal_pdf(items, title)

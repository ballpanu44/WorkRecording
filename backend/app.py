from io import BytesIO
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.error import HTTPError
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import pandas as pd
from flask import Flask, Response, abort, redirect, render_template, request, send_from_directory

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


app = Flask(__name__, template_folder='templates', static_folder='static', static_url_path='/static')

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent
GOOGLE_CSV_URL = os.getenv("GOOGLE_CSV_URL", "").strip()
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "").strip()
GOOGLE_SHEET_GID = os.getenv("GOOGLE_SHEET_GID", "").strip()
DELIVERY_GOOGLE_CSV_URL = os.getenv("DELIVERY_GOOGLE_CSV_URL", "").strip()
DELIVERY_GOOGLE_SHEET_GID = os.getenv("DELIVERY_GOOGLE_SHEET_GID", "").strip()
PACKAGED_THAI_FONT_PATH = BASE_DIR / "static" / "fonts" / "Sarabun-Regular.ttf"
PACKAGED_THAI_BOLD_FONT_PATH = BASE_DIR / "static" / "fonts" / "Sarabun-Bold.ttf"
NOTO_THAI_FONT_PATH = BASE_DIR / "static" / "fonts" / "NotoSansThai.ttf"
THAI_FONT_PATH = Path("C:/Windows/Fonts/upcfl.ttf")
THAI_BOLD_FONT_PATH = Path("C:/Windows/Fonts/upcfb.ttf")
FALLBACK_THAI_FONT_PATH = Path("C:/Windows/Fonts/tahoma.ttf")
FALLBACK_THAI_BOLD_FONT_PATH = Path("C:/Windows/Fonts/tahomabd.ttf")

COLUMNS = [
    "id",
    "วันที่เบิกงาน",
    "เลขที่เอกสาร",
    "รหัสงบประมาณ",
    "รหัสบัญชี",
    "Lot no.",
    "รหัสบล็อกแก้ว",
    "รายการ",
    "จำนวนที่เบิก",
    "ผู้บันทึก",
    "ผู้เบิก",
]

SHEET_COLUMN_ALIASES = {
    "id": ["id", "ลำดับ"],
    "วันที่เบิกงาน": ["วันที่เบิกงาน"],
    "เลขที่เอกสาร": ["เลขที่เอกสาร", "เลขที่เอกสาร (เบิก)"],
    "รหัสงบประมาณ": ["รหัสงบประมาณ"],
    "รหัสบัญชี": ["รหัสบัญชี"],
    "Lot no.": ["Lot no.", "Lot no"],
    "รหัสบล็อกแก้ว": ["รหัสบล็อกแก้ว"],
    "รายการ": ["รายการ"],
    "จำนวนที่เบิก": ["จำนวนที่เบิก"],
    "ผู้บันทึก": ["ผู้บันทึก"],
    "ผู้เบิก": ["ผู้เบิก", "ผู้บันทึก"],
}

DELIVERY_COLUMNS = [
    "id",
    "วันที่ส่งงาน",
    "เลขที่เอกสาร",
    "รหัสสินค้า",
    "รายการ",
    "ยอดเบิก",
    "งานเสีย",
    "งานดี",
    "งานสำเร็จรูป",
    "ผู้บันทึก",
]

DELIVERY_COLUMN_ALIASES = {
    "id": ["id", "ลำดับ"],
    "วันที่ส่งงาน": ["วันที่ส่งงาน"],
    "เลขที่เอกสาร": ["เลขที่เอกสาร", "เลขที่เอกสาร (โอน)"],
    "รหัสสินค้า": ["รหัสสินค้า"],
    "รายการ": ["รายการ"],
    "ยอดเบิก": ["ยอดเบิก", "ยอดเบิก (Withdraw FG)"],
    "งานเสีย": ["งานเสีย", "งานเสีย (Reject)"],
    "งานดี": ["งานดี", "งานดี (Good product)"],
    "งานสำเร็จรูป": ["งานสำเร็จรูป", "งานสำเร็จรูป (Finish Good)"],
    "ผู้บันทึก": ["ผู้บันทึก"],
}

@app.get("/")
def frontend_index():
    if not (FRONTEND_DIR / "index.html").exists():
        return redirect("/withdraw")
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/healthz")
def healthz():
    return "ok"


@app.get("/fontz")
def fontz():
    return {
        "regular": str(PACKAGED_THAI_FONT_PATH),
        "regular_exists": PACKAGED_THAI_FONT_PATH.exists(),
        "bold": str(PACKAGED_THAI_BOLD_FONT_PATH),
        "bold_exists": PACKAGED_THAI_BOLD_FONT_PATH.exists(),
    }


@app.get("/index.html")
@app.get("/login.html")
@app.get("/admin.html")
@app.get("/withdraw.html")
@app.get("/submit.html")
@app.get("/styles.css")
@app.get("/app.js")
def frontend_file():
    filename = request.path.lstrip("/")
    if not (FRONTEND_DIR / filename).exists():
        abort(404)
    return send_from_directory(FRONTEND_DIR, filename)

def clean_value(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def get_record_value(record, canonical_column, aliases=None):
    aliases = aliases or SHEET_COLUMN_ALIASES
    for column in aliases.get(canonical_column, [canonical_column]):
        if column in record:
            return clean_value(record.get(column, ""))
    return ""


def normalize_records(records, columns=None, aliases=None):
    columns = columns or COLUMNS
    aliases = aliases or SHEET_COLUMN_ALIASES
    normalized = []
    for record in records:
        normalized.append({column: get_record_value(record, column, aliases) for column in columns})
    return normalized


def get_google_csv_records():
    df = read_google_csv(GOOGLE_CSV_URL, GOOGLE_SHEET_ID, GOOGLE_SHEET_GID, "GOOGLE_CSV_URL")
    return normalize_records(df.to_dict(orient="records"))


def read_google_csv(csv_url, sheet_id, gid, setting_name):
    if csv_url:
        url = normalize_google_csv_url(csv_url, gid)
    elif sheet_id:
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        if gid:
            url = f"{url}&gid={gid}"
    else:
        raise RuntimeError(f"กรุณาตั้งค่า {setting_name} ก่อนใช้งาน Google Sheet CSV")

    try:
        return pd.read_csv(url, dtype=str).fillna("")
    except HTTPError as exc:
        raise RuntimeError(
            "อ่าน Google Sheet แบบ CSV ไม่ได้ "
            "กรุณาแชร์ Sheet เป็น Anyone with the link can view หรือใช้ File > Share > Publish to web "
            f"แล้วนำลิงก์ CSV มาใส่ {setting_name}"
        ) from exc


def normalize_google_csv_url(url, gid=""):
    parsed = urlparse(url)
    if parsed.path.endswith("/pubhtml"):
        query = dict(parse_qsl(parsed.query))
        query["output"] = "csv"
        if "single" not in query:
            query["single"] = "true"
        if gid:
            query["gid"] = gid
        return urlunparse(parsed._replace(path=parsed.path[:-4], query=urlencode(query)))

    if parsed.path.endswith("/pub"):
        query = dict(parse_qsl(parsed.query))
        query["output"] = "csv"
        if "single" not in query:
            query["single"] = "true"
        if gid:
            query["gid"] = gid
        return urlunparse(parsed._replace(query=urlencode(query)))

    if gid and "/export" in parsed.path:
        query = dict(parse_qsl(parsed.query))
        query["gid"] = gid
        return urlunparse(parsed._replace(query=urlencode(query)))

    return url


def get_all_records():
    return get_google_csv_records()


def get_records_by_set_no(set_no):
    records = get_all_records()
    return [record for record in records if clean_value(record["id"]) == set_no]


def get_grouped_records():
    grouped = []
    seen = set()
    records = get_all_records()
    for record in records:
        set_no = clean_value(record["id"])
        if not set_no or set_no in seen:
            continue
        seen.add(set_no)
        group_items = [item for item in records if clean_value(item["id"]) == set_no]
        quantities = pd.Series([item["จำนวนที่เบิก"] for item in group_items])
        first = dict(group_items[0])
        first["จำนวนรายการ"] = str(len(group_items))
        first["รวมจำนวนที่เบิก"] = str(pd.to_numeric(quantities, errors="coerce").dropna().sum())
        grouped.append(first)
    return grouped


def get_delivery_records():
    if not DELIVERY_GOOGLE_CSV_URL and not DELIVERY_GOOGLE_SHEET_GID:
        raise RuntimeError(
            "กรุณาตั้งค่า DELIVERY_GOOGLE_SHEET_GID "
            "สำหรับแท็บบันทึกการส่งงาน"
        )
    df = read_google_csv(
        DELIVERY_GOOGLE_CSV_URL or GOOGLE_CSV_URL,
        GOOGLE_SHEET_ID,
        DELIVERY_GOOGLE_SHEET_GID,
        "DELIVERY_GOOGLE_CSV_URL",
    )
    return normalize_records(df.to_dict(orient="records"), DELIVERY_COLUMNS, DELIVERY_COLUMN_ALIASES)


def get_delivery_records_by_set_no(set_no):
    return [record for record in get_delivery_records() if clean_value(record["id"]) == set_no]


def get_grouped_delivery_records():
    grouped = []
    seen = set()
    records = get_delivery_records()
    for record in records:
        set_no = clean_value(record["id"])
        if not set_no or set_no in seen:
            continue
        seen.add(set_no)
        group_items = [item for item in records if clean_value(item["id"]) == set_no]
        first = dict(group_items[0])
        first["จำนวนรายการ"] = str(len(group_items))
        for column in ["ยอดเบิก", "งานเสีย", "งานดี", "งานสำเร็จรูป"]:
            values = pd.Series([item[column] for item in group_items])
            first[f"รวม{column}"] = str(pd.to_numeric(values, errors="coerce").dropna().sum())
        grouped.append(first)
    return grouped


def get_form_context():
    item_codes = request.form.getlist("item_code[]")
    item_names = request.form.getlist("item_name[]")
    item_qtys = request.form.getlist("item_qty[]")

    items = []
    for code, name, qty in zip(item_codes, item_names, item_qtys):
        items.append(
            {
                "รหัสบล็อกแก้ว": code.strip(),
                "รายการ": name.strip(),
                "จำนวนที่เบิก": qty.strip(),
            }
        )

    return {
        "withdraw_date": request.form.get("withdraw_date", "").strip(),
        "doc_no": request.form.get("doc_no", "").strip(),
        "budget_code": request.form.get("budget_code", "").strip(),
        "account_code": request.form.get("account_code", "").strip(),
        "lot_no": request.form.get("lot_no", "").strip(),
        "withdrawer": request.form.get("withdrawer", "").strip(),
        "items": items,
    }


def get_delivery_form_context():
    item_codes = request.form.getlist("item_code[]")
    item_names = request.form.getlist("item_name[]")
    withdraw_qtys = request.form.getlist("withdraw_qty[]")
    reject_qtys = request.form.getlist("reject_qty[]")
    good_qtys = request.form.getlist("good_qty[]")
    finish_qtys = request.form.getlist("finish_qty[]")

    items = []
    for code, name, withdraw, reject, good, finish in zip(
        item_codes, item_names, withdraw_qtys, reject_qtys, good_qtys, finish_qtys
    ):
        items.append(
            {
                "รหัสสินค้า": code.strip(),
                "รายการ": name.strip(),
                "ยอดเบิก": withdraw.strip(),
                "งานเสีย": reject.strip(),
                "งานดี": good.strip(),
                "งานสำเร็จรูป": finish.strip(),
            }
        )

    return {
        "delivery_date": request.form.get("delivery_date", "").strip(),
        "doc_no": request.form.get("doc_no", "").strip(),
        "recorder": request.form.get("recorder", "").strip(),
        "items": items,
    }


def get_reportlab_font_names():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    regular_font = "Helvetica"
    bold_font = "Helvetica-Bold"
    regular_candidates = [PACKAGED_THAI_FONT_PATH, NOTO_THAI_FONT_PATH, THAI_FONT_PATH, FALLBACK_THAI_FONT_PATH]
    bold_candidates = [PACKAGED_THAI_BOLD_FONT_PATH, NOTO_THAI_FONT_PATH, THAI_BOLD_FONT_PATH, FALLBACK_THAI_BOLD_FONT_PATH]
    regular_path = next((path for path in regular_candidates if path.exists()), None)
    bold_path = next((path for path in bold_candidates if path.exists()), None)

    if regular_path:
        pdfmetrics.registerFont(TTFont("ThaiRegular", str(regular_path)))
        regular_font = "ThaiRegular"
    if bold_path:
        pdfmetrics.registerFont(TTFont("ThaiBold", str(bold_path)))
        bold_font = "ThaiBold"
    return regular_font, bold_font


def make_paragraph(text, style):
    from xml.sax.saxutils import escape

    return escape(str(text or "")).replace("\n", "<br/>")


def build_withdraw_pdf_reportlab(context):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    regular_font, bold_font = get_reportlab_font_names()
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=16 * mm,
        bottomMargin=14 * mm,
    )

    normal = ParagraphStyle(
        "ThaiNormal",
        fontName=regular_font,
        fontSize=12,
        leading=14,
        textColor=colors.HexColor("#111827"),
    )
    title = ParagraphStyle(
        "ThaiTitle",
        parent=normal,
        alignment=TA_CENTER,
        fontName=regular_font,
        fontSize=21,
        leading=24,
        spaceAfter=9,
    )
    heading = ParagraphStyle(
        "ThaiHeading",
        parent=normal,
        fontName=regular_font,
        fontSize=13,
        leading=15,
        spaceBefore=7,
        spaceAfter=5,
    )
    center = ParagraphStyle("ThaiCenter", parent=normal, alignment=TA_CENTER)
    right = ParagraphStyle("ThaiRight", parent=normal, alignment=TA_RIGHT)
    label = ParagraphStyle("ThaiLabel", parent=normal, fontName=regular_font)
    bold_center = ParagraphStyle("ThaiBoldCenter", parent=center, fontName=regular_font)

    def p(text, style=normal):
        return Paragraph(make_paragraph(text, style), style)

    story = [p("ฟอร์มบันทึกการเบิกงาน", title)]

    meta_rows = [
        [
            p("วันที่เบิกงาน", label),
            p(context["withdraw_date"], normal),
            p("เลขที่เอกสาร (เบิก)", label),
            p(context["doc_no"], normal),
        ],
        [
            p("รหัสงบประมาณ", label),
            p(context["budget_code"], normal),
            p("รหัสบัญชี", label),
            p(context["account_code"], normal),
        ],
        [
            p("Lot no.", label),
            p(context["lot_no"], normal),
            "",
            "",
        ],
    ]
    meta_table = Table(
        meta_rows,
        colWidths=[30 * mm, 58 * mm, 34 * mm, 60 * mm],
        rowHeights=[8 * mm, 8 * mm, 8 * mm],
    )
    meta_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LINEBELOW", (1, 0), (1, 2), 0.5, colors.HexColor("#374151")),
                ("LINEBELOW", (3, 0), (3, 1), 0.5, colors.HexColor("#374151")),
            ]
        )
    )
    story.append(meta_table)
    story.append(p("รายการที่เบิก", heading))

    rows = [[p("รหัสบล็อกแก้ว", bold_center), p("รายการ", bold_center), p("จำนวนที่เบิก", bold_center)]]
    for item in context["items"]:
        rows.append(
            [
                p(item["รหัสบล็อกแก้ว"]),
                p(item["รายการ"]),
                p(item["จำนวนที่เบิก"], right),
            ]
        )
    for _ in range(max(0, 18 - len(context["items"]))):
        rows.append(["", "", ""])

    item_table = Table(
        rows,
        colWidths=[50 * mm, 97 * mm, 35 * mm],
        rowHeights=[7.5 * mm] + [7 * mm] * (len(rows) - 1),
    )
    item_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#111827")),
                ("INNERGRID", (0, 0), (-1, -1), 0.55, colors.HexColor("#111827")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f7")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    story.append(item_table)
    story.append(Spacer(1, 7 * mm))

    signature_table = Table(
        [
            [p(context["withdrawer"], center)],
            [p("ผู้เบิก", center)],
        ],
        colWidths=[56 * mm],
        rowHeights=[8 * mm, 6 * mm],
        hAlign="RIGHT",
    )
    signature_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LINEBELOW", (0, 0), (0, 0), 0.7, colors.HexColor("#111827")),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )
    story.append(signature_table)

    document.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def build_delivery_pdf_reportlab(context):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    regular_font, bold_font = get_reportlab_font_names()
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=14 * mm,
        bottomMargin=12 * mm,
    )

    normal = ParagraphStyle("DeliveryNormal", fontName=regular_font, fontSize=11.5, leading=13.5)
    title = ParagraphStyle(
        "DeliveryTitle",
        parent=normal,
        alignment=TA_CENTER,
        fontName=regular_font,
        fontSize=21,
        leading=24,
        spaceAfter=9,
    )
    label = ParagraphStyle("DeliveryLabel", parent=normal, fontName=regular_font)
    center = ParagraphStyle("DeliveryCenter", parent=normal, alignment=TA_CENTER)
    right = ParagraphStyle("DeliveryRight", parent=normal, alignment=TA_RIGHT)
    bold_center = ParagraphStyle("DeliveryBoldCenter", parent=center, fontName=regular_font)

    def p(text, style=normal):
        return Paragraph(make_paragraph(text, style), style)

    story = [p("ฟอร์มบันทึกการส่งงาน", title)]
    meta_rows = [
        [
            p("วันที่ส่งงาน", label),
            p(context["delivery_date"], normal),
            p("เลขที่เอกสาร (โอน)", label),
            p(context["doc_no"], normal),
        ],
        [
            p("ผู้บันทึก", label),
            p(context["recorder"], normal),
            "",
            "",
        ],
    ]
    meta_table = Table(meta_rows, colWidths=[26 * mm, 64 * mm, 35 * mm, 61 * mm], rowHeights=[8 * mm, 8 * mm])
    meta_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LINEBELOW", (1, 0), (1, 1), 0.5, colors.HexColor("#374151")),
                ("LINEBELOW", (3, 0), (3, 0), 0.5, colors.HexColor("#374151")),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 5 * mm))

    rows = [
        [
            p("รหัสสินค้า", bold_center),
            p("รายการ", bold_center),
            p("ยอดเบิก", bold_center),
            p("งานเสีย", bold_center),
            p("งานดี", bold_center),
            p("งานสำเร็จรูป", bold_center),
        ]
    ]
    for item in context["items"]:
        rows.append(
            [
                p(item["รหัสสินค้า"]),
                p(item["รายการ"]),
                p(item["ยอดเบิก"], right),
                p(item["งานเสีย"], right),
                p(item["งานดี"], right),
                p(item["งานสำเร็จรูป"], right),
            ]
        )
    for _ in range(max(0, 16 - len(context["items"]))):
        rows.append(["", "", "", "", "", ""])

    table = Table(rows, colWidths=[27 * mm, 77 * mm, 20 * mm, 20 * mm, 20 * mm, 22 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#111827")),
                ("INNERGRID", (0, 0), (-1, -1), 0.55, colors.HexColor("#111827")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f7")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 12 * mm))

    signature_table = Table(
        [[p(context["recorder"], center)], [p("ผู้ส่งงาน", center)]],
        colWidths=[56 * mm],
        rowHeights=[8 * mm, 6 * mm],
        hAlign="RIGHT",
    )
    signature_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LINEBELOW", (0, 0), (0, 0), 0.7, colors.HexColor("#111827")),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )
    story.append(signature_table)

    document.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def find_browser_executable():
    candidates = [
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
        Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
        Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
        Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def build_pdf_with_browser(html):
    browser = find_browser_executable()
    if not browser:
        raise RuntimeError("ไม่พบ Chrome หรือ Edge สำหรับสร้าง PDF")

    temp_root = BASE_DIR / ".tmp_pdf"
    temp_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_root) as temp_dir:
        temp_dir_path = Path(temp_dir)
        html_path = temp_dir_path / "preview.html"
        pdf_path = temp_dir_path / "preview.pdf"
        profile_path = temp_dir_path / "profile"
        html_path.write_text(html, encoding="utf-8")

        command = [
            str(browser),
            "--headless=new",
            "--disable-gpu",
            "--disable-extensions",
            "--no-first-run",
            "--no-default-browser-check",
            "--no-pdf-header-footer",
            f"--user-data-dir={profile_path}",
            f"--print-to-pdf={pdf_path}",
            html_path.as_uri(),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        if result.returncode != 0 or not pdf_path.exists():
            raise RuntimeError(result.stderr or result.stdout or "Chrome สร้าง PDF ไม่สำเร็จ")
        return pdf_path.read_bytes()


def build_withdraw_pdf(context):
    try:
        html = render_template(
            "withdraw_pdf.html",
            **context,
            empty_rows=range(max(0, 16 - len(context["items"]))),
        )
        return build_pdf_with_browser(html)
    except Exception:
        return build_withdraw_pdf_reportlab(context)


def build_delivery_pdf(context):
    try:
        html = render_template(
            "delivery_pdf.html",
            **context,
            empty_rows=range(max(0, 14 - len(context["items"]))),
        )
        return build_pdf_with_browser(html)
    except Exception:
        return build_delivery_pdf_reportlab(context)


@app.route("/withdraw")
@app.route("/withdraw_index.html")
def withdraw_index():
    try:
        records = get_grouped_records()
    except RuntimeError as exc:
        return render_template("withdraw_index.html", records=[], data_error=str(exc)), 500
    return render_template("withdraw_index.html", records=records, data_error="")


@app.route("/delivery")
@app.route("/delivery_index.html")
def delivery_index():
    try:
        records = get_grouped_delivery_records()
    except RuntimeError as exc:
        return render_template("delivery_index.html", records=[], data_error=str(exc)), 500
    return render_template("delivery_index.html", records=records, data_error="")


@app.route("/withdraw/form/set/<path:set_no>")
def form_by_set(set_no):
    records = get_records_by_set_no(set_no)
    if not records:
        abort(404)

    header = records[0]
    return render_template(
        "withdraw_form.html",
        header=header,
        items=records,
    )


@app.route("/delivery/form/<path:set_no>")
def delivery_form(set_no):
    records = get_delivery_records_by_set_no(set_no)
    if not records:
        abort(404)

    header = records[0]
    return render_template("delivery_form.html", header=header, items=records)


@app.post("/withdraw/preview_pdf")
@app.post("/withdraw/preview_pdf/<path:url_doc_no>")
def preview_pdf(url_doc_no=None):
    context = get_form_context()
    doc_no = context["doc_no"]

    try:
        pdf = build_withdraw_pdf(context)
    except ImportError:
        return Response(
            "ยังไม่ได้ติดตั้ง ReportLab กรุณารันคำสั่ง: pip install -r requirements.txt",
            status=500,
            mimetype="text/plain; charset=utf-8",
        )

    safe_doc_no = "".join(ch for ch in doc_no if ch.isalnum() or ch in ("-", "_")) or "preview"
    return Response(
        pdf,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"inline; filename=withdraw_{safe_doc_no}.pdf"},
    )


@app.post("/delivery/preview_pdf")
@app.post("/delivery/preview_pdf/<path:url_doc_no>")
def delivery_preview_pdf(url_doc_no=None):
    context = get_delivery_form_context()
    doc_no = context["doc_no"]

    try:
        pdf = build_delivery_pdf(context)
    except ImportError:
        return Response(
            "ยังไม่ได้ติดตั้ง ReportLab กรุณารันคำสั่ง: pip install -r requirements.txt",
            status=500,
            mimetype="text/plain; charset=utf-8",
        )

    safe_doc_no = "".join(ch for ch in doc_no if ch.isalnum() or ch in ("-", "_")) or "preview"
    return Response(
        pdf,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"inline; filename=delivery_{safe_doc_no}.pdf"},
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(debug=True, port=port, host="0.0.0.0")

#!/usr/bin/env python3
"""Generate a proper Carrier & Aqua bill plus an arithmetic check page."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

NAVY = HexColor("#0F2C59")
GOLD = HexColor("#C9A227")
TEAL = HexColor("#1A6B6B")
LIGHT = HexColor("#F4F7FA")
ROW_ALT = HexColor("#EEF4F8")
GREEN = HexColor("#1B7A4E")
GREEN_BG = HexColor("#E8F5EE")
CREAM = HexColor("#F7F4EA")
LINE = HexColor("#D6DEE6")
DARK = HexColor("#1A2332")
GRAY = HexColor("#5C6773")

ITEMS = [
    {
        "sr": 1,
        "desc": "Tractor Scrap",
        "detail": "7 trips — scrap cartage / tractor hire (lump sum)",
        "qty": "7",
        "unit": "Trip",
        "rate": "Lump sum",
        "amount": 16000,
    },
    {
        "sr": 2,
        "desc": "Ply Carrier",
        "detail": "Plywood / ply carrier charges",
        "qty": "1",
        "unit": "Job",
        "rate": "9,000",
        "amount": 9000,
    },
    {
        "sr": 3,
        "desc": "Safai Labour",
        "detail": "Cleaning / safai labour charges",
        "qty": "1",
        "unit": "Job",
        "rate": "7,000",
        "amount": 7000,
    },
    {
        "sr": 4,
        "desc": "Aqua Guard",
        "detail": "Aqua Guard water purifier",
        "qty": "1",
        "unit": "Nos",
        "rate": "17,700",
        "amount": 17700,
    },
    {
        "sr": 5,
        "desc": "Aqua Tap",
        "detail": "Aqua tap fitting / supply",
        "qty": "1",
        "unit": "Nos",
        "rate": "1,775",
        "amount": 1775,
    },
    {
        "sr": 6,
        "desc": "Gas Pipe",
        "detail": "Gas pipe supply / fitting",
        "qty": "1",
        "unit": "Nos",
        "rate": "1,450",
        "amount": 1450,
    },
    {
        "sr": 7,
        "desc": "GLN Dining Table",
        "detail": "GLN dining table",
        "qty": "1",
        "unit": "Nos",
        "rate": "84,700",
        "amount": 84700,
    },
]

STATED_TOTAL = 137625
BILL_NO = "CA/2026-27/001"
BILL_DATE = "23 August 2026"


def inr(n: int) -> str:
    s = str(int(n))
    if len(s) <= 3:
        return s
    last3, rest = s[-3:], s[:-3]
    parts = []
    while len(rest) > 2:
        parts.append(rest[-2:])
        rest = rest[:-2]
    if rest:
        parts.append(rest)
    return ",".join(reversed(parts)) + "," + last3


def amount_in_words(num: int) -> str:
    ones = [
        "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
        "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
        "Seventeen", "Eighteen", "Nineteen",
    ]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def two(n: int) -> str:
        if n < 20:
            return ones[n]
        return tens[n // 10] + ((" " + ones[n % 10]) if n % 10 else "")

    def three(n: int) -> str:
        h, r = divmod(n, 100)
        if h and r:
            return ones[h] + " Hundred " + two(r)
        if h:
            return ones[h] + " Hundred"
        return two(r)

    crore, rem = divmod(num, 10_000_000)
    lakh, rem = divmod(rem, 100_000)
    thousand, rem = divmod(rem, 1_000)
    parts = []
    if crore:
        parts.append(three(crore) + " Crore")
    if lakh:
        parts.append(three(lakh) + " Lakh")
    if thousand:
        parts.append(three(thousand) + " Thousand")
    if rem:
        parts.append(three(rem))
    return (" ".join(parts) + " Rupees Only") if parts else "Zero Rupees Only"


def try_register_fonts() -> tuple[str, str]:
    candidates = [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ]
    for regular, bold in candidates:
        if Path(regular).exists() and Path(bold).exists():
            pdfmetrics.registerFont(TTFont("BillSans", regular))
            pdfmetrics.registerFont(TTFont("BillSans-Bold", bold))
            return "BillSans", "BillSans-Bold"
    return "Helvetica", "Helvetica-Bold"


FONT, FONT_B = try_register_fonts()


def frame(c: canvas.Canvas, page_no: int, page_count: int) -> None:
    w, h = A4
    c.setFillColor(NAVY)
    c.rect(0, h - 7 * mm, w, 7 * mm, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.rect(0, h - 8.6 * mm, w, 1.6 * mm, fill=1, stroke=0)
    c.setFillColor(NAVY)
    c.rect(0, 0, w, 10 * mm, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.rect(0, 10 * mm, w, 1.2 * mm, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont(FONT, 8)
    c.drawString(16 * mm, 4.2 * mm, "Carrier & Aqua  |  Consolidated Bill")
    c.drawRightString(w - 16 * mm, 4.2 * mm, f"Page {page_no} of {page_count}")


def rounded_rect(c: canvas.Canvas, x, y, w, h, fill):
    c.setFillColor(fill)
    c.setStrokeColor(LINE)
    c.setLineWidth(0.6)
    c.roundRect(x, y, w, h, 3, fill=1, stroke=1)


def draw_invoice(c: canvas.Canvas) -> None:
    w, h = A4
    frame(c, 1, 2)
    left, right = 16 * mm, w - 16 * mm
    y = h - 16 * mm

    c.setFillColor(NAVY)
    c.setFont(FONT_B, 20)
    c.drawString(left, y, "CARRIER & AQUA")
    c.setFont(FONT_B, 13)
    c.drawRightString(right, y, "BILL")
    y -= 6 * mm
    c.setFillColor(TEAL)
    c.setFont(FONT, 9.5)
    c.drawString(left, y, "Consolidated Expense / Purchase Bill")
    c.setFillColor(DARK)
    c.setFont(FONT, 9)
    c.drawRightString(right, y, f"Bill No.  {BILL_NO}")
    y -= 4.5 * mm
    c.setFillColor(GRAY)
    c.setFont(FONT, 8)
    c.drawString(left, y, "Particulars reconstructed from the original summary sheet")
    c.setFillColor(DARK)
    c.setFont(FONT, 9)
    c.drawRightString(right, y, f"Date  {BILL_DATE}    |    Currency  INR")

    y -= 8 * mm
    box_h = 22 * mm
    box_w = (right - left - 4 * mm) / 2
    rounded_rect(c, left, y - box_h, box_w, box_h, LIGHT)
    rounded_rect(c, left + box_w + 4 * mm, y - box_h, box_w, box_h, CREAM)
    c.setFillColor(TEAL)
    c.setFont(FONT_B, 7.5)
    c.drawString(left + 3.5 * mm, y - 5.5 * mm, "BILL TO")
    c.drawString(left + box_w + 7.5 * mm, y - 5.5 * mm, "NATURE OF BILL")
    c.setFillColor(DARK)
    c.setFont(FONT_B, 11)
    c.drawString(left + 3.5 * mm, y - 11.5 * mm, "Aditya Vishwakarma")
    c.setFont(FONT, 8.5)
    c.setFillColor(GRAY)
    c.drawString(left + 3.5 * mm, y - 16.5 * mm, "Customer / Payer")
    c.setFillColor(DARK)
    c.setFont(FONT_B, 10)
    c.drawString(left + box_w + 7.5 * mm, y - 11.5 * mm, "Carrier, labour & household supplies")
    c.setFont(FONT, 8)
    c.setFillColor(GRAY)
    c.drawString(left + box_w + 7.5 * mm, y - 16.5 * mm, "GST not charged — not shown on original sheet")

    y = y - box_h - 6 * mm

    # Table
    cols = [
        ("Sr.", 12 * mm),
        ("Description of goods / services", 78 * mm),
        ("Qty", 14 * mm),
        ("Unit", 16 * mm),
        ("Rate (Rs.)", 28 * mm),
        ("Amount (Rs.)", 30 * mm),
    ]
    table_w = sum(cw for _, cw in cols)
    row_h = 11.2 * mm
    header_h = 8 * mm
    x = left
    c.setFillColor(NAVY)
    c.rect(left, y - header_h, table_w, header_h, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont(FONT_B, 8)
    cx = left
    for title, cw in cols:
        if title.startswith("Rate") or title.startswith("Amount"):
            c.drawRightString(cx + cw - 2.5 * mm, y - 5.3 * mm, title)
        elif title in ("Sr.", "Qty", "Unit"):
            c.drawCentredString(cx + cw / 2, y - 5.3 * mm, title)
        else:
            c.drawString(cx + 2.5 * mm, y - 5.3 * mm, title)
        cx += cw
    y -= header_h

    for i, item in enumerate(ITEMS):
        bg = ROW_ALT if i % 2 else white
        c.setFillColor(bg)
        c.rect(left, y - row_h, table_w, row_h, fill=1, stroke=0)
        c.setStrokeColor(LINE)
        c.setLineWidth(0.3)
        c.line(left, y - row_h, left + table_w, y - row_h)
        vals = [
            (str(item["sr"]), "c"),
            (item["desc"], "l"),
            (item["qty"], "c"),
            (item["unit"], "c"),
            (item["rate"], "r"),
            (inr(item["amount"]), "r"),
        ]
        cx = left
        for (text, align), (_, cw) in zip(vals, cols):
            if text == item["desc"]:
                c.setFillColor(DARK)
                c.setFont(FONT_B, 9)
                c.drawString(cx + 2.5 * mm, y - 4.6 * mm, item["desc"])
                c.setFillColor(GRAY)
                c.setFont(FONT, 7.5)
                c.drawString(cx + 2.5 * mm, y - 8.6 * mm, item["detail"])
            else:
                c.setFillColor(DARK)
                c.setFont(FONT_B if align == "r" and text == inr(item["amount"]) else FONT, 9)
                if align == "c":
                    c.drawCentredString(cx + cw / 2, y - 6.6 * mm, text)
                elif align == "r":
                    c.drawRightString(cx + cw - 2.5 * mm, y - 6.6 * mm, text)
                else:
                    c.drawString(cx + 2.5 * mm, y - 6.6 * mm, text)
            cx += cw
        y -= row_h

    c.setStrokeColor(NAVY)
    c.setLineWidth(0.8)
    c.rect(left, y, table_w, header_h + row_h * len(ITEMS), fill=0, stroke=1)

    y -= 8 * mm
    tot_w = 78 * mm
    tot_x = right - tot_w
    # subtotal
    c.setFillColor(LIGHT)
    c.rect(tot_x, y - 8 * mm, tot_w, 8 * mm, fill=1, stroke=0)
    c.setStrokeColor(LINE)
    c.setLineWidth(0.4)
    c.rect(tot_x, y - 8 * mm, tot_w, 8 * mm, fill=0, stroke=1)
    c.setFillColor(DARK)
    c.setFont(FONT, 9)
    c.drawString(tot_x + 3 * mm, y - 5.3 * mm, "Sub-total (Sr. 1 to 7)")
    c.setFont(FONT_B, 9)
    c.drawRightString(tot_x + tot_w - 3 * mm, y - 5.3 * mm, f"Rs. {inr(STATED_TOTAL)}")
    y -= 8 * mm
    c.setFillColor(LIGHT)
    c.rect(tot_x, y - 8 * mm, tot_w, 8 * mm, fill=1, stroke=0)
    c.rect(tot_x, y - 8 * mm, tot_w, 8 * mm, fill=0, stroke=1)
    c.setFillColor(DARK)
    c.setFont(FONT, 9)
    c.drawString(tot_x + 3 * mm, y - 5.3 * mm, "Taxes / GST (not applied)")
    c.drawRightString(tot_x + tot_w - 3 * mm, y - 5.3 * mm, "Nil")
    y -= 8 * mm
    c.setFillColor(NAVY)
    c.rect(tot_x, y - 10 * mm, tot_w, 10 * mm, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont(FONT_B, 10.5)
    c.drawString(tot_x + 3 * mm, y - 6.5 * mm, "GRAND TOTAL")
    c.drawRightString(tot_x + tot_w - 3 * mm, y - 6.5 * mm, f"Rs. {inr(STATED_TOTAL)}")

    words_y = y - 10 * mm
    c.setFillColor(TEAL)
    c.setFont(FONT_B, 8)
    c.drawString(left, words_y - 2 * mm, "AMOUNT IN WORDS")
    c.setFillColor(DARK)
    c.setFont(FONT_B, 10)
    c.drawString(left, words_y - 7.5 * mm, amount_in_words(STATED_TOTAL))

    y = words_y - 16 * mm
    c.setFillColor(GREEN_BG)
    c.setStrokeColor(GREEN)
    c.setLineWidth(0.8)
    c.roundRect(left, y - 14 * mm, right - left, 14 * mm, 3, fill=1, stroke=1)
    c.setFillColor(GREEN)
    c.setFont(FONT_B, 9.5)
    c.drawCentredString(
        (left + right) / 2,
        y - 6 * mm,
        f"CALCULATION VERIFIED  —  Rs. {inr(STATED_TOTAL)}  |  Difference Rs. 0",
    )
    c.setFont(FONT, 8)
    c.drawCentredString(
        (left + right) / 2,
        y - 11 * mm,
        "Line-item sum matches the original printed total. Full working is on page 2.",
    )

    y -= 28 * mm
    c.setStrokeColor(LINE)
    c.setLineWidth(0.5)
    c.line(left, y + 10 * mm, right, y + 10 * mm)
    c.setFillColor(GRAY)
    c.setFont(FONT, 8)
    c.drawString(left, y + 3 * mm, "Prepared as per original particulars (Carrier & Aqua).")
    c.drawString(left, y - 1.5 * mm, "Spelling normalised: Saf Safai → Safai Labour; Dinning → Dining.")
    c.setFillColor(DARK)
    c.setFont(FONT, 9)
    c.drawRightString(right, y + 12 * mm, "For Receiver / Payer")
    c.setStrokeColor(DARK)
    c.setLineWidth(0.7)
    c.line(right - 58 * mm, y + 1 * mm, right, y + 1 * mm)
    c.setFont(FONT_B, 9)
    c.drawRightString(right, y - 4 * mm, "Aditya Vishwakarma")
    c.setFont(FONT, 8)
    c.setFillColor(GRAY)
    c.drawRightString(right, y - 8 * mm, "Signature")


def draw_check(c: canvas.Canvas) -> None:
    w, h = A4
    frame(c, 2, 2)
    left, right = 16 * mm, w - 16 * mm
    y = h - 18 * mm

    c.setFillColor(NAVY)
    c.setFont(FONT_B, 16)
    c.drawString(left, y, "Calculation Check Sheet")
    y -= 6 * mm
    c.setFillColor(GRAY)
    c.setFont(FONT, 9)
    c.drawString(left, y, "Independent addition of every line from the original PDF. Tick each running total by hand if you wish.")

    y -= 8 * mm
    cols = [
        ("Step", 14 * mm),
        ("Item", 48 * mm),
        ("Amount (Rs.)", 30 * mm),
        ("Operation", 52 * mm),
        ("Running total", 34 * mm),
    ]
    table_w = sum(cw for _, cw in cols)
    header_h = 8 * mm
    row_h = 9.2 * mm
    c.setFillColor(TEAL)
    c.rect(left, y - header_h, table_w, header_h, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont(FONT_B, 8)
    cx = left
    for title, cw in cols:
        if "Amount" in title or "Running" in title:
            c.drawRightString(cx + cw - 2.2 * mm, y - 5.2 * mm, title)
        elif title in ("Step",):
            c.drawCentredString(cx + cw / 2, y - 5.2 * mm, title)
        else:
            c.drawString(cx + 2.2 * mm, y - 5.2 * mm, title)
        cx += cw
    y -= header_h

    running = 0
    prev = 0
    for i, item in enumerate(ITEMS):
        running += item["amount"]
        bg = white if i % 2 else ROW_ALT
        c.setFillColor(bg)
        c.rect(left, y - row_h, table_w, row_h, fill=1, stroke=0)
        c.setStrokeColor(LINE)
        c.setLineWidth(0.3)
        c.line(left, y - row_h, left + table_w, y - row_h)
        op = f"Start  {inr(item['amount'])}" if i == 0 else f"{inr(prev)} + {inr(item['amount'])}"
        label = item["desc"] + ("  x 7 trips" if item["sr"] == 1 else "")
        vals = [
            (str(i + 1), "c", 14 * mm),
            (f"{item['sr']}. {label}", "l", 48 * mm),
            (inr(item["amount"]), "r", 30 * mm),
            (op, "c", 52 * mm),
            (inr(running), "r", 34 * mm),
        ]
        cx = left
        for text, align, cw in vals:
            c.setFillColor(DARK)
            c.setFont(FONT_B if align == "r" and text == inr(running) else FONT, 8.5)
            if align == "c":
                c.drawCentredString(cx + cw / 2, y - 5.8 * mm, text)
            elif align == "r":
                c.drawRightString(cx + cw - 2.2 * mm, y - 5.8 * mm, text)
            else:
                c.drawString(cx + 2.2 * mm, y - 5.8 * mm, text)
            cx += cw
        prev = running
        y -= row_h

    c.setStrokeColor(TEAL)
    c.setLineWidth(0.8)
    c.rect(left, y, table_w, header_h + row_h * len(ITEMS), fill=0, stroke=1)

    y -= 8 * mm
    c.setFillColor(NAVY)
    c.setFont(FONT_B, 11)
    c.drawString(left, y, "Quantity / rate notes")
    y -= 6 * mm
    c.setFillColor(DARK)
    c.setFont(FONT, 9)
    lines = [
        "1. Tractor Scrap — 7 trips: original amount is a lump sum of Rs. 16,000 (not 7 x a printed rate).",
        f"    Derived rate = 16,000 / 7 = Rs. 2,285.71 per trip.  Check: 2,285.71 x 7 = 15,999.97, rounded to Rs. 16,000.",
        "    This bill keeps the original lump-sum Rs. 16,000 so the total stays exact.",
        "2–7. Quantity taken as 1 (job / nos). Original sheet did not split rate and qty; amounts are used as given.",
    ]
    for line in lines:
        c.drawString(left, y, line)
        y -= 4.4 * mm

    y -= 3 * mm
    proof_w = 100 * mm
    proof_x = left
    rows = [
        ("Original printed total", f"Rs. {inr(STATED_TOTAL)}", False),
        ("Recomputed sum of 7 lines", f"Rs. {inr(running)}", False),
        ("Difference", "Rs. 0", False),
        ("RESULT", "CORRECT — NO ERROR", True),
    ]
    rh = 8 * mm
    for label, val, highlight in rows:
        if highlight:
            c.setFillColor(GREEN)
            c.rect(proof_x, y - rh, proof_w, rh, fill=1, stroke=0)
            c.setFillColor(white)
            c.setFont(FONT_B, 9)
        else:
            c.setFillColor(LIGHT)
            c.setStrokeColor(LINE)
            c.setLineWidth(0.4)
            c.rect(proof_x, y - rh, proof_w, rh, fill=1, stroke=1)
            c.setFillColor(DARK)
            c.setFont(FONT, 9)
        c.drawString(proof_x + 3 * mm, y - 5.3 * mm, label)
        c.setFont(FONT_B, 9)
        c.drawRightString(proof_x + proof_w - 3 * mm, y - 5.3 * mm, val)
        y -= rh

    # Vertical addition on the right
    add_x = left + proof_w + 12 * mm
    add_top = y + rh * 4
    c.setFillColor(NAVY)
    c.setFont(FONT_B, 10)
    c.drawString(add_x, add_top + 3 * mm, "Vertical addition")
    c.setFont(FONT, 9)
    c.setFillColor(DARK)
    ay = add_top - 4 * mm
    for item in ITEMS:
        c.drawRightString(add_x + 38 * mm, ay, inr(item["amount"]))
        ay -= 4.6 * mm
    c.setStrokeColor(NAVY)
    c.setLineWidth(0.8)
    c.line(add_x + 12 * mm, ay + 2.2 * mm, add_x + 38 * mm, ay + 2.2 * mm)
    c.setFillColor(GREEN)
    c.setFont(FONT_B, 10)
    c.drawRightString(add_x + 38 * mm, ay - 2 * mm, inr(STATED_TOTAL))

    y -= 10 * mm
    c.setFillColor(DARK)
    c.setFont(FONT, 9)
    c.drawString(
        left,
        y,
        f"16,000 + 9,000 + 7,000 + 17,700 + 1,775 + 1,450 + 84,700  =  Rs. {inr(STATED_TOTAL)}",
    )
    y -= 8 * mm
    c.setFillColor(GRAY)
    c.setFont(FONT, 8)
    c.drawString(
        left,
        y,
        "Prepared 23 August 2026 from uploaded file Carrier_7e2b.pdf. Figures copied without change except spelling.",
    )


def generate(path: Path) -> Path:
    total = sum(i["amount"] for i in ITEMS)
    if total != STATED_TOTAL:
        raise SystemExit(f"Internal error: sum {total} != stated {STATED_TOTAL}")
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setTitle("Carrier & Aqua — Bill CA/2026-27/001")
    c.setAuthor("Aditya Vishwakarma")
    c.setSubject("Consolidated bill with calculation check")
    draw_invoice(c)
    c.showPage()
    draw_check(c)
    c.save()
    return path


def main() -> None:
    here = Path(__file__).resolve().parent
    out = here / "Carrier_Aqua_Invoice.pdf"
    generate(out)
    print(f"Wrote {out}")
    print(f"Total Rs. {inr(STATED_TOTAL)}  |  {amount_in_words(STATED_TOTAL)}")


if __name__ == "__main__":
    main()

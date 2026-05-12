import os
import json
from datetime import datetime
from dotenv import load_dotenv
import pytz
from slack_sdk import WebClient
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.socket_mode.request import SocketModeRequest
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER

# ── CONFIG ──────────────────────────────────────────────────────
load_dotenv()
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID")
ABN = os.getenv("ABN")
BANK_NAME = os.getenv("BANK_NAME")
BSB = os.getenv("BSB")
ACCOUNT_NUMBER = os.getenv("ACCOUNT_NUMBER")
CLIENT_EMAIL = os.getenv("CLIENT_EMAIL")


INVOICE_STATE_FILE = "/home/ubuntu/invoice-bot/invoice_state.json"
SYDNEY_TZ = pytz.timezone("Australia/Sydney")

# ── INVOICE STATE ────────────────────────────────────────────────
def load_state():
    if os.path.exists(INVOICE_STATE_FILE):
        with open(INVOICE_STATE_FILE) as f:
            return json.load(f)
    raise FileNotFoundError(f"Invoice state file not found at {INVOICE_STATE_FILE}. Please create it manually.")

def save_state(state):
    with open(INVOICE_STATE_FILE, "w") as f:
        json.dump(state, f)

# ── PDF GENERATION ───────────────────────────────────────────────
def generate_invoice_pdf(invoice_num, date_str, sessions):
    filename = f"/home/ubuntu/invoice-bot/INV-{str(invoice_num).zfill(3)}_Yousif_Solaiman.pdf"
    doc = SimpleDocTemplate(filename, pagesize=A4,
                            rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)

    BLUE = colors.HexColor("#1A3C6E")
    LIGHT_BLUE = colors.HexColor("#F5F8FC")
    GRAY = colors.HexColor("#666666")
    WHITE = colors.white

    styles = getSampleStyleSheet()
    elements = []

    # Header
    header_data = [
        [Paragraph(f'<font color="#1A3C6E" size="28"><b>INVOICE</b></font>', styles['Normal']),
         Paragraph(f'<font color="#666666" size="9">Invoice Number</font><br/><b>INV-{str(invoice_num).zfill(3)}</b><br/><br/><font color="#666666" size="9">Date</font><br/><b>{date_str}</b>',
                   ParagraphStyle('right', alignment=TA_RIGHT, fontSize=10))]
    ]
    header_table = Table(header_data, colWidths=[100*mm, 70*mm])
    header_table.setStyle(TableStyle([
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LINEBELOW', (0, 0), (-1, 0), 1.5, BLUE),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 8*mm))

    # From / To
    from_to_data = [[
        Paragraph(f'<font color="#666666" size="8">FROM</font><br/><b>Yousif Solaiman</b><br/><font color="#666666">ABN: {ABN}</font>', styles['Normal']),
        Paragraph('<font color="#666666" size="8">TO</font><br/><b>ASKTUTORING</b>', styles['Normal'])
    ]]
    from_to_table = Table(from_to_data, colWidths=[85*mm, 85*mm])
    from_to_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(from_to_table)
    elements.append(Spacer(1, 10*mm))

    # Sessions table
    session_header = ['DESCRIPTION', 'DATE', 'TIME', 'SUBJECT', 'HRS', 'TYPE']
    session_rows = []
    total_hours = 0
    for s in sessions:
        session_rows.append([s['name'], s['date'], s['time'], s['subject'], s['hours'], s['type']])
        total_hours += float(s['hours'])

    table_data = [session_header] + session_rows
    col_widths = [40*mm, 25*mm, 32*mm, 28*mm, 20*mm, 25*mm]
    session_table = Table(table_data, colWidths=col_widths)
    session_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (4, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [LIGHT_BLUE, WHITE]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(session_table)
    elements.append(Spacer(1, 4*mm))

    # Total hours row
    total_data = [['', '', '', 'TOTAL HOURS', '', str(total_hours)]]
    total_table = Table(total_data, colWidths=col_widths)
    total_table.setStyle(TableStyle([
        ('BACKGROUND', (5, 0), (5, 0), BLUE),
        ('TEXTCOLOR', (5, 0), (5, 0), WHITE),
        ('TEXTCOLOR', (3, 0), (3, 0), BLUE),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (3, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(total_table)
    elements.append(Spacer(1, 4*mm))

    # Note
    elements.append(Paragraph(
        '<i><font color="#666666" size="8">Payment amount to be determined by ASKTUTORING based on session types.</font></i>',
        styles['Normal']))
    elements.append(Spacer(1, 10*mm))

    # Bank details
    bank_header_table = Table([['PAYMENT DETAILS']], colWidths=[170*mm])
    bank_header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BLUE),
        ('TEXTCOLOR', (0, 0), (-1, -1), WHITE),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(bank_header_table)

    bank_table = Table([
        ['Account Name:', BANK_NAME],
        ['BSB:', BSB],
        ['Account Number:', ACCOUNT_NUMBER],
    ], colWidths=[40*mm, 130*mm])
    bank_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_BLUE),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (0, -1), GRAY),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(bank_table)
    elements.append(Spacer(1, 10*mm))

    # Footer
    elements.append(Paragraph(
        '<i><font color="#666666">Thank you for the opportunity to work with you.</font></i>',
        ParagraphStyle('center', alignment=TA_CENTER, fontSize=9)))

    doc.build(elements)
    return filename

# ── SLACK BOT ────────────────────────────────────────────────────
web_client = WebClient(token=SLACK_BOT_TOKEN)
waiting_for_response = False

def send_question():
    web_client.chat_postMessage(
        channel=SLACK_CHANNEL_ID,
        text="👋 Hey Yousif! Did you have a tutoring session this week?\n\nReply with *yes* or *no*."
    )

def process_reply(text):
    global waiting_for_response
    reply = text.strip().lower()

    if reply == "yes":
        waiting_for_response = False
        state = load_state()
        invoice_num = state["next_invoice_num"]
        now_sydney = datetime.now(SYDNEY_TZ)
        date_str = now_sydney.strftime("%-d %B %Y")

        sessions = [{
            "name": "Thursday Group Session",
            "date": date_str,
            "time": "5:00 PM – 6:30 PM",
            "subject": "Stage 4 Maths",
            "hours": "1.5",
            "type": "Group"
        }]

        web_client.chat_postMessage(channel=SLACK_CHANNEL_ID, text="⏳ Generating your invoice...")
        filename = generate_invoice_pdf(invoice_num, date_str, sessions)

        state["next_invoice_num"] = invoice_num + 1
        save_state(state)

        with open(filename, "rb") as f:
            web_client.files_upload_v2(
                channel=SLACK_CHANNEL_ID,
                file=f,
                filename=os.path.basename(filename),
                initial_comment=f"✅ *INV-{str(invoice_num).zfill(3)} is ready!* Download and forward to {CLIENT_EMAIL} from Outlook."
            )

    elif reply == "no":
        waiting_for_response = False
        state = load_state()
        next_num = state["next_invoice_num"]
        web_client.chat_postMessage(
            channel=SLACK_CHANNEL_ID,
            text=f"👍 Got it — no invoice this week.\nNext week's invoice will be *INV-{str(next_num).zfill(3)}*."
        )

    else:
        web_client.chat_postMessage(
            channel=SLACK_CHANNEL_ID,
            text="Please reply with *yes* or *no*."
        )

def handle_event(client: SocketModeClient, req: SocketModeRequest):
    global waiting_for_response
    if req.type == "events_api":
        client.send_socket_mode_response(SocketModeResponse(envelope_id=req.envelope_id))
        event = req.payload.get("event", {})
        if event.get("type") == "message" and not event.get("bot_id") and waiting_for_response:
            process_reply(event.get("text", ""))

if __name__ == "__main__":
    waiting_for_response = True
    send_question()
    socket_client = SocketModeClient(app_token=SLACK_APP_TOKEN, web_client=web_client)
    socket_client.socket_mode_request_listeners.append(handle_event)
    socket_client.connect()
    import time
    while waiting_for_response:
        time.sleep(1)
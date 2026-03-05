"""
QR Forge MCP Server
====================
An MCP server that generates QR codes for URLs, WiFi, vCards, Email, and SMS,
and returns them as base64-encoded PDF files.

Usage:
    python server.py                  # Run with stdio transport (default)
    python server.py --port 8080      # Run with SSE transport on a specific port
"""

import argparse
import base64
import io
import json
import re
import sys
import uuid
from typing import Any

import qrcode
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

try:
    from mcp.server.fastmcp import FastMCP
    _mcp_available = True
except ImportError:
    _mcp_available = False

# ---------------------------------------------------------------------------
# MCP Server setup
# ---------------------------------------------------------------------------

if _mcp_available:
    try:
        mcp = FastMCP(
            "QR Forge",
            description="Generate QR codes for URLs, WiFi, vCards, Email, and SMS. Returns a downloadable PDF.",
        )
    except TypeError:
        # Older versions of FastMCP don't accept 'description'
        mcp = FastMCP("QR Forge")
    _tool_decorator = mcp.tool()
else:
    # Fallback: no-op decorator so functions are still callable without MCP installed
    mcp = None
    def _tool_decorator(func):
        return func

# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def _validate_phone(phone: str) -> bool:
    digits = re.sub(r"[\s\-\(\)\+]", "", phone)
    return digits.isdigit() and 7 <= len(digits) <= 15


def _sanitize_url(url: str) -> str:
    url = url.strip()
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = "https://" + url
    return url


# ---------------------------------------------------------------------------
# QR image + PDF generation helpers
# ---------------------------------------------------------------------------


def _make_qr_image(
    data: str,
    style: str = "square",
    fg_color: str = "#000000",
    bg_color: str = "#FFFFFF",
) -> io.BytesIO:
    """Generate a QR code PNG and return it as a BytesIO buffer."""
    from PIL import Image, ImageDraw

    qr = qrcode.QRCode(
        version=None,  # auto-size
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    # Generate the base image with standard factory (reliable across versions)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")

    # Apply style (rounded / circle dots) by redrawing modules
    if style in ("rounded", "circle"):
        matrix = qr.modules
        box_size = 10
        border = 4
        img_size = (len(matrix) + border * 2) * box_size
        styled = Image.new("RGBA", (img_size, img_size), _hex_to_rgba(bg_color))
        draw = ImageDraw.Draw(styled)

        fg = _hex_to_rgba(fg_color)
        for row_idx, row in enumerate(matrix):
            for col_idx, module in enumerate(row):
                if module:
                    x = (col_idx + border) * box_size
                    y = (row_idx + border) * box_size
                    if style == "circle":
                        margin = 1
                        draw.ellipse(
                            [x + margin, y + margin, x + box_size - margin, y + box_size - margin],
                            fill=fg,
                        )
                    else:  # rounded
                        radius = 3
                        draw.rounded_rectangle(
                            [x, y, x + box_size, y + box_size],
                            radius=radius,
                            fill=fg,
                        )
        img = styled
    else:
        # Square style: just recolour the pixels
        pixels = img.load()
        w, h = img.size
        fg = _hex_to_rgba(fg_color)
        bg = _hex_to_rgba(bg_color)
        for x in range(w):
            for y in range(h):
                r, g, b, a = pixels[x, y]
                if (r, g, b) == (0, 0, 0):
                    pixels[x, y] = fg
                elif (r, g, b) == (255, 255, 255):
                    pixels[x, y] = bg

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _hex_to_rgba(hex_color: str) -> tuple:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return (r, g, b, 255)


def _make_pdf(
    qr_buf: io.BytesIO,
    title: str,
    subtitle: str,
    raw_data: str,
) -> str:
    """Wrap the QR image in a clean PDF and return it as a base64 string."""
    pdf_buf = io.BytesIO()
    c = canvas.Canvas(pdf_buf, pagesize=letter)
    page_w, page_h = letter

    # Title
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(page_w / 2, page_h - 1.2 * inch, title)

    # Subtitle
    c.setFont("Helvetica", 12)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawCentredString(page_w / 2, page_h - 1.6 * inch, subtitle)

    # QR image (centred, 3.5 x 3.5 inches)
    qr_size = 3.5 * inch
    qr_x = (page_w - qr_size) / 2
    qr_y = (page_h - qr_size) / 2 - 0.3 * inch
    qr_buf.seek(0)
    c.drawImage(ImageReader(qr_buf), qr_x, qr_y, qr_size, qr_size)

    # Raw data text (small, below QR)
    c.setFont("Helvetica", 8)
    c.setFillColorRGB(0.55, 0.55, 0.55)
    display_data = raw_data if len(raw_data) <= 90 else raw_data[:87] + "..."
    c.drawCentredString(page_w / 2, qr_y - 0.35 * inch, display_data)

    # Footer
    c.setFont("Helvetica-Oblique", 9)
    c.setFillColorRGB(0.6, 0.6, 0.6)
    c.drawCentredString(page_w / 2, 0.6 * inch, "Generated by QR Forge")

    c.save()
    pdf_buf.seek(0)
    return base64.b64encode(pdf_buf.read()).decode("utf-8")


# ---------------------------------------------------------------------------
# Shared response builder
# ---------------------------------------------------------------------------


def _success(pdf_b64: str, qr_type: str, summary: str) -> dict[str, Any]:
    return {
        "success": True,
        "type": qr_type,
        "summary": summary,
        "pdf_base64": pdf_b64,
        "instructions": "Decode the pdf_base64 string and save it as a .pdf file to download your QR code.",
    }


def _error(message: str) -> dict[str, Any]:
    return {"success": False, "error": message}


# ===================================================================
# MCP TOOLS
# ===================================================================


@_tool_decorator
def generate_url_qr(
    url: str,
    style: str = "square",
    fg_color: str = "#000000",
    bg_color: str = "#FFFFFF",
) -> str:
    """
    Generate a QR code for a website URL and return it as a PDF.

    Args:
        url: The website URL (e.g. https://example.com). Will auto-add https:// if missing.
        style: QR dot style. Options: "square", "rounded", "circle". Default "square".
        fg_color: Foreground (dot) hex colour. Default "#000000".
        bg_color: Background hex colour. Default "#FFFFFF".

    Returns:
        JSON with success status and base64-encoded PDF.
    """
    url = _sanitize_url(url)
    try:
        qr_buf = _make_qr_image(url, style, fg_color, bg_color)
        pdf_b64 = _make_pdf(qr_buf, "Website QR Code", url, url)
        return json.dumps(_success(pdf_b64, "url", f"QR code for {url}"))
    except Exception as e:
        return json.dumps(_error(str(e)))


@_tool_decorator
def generate_wifi_qr(
    ssid: str,
    password: str,
    encryption: str = "WPA2",
    hidden: bool = False,
    style: str = "square",
    fg_color: str = "#000000",
    bg_color: str = "#FFFFFF",
) -> str:
    """
    Generate a QR code for WiFi network credentials and return it as a PDF.

    Args:
        ssid: The WiFi network name.
        password: The WiFi password.
        encryption: Encryption type. Options: "WPA", "WPA2", "WEP", "nopass". Default "WPA2".
        hidden: Whether the network is hidden. Default False.
        style: QR dot style. Options: "square", "rounded", "circle". Default "square".
        fg_color: Foreground hex colour. Default "#000000".
        bg_color: Background hex colour. Default "#FFFFFF".

    Returns:
        JSON with success status and base64-encoded PDF.
    """
    encryption = encryption.upper().strip()
    if encryption not in ("WPA", "WPA2", "WEP", "NOPASS"):
        return json.dumps(_error(f"Invalid encryption type: {encryption}. Use WPA, WPA2, WEP, or nopass."))

    # WPA and WPA2 use the same "WPA" token in the WiFi QR spec
    enc_token = "WPA" if encryption in ("WPA", "WPA2") else encryption
    hidden_flag = "true" if hidden else "false"

    wifi_string = f"WIFI:T:{enc_token};S:{ssid};P:{password};H:{hidden_flag};;"

    try:
        qr_buf = _make_qr_image(wifi_string, style, fg_color, bg_color)
        pdf_b64 = _make_pdf(qr_buf, "WiFi QR Code", f"Network: {ssid}", wifi_string)
        return json.dumps(_success(pdf_b64, "wifi", f"WiFi QR for network '{ssid}'"))
    except Exception as e:
        return json.dumps(_error(str(e)))


@_tool_decorator
def generate_vcard_qr(
    full_name: str,
    phone: str = "",
    email: str = "",
    organization: str = "",
    title: str = "",
    website: str = "",
    style: str = "square",
    fg_color: str = "#000000",
    bg_color: str = "#FFFFFF",
) -> str:
    """
    Generate a QR code for a vCard (contact card) and return it as a PDF.

    Args:
        full_name: Full name of the contact (required).
        phone: Phone number. At least phone or email must be provided.
        email: Email address. At least phone or email must be provided.
        organization: Company or organization name (optional).
        title: Job title (optional).
        website: Personal or company website (optional).
        style: QR dot style. Options: "square", "rounded", "circle". Default "square".
        fg_color: Foreground hex colour. Default "#000000".
        bg_color: Background hex colour. Default "#FFFFFF".

    Returns:
        JSON with success status and base64-encoded PDF.
    """
    if not full_name.strip():
        return json.dumps(_error("Full name is required."))
    if not phone.strip() and not email.strip():
        return json.dumps(_error("At least a phone number or email is required."))
    if phone and not _validate_phone(phone):
        return json.dumps(_error(f"Phone number looks invalid: {phone}. Please use digits, spaces, dashes, or parentheses."))
    if email and not _validate_email(email):
        return json.dumps(_error(f"Email looks invalid: {email}. Please check the format."))

    # Build vCard 3.0
    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"FN:{full_name.strip()}",
    ]
    # Split name into parts for N field
    parts = full_name.strip().split()
    if len(parts) >= 2:
        lines.append(f"N:{parts[-1]};{' '.join(parts[:-1])}")
    else:
        lines.append(f"N:{full_name.strip()};")

    if phone:
        lines.append(f"TEL:{phone.strip()}")
    if email:
        lines.append(f"EMAIL:{email.strip()}")
    if organization:
        lines.append(f"ORG:{organization.strip()}")
    if title:
        lines.append(f"TITLE:{title.strip()}")
    if website:
        lines.append(f"URL:{_sanitize_url(website)}")
    lines.append("END:VCARD")

    vcard_string = "\n".join(lines)

    try:
        qr_buf = _make_qr_image(vcard_string, style, fg_color, bg_color)
        pdf_b64 = _make_pdf(qr_buf, "Contact QR Code", full_name.strip(), vcard_string)
        return json.dumps(_success(pdf_b64, "vcard", f"vCard QR for {full_name.strip()}"))
    except Exception as e:
        return json.dumps(_error(str(e)))


@_tool_decorator
def generate_email_qr(
    email_address: str,
    subject: str = "",
    body: str = "",
    style: str = "square",
    fg_color: str = "#000000",
    bg_color: str = "#FFFFFF",
) -> str:
    """
    Generate a QR code for a pre-filled email and return it as a PDF.

    Args:
        email_address: The recipient email address (required).
        subject: Pre-filled subject line (optional).
        body: Pre-filled email body text (optional).
        style: QR dot style. Options: "square", "rounded", "circle". Default "square".
        fg_color: Foreground hex colour. Default "#000000".
        bg_color: Background hex colour. Default "#FFFFFF".

    Returns:
        JSON with success status and base64-encoded PDF.
    """
    if not _validate_email(email_address):
        return json.dumps(_error(f"Invalid email address: {email_address}"))

    from urllib.parse import quote

    params = []
    if subject:
        params.append(f"subject={quote(subject)}")
    if body:
        params.append(f"body={quote(body)}")

    mailto = f"mailto:{email_address}"
    if params:
        mailto += "?" + "&".join(params)

    try:
        qr_buf = _make_qr_image(mailto, style, fg_color, bg_color)
        subtitle = f"To: {email_address}"
        if subject:
            subtitle += f" | Subject: {subject}"
        pdf_b64 = _make_pdf(qr_buf, "Email QR Code", subtitle, mailto)
        return json.dumps(_success(pdf_b64, "email", f"Email QR for {email_address}"))
    except Exception as e:
        return json.dumps(_error(str(e)))


@_tool_decorator
def generate_sms_qr(
    phone_number: str,
    message: str = "",
    style: str = "square",
    fg_color: str = "#000000",
    bg_color: str = "#FFFFFF",
) -> str:
    """
    Generate a QR code for a pre-filled SMS message and return it as a PDF.

    Args:
        phone_number: The recipient phone number (required).
        message: Pre-filled text message content (optional).
        style: QR dot style. Options: "square", "rounded", "circle". Default "square".
        fg_color: Foreground hex colour. Default "#000000".
        bg_color: Background hex colour. Default "#FFFFFF".

    Returns:
        JSON with success status and base64-encoded PDF.
    """
    if not _validate_phone(phone_number):
        return json.dumps(_error(f"Invalid phone number: {phone_number}. Please use digits, spaces, dashes, or parentheses."))

    sms_string = f"smsto:{phone_number.strip()}"
    if message:
        sms_string += f":{message}"

    try:
        qr_buf = _make_qr_image(sms_string, style, fg_color, bg_color)
        subtitle = f"To: {phone_number.strip()}"
        if message:
            short_msg = message if len(message) <= 50 else message[:47] + "..."
            subtitle += f" | Message: {short_msg}"
        pdf_b64 = _make_pdf(qr_buf, "SMS QR Code", subtitle, sms_string)
        return json.dumps(_success(pdf_b64, "sms", f"SMS QR for {phone_number.strip()}"))
    except Exception as e:
        return json.dumps(_error(str(e)))


@_tool_decorator
def generate_event_qr(
    event_name: str,
    start_datetime: str,
    end_datetime: str,
    location: str = "",
    description: str = "",
    organizer_name: str = "",
    organizer_email: str = "",
    reminder_minutes: int = 15,
    style: str = "square",
    fg_color: str = "#000000",
    bg_color: str = "#FFFFFF",
) -> str:
    """
    Generate a QR code for a calendar event (iCalendar format) and return it as a PDF.
    Scanning the QR code will prompt the user to add the event to their phone calendar.

    Args:
        event_name: Name / title of the event (required).
        start_datetime: Start date and time in ISO 8601 format, e.g. "2026-03-15T14:00:00".
            Must include date and time. Timezone is assumed local unless a Z or offset is appended.
        end_datetime: End date and time in ISO 8601 format, e.g. "2026-03-15T16:00:00".
        location: Venue or address of the event (optional).
        description: Longer description or notes for the event (optional).
        organizer_name: Name of the event organizer (optional).
        organizer_email: Email of the event organizer (optional).
        reminder_minutes: Minutes before the event to trigger a reminder. Default 15. Set to 0 for no reminder.
        style: QR dot style. Options: "square", "rounded", "circle". Default "square".
        fg_color: Foreground hex colour. Default "#000000".
        bg_color: Background hex colour. Default "#FFFFFF".

    Returns:
        JSON with success status and base64-encoded PDF.
    """
    if not event_name.strip():
        return json.dumps(_error("Event name is required."))
    if not start_datetime.strip() or not end_datetime.strip():
        return json.dumps(_error("Both start and end date/time are required."))

    def _to_ical_dt(iso_str: str) -> str:
        """Convert ISO 8601 string to iCalendar DTSTART/DTEND format (basic)."""
        cleaned = iso_str.strip().replace("-", "").replace(":", "")
        # Remove any fractional seconds
        if "." in cleaned:
            cleaned = cleaned.split(".")[0]
        # Ensure it looks like a valid iCal datetime (at minimum YYYYMMDDTHHMMSS)
        if "T" not in cleaned:
            return cleaned + "T000000"
        return cleaned

    try:
        dt_start = _to_ical_dt(start_datetime)
        dt_end = _to_ical_dt(end_datetime)
    except Exception:
        return json.dumps(_error(
            "Could not parse date/time. Please use ISO 8601 format like 2026-03-15T14:00:00"
        ))

    # Build iCalendar string
    uid = str(uuid.uuid4())

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//QR Forge//EN",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTART:{dt_start}",
        f"DTEND:{dt_end}",
        f"SUMMARY:{event_name.strip()}",
    ]
    if location:
        lines.append(f"LOCATION:{location.strip()}")
    if description:
        lines.append(f"DESCRIPTION:{description.strip()}")
    if organizer_email:
        cn_part = f"CN={organizer_name.strip()}" if organizer_name else f"CN={organizer_email.strip()}"
        lines.append(f"ORGANIZER;{cn_part}:mailto:{organizer_email.strip()}")
    if reminder_minutes > 0:
        lines.extend([
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            f"DESCRIPTION:Reminder: {event_name.strip()}",
            f"TRIGGER:-PT{reminder_minutes}M",
            "END:VALARM",
        ])
    lines.extend([
        "END:VEVENT",
        "END:VCALENDAR",
    ])

    ical_string = "\r\n".join(lines)

    try:
        qr_buf = _make_qr_image(ical_string, style, fg_color, bg_color)

        # Build a nice subtitle
        # Parse display date from the ISO input
        display_date = start_datetime.strip()
        subtitle = f"{event_name.strip()}"
        if location:
            subtitle += f" @ {location.strip()}"

        pdf_b64 = _make_pdf(qr_buf, "Event QR Code", subtitle, ical_string)
        return json.dumps(_success(pdf_b64, "event", f"Calendar event QR for '{event_name.strip()}'"))
    except Exception as e:
        return json.dumps(_error(str(e)))


@_tool_decorator
def generate_medical_id_qr(
    full_name: str,
    date_of_birth: str = "",
    blood_type: str = "",
    allergies: str = "",
    medications: str = "",
    medical_conditions: str = "",
    emergency_contact_name: str = "",
    emergency_contact_phone: str = "",
    emergency_contact_relation: str = "",
    organ_donor: bool = False,
    additional_notes: str = "",
    style: str = "square",
    fg_color: str = "#000000",
    bg_color: str = "#FFFFFF",
) -> str:
    """
    Generate a QR code containing emergency medical information and return it as a PDF.
    Designed to be printed on a badge, wristband, wallet card, or phone case.
    Scanning reveals critical health info for first responders or medical staff.

    Args:
        full_name: Patient / wearer's full name (required).
        date_of_birth: Date of birth, e.g. "1990-05-14" (optional but recommended).
        blood_type: Blood type, e.g. "O+", "A-", "AB+" (optional but recommended).
        allergies: Comma-separated list of allergies, e.g. "Penicillin, Peanuts, Latex" (optional).
        medications: Comma-separated list of current medications, e.g. "Metformin 500mg, Lisinopril 10mg" (optional).
        medical_conditions: Comma-separated list of conditions, e.g. "Type 2 Diabetes, Hypertension" (optional).
        emergency_contact_name: Name of emergency contact (optional but recommended).
        emergency_contact_phone: Phone number of emergency contact (optional but recommended).
        emergency_contact_relation: Relationship, e.g. "Spouse", "Parent", "Sibling" (optional).
        organ_donor: Whether the person is a registered organ donor. Default False.
        additional_notes: Any other critical info, e.g. "DNR order on file", "Pacemaker installed" (optional).
        style: QR dot style. Options: "square", "rounded", "circle". Default "square".
        fg_color: Foreground hex colour. Default "#000000" (consider using "#CC0000" red for medical).
        bg_color: Background hex colour. Default "#FFFFFF".

    Returns:
        JSON with success status and base64-encoded PDF.
    """
    if not full_name.strip():
        return json.dumps(_error("Full name is required for a medical ID."))
    if emergency_contact_phone and not _validate_phone(emergency_contact_phone):
        return json.dumps(_error(
            f"Emergency contact phone looks invalid: {emergency_contact_phone}. "
            "Please use digits, spaces, dashes, or parentheses."
        ))

    # Blood type validation
    valid_blood_types = {
        "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-",
        "a+", "a-", "b+", "b-", "ab+", "ab-", "o+", "o-",
    }
    if blood_type and blood_type.strip() not in valid_blood_types:
        return json.dumps(_error(
            f"Unrecognized blood type: {blood_type}. "
            "Valid options: A+, A-, B+, B-, AB+, AB-, O+, O-"
        ))

    # Build a structured plain-text medical card
    # Using a simple, scannable text format that any QR reader can display
    sections = []
    sections.append("=== EMERGENCY MEDICAL ID ===")
    sections.append(f"Name: {full_name.strip()}")

    if date_of_birth:
        sections.append(f"DOB: {date_of_birth.strip()}")
    if blood_type:
        sections.append(f"Blood Type: {blood_type.strip().upper()}")

    if allergies:
        sections.append(f"\nALLERGIES: {allergies.strip()}")
    else:
        sections.append("\nALLERGIES: None reported")

    if medications:
        sections.append(f"MEDICATIONS: {medications.strip()}")

    if medical_conditions:
        sections.append(f"CONDITIONS: {medical_conditions.strip()}")

    if organ_donor:
        sections.append("ORGAN DONOR: Yes")

    if emergency_contact_name or emergency_contact_phone:
        sections.append("\n--- EMERGENCY CONTACT ---")
        if emergency_contact_name:
            contact_line = emergency_contact_name.strip()
            if emergency_contact_relation:
                contact_line += f" ({emergency_contact_relation.strip()})"
            sections.append(f"Contact: {contact_line}")
        if emergency_contact_phone:
            sections.append(f"Phone: {emergency_contact_phone.strip()}")

    if additional_notes:
        sections.append(f"\nNOTES: {additional_notes.strip()}")

    sections.append("\n[Generated by QR Forge]")

    medical_string = "\n".join(sections)

    try:
        qr_buf = _make_qr_image(medical_string, style, fg_color, bg_color)

        subtitle = full_name.strip()
        if blood_type:
            subtitle += f" | Blood Type: {blood_type.strip().upper()}"

        pdf_b64 = _make_pdf(qr_buf, "Emergency Medical ID", subtitle, medical_string)
        return json.dumps(_success(pdf_b64, "medical_id", f"Medical ID QR for {full_name.strip()}"))
    except Exception as e:
        return json.dumps(_error(str(e)))


@_tool_decorator
def list_supported_types() -> str:
    """
    List all supported QR code types and the required fields for each.

    Returns:
        JSON describing each QR code type and its parameters.
    """
    types = {
        "url": {
            "description": "Website or link QR code",
            "required_fields": ["url"],
            "optional_fields": ["style", "fg_color", "bg_color"],
        },
        "wifi": {
            "description": "WiFi network credentials QR code",
            "required_fields": ["ssid", "password"],
            "optional_fields": ["encryption", "hidden", "style", "fg_color", "bg_color"],
        },
        "vcard": {
            "description": "Contact card (vCard) QR code",
            "required_fields": ["full_name", "phone OR email"],
            "optional_fields": ["organization", "title", "website", "style", "fg_color", "bg_color"],
        },
        "email": {
            "description": "Pre-filled email QR code",
            "required_fields": ["email_address"],
            "optional_fields": ["subject", "body", "style", "fg_color", "bg_color"],
        },
        "sms": {
            "description": "Pre-filled SMS message QR code",
            "required_fields": ["phone_number"],
            "optional_fields": ["message", "style", "fg_color", "bg_color"],
        },
        "event": {
            "description": "Calendar event QR code (iCalendar). Scanning adds the event to the phone calendar.",
            "required_fields": ["event_name", "start_datetime", "end_datetime"],
            "optional_fields": [
                "location", "description", "organizer_name", "organizer_email",
                "reminder_minutes", "style", "fg_color", "bg_color",
            ],
        },
        "medical_id": {
            "description": "Emergency medical ID QR code. Contains critical health info for first responders.",
            "required_fields": ["full_name"],
            "optional_fields": [
                "date_of_birth", "blood_type", "allergies", "medications",
                "medical_conditions", "emergency_contact_name", "emergency_contact_phone",
                "emergency_contact_relation", "organ_donor", "additional_notes",
                "style", "fg_color", "bg_color",
            ],
        },
    }
    style_info = {
        "available_styles": ["square", "rounded", "circle"],
        "default_style": "square",
        "color_format": "Hex color codes (e.g. #FF5733)",
    }
    return json.dumps({"types": types, "styling": style_info})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os

    if not _mcp_available:
        print("ERROR: The 'mcp' package is not installed.")
        print("To run the MCP server:  pip install mcp")
        print("To test QR generation:  python test_local.py  (works without mcp)")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="QR Forge MCP Server")
    parser.add_argument("--port", type=int, default=None, help="Port for SSE transport (omit for stdio)")
    args = parser.parse_args()

    port = args.port or int(os.environ.get("PORT", 0))

    if port:
        # Try different FastMCP.run() signatures across mcp package versions
        try:
            mcp.run(transport="sse", sse_params={"port": port})
        except TypeError:
            try:
                mcp.settings.port = port
                mcp.run(transport="sse")
            except (TypeError, AttributeError):
                try:
                    mcp.run(transport="sse", port=port)
                except TypeError:
                    # Last resort: set host/port via environment and run
                    os.environ["FASTMCP_PORT"] = str(port)
                    os.environ["HOST"] = "0.0.0.0"
                    os.environ["PORT"] = str(port)
                    mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")
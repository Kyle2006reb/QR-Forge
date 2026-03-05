"""
QR Forge - FastMCP Server
==================================
Run this file to start the SSE streaming server required by Athena.
Command: mcp run server.py
"""
import os
from mcp.server.fastmcp import FastMCP
from qr_core import (
    generate_url_qr,
    generate_wifi_qr,
    generate_vcard_qr,
    generate_email_qr,
    generate_sms_qr,
    generate_event_qr,
    generate_medical_id_qr
)

# Initialize the FastMCP server
mcp = FastMCP("QR Forge")

def _format_response(result: dict) -> str:
    """Helper to standardize tool output for the LLM."""
    if result.get("success"):
        return f"SUCCESS\nSummary: {result['summary']}\nPDF_BASE64:\n{result['pdf_base64']}"
    return f"ERROR\nFailed to generate QR code: {result.get('error')}"

@mcp.tool()
def create_url_qr(url: str, style: str = "square", fg_color: str = "#000000", bg_color: str = "#FFFFFF") -> str:
    """Generate a QR code for a website URL."""
    return _format_response(generate_url_qr(url, style, fg_color, bg_color))

@mcp.tool()
def create_wifi_qr(ssid: str, password: str, encryption: str = "WPA2", hidden: bool = False, style: str = "square", fg_color: str = "#000000", bg_color: str = "#FFFFFF") -> str:
    """Generate a QR code for a WiFi network."""
    return _format_response(generate_wifi_qr(ssid, password, encryption, hidden, style, fg_color, bg_color))

@mcp.tool()
def create_vcard_qr(full_name: str, phone: str = "", email: str = "", organization: str = "", title: str = "", website: str = "", style: str = "square", fg_color: str = "#000000", bg_color: str = "#FFFFFF") -> str:
    """Generate a vCard contact QR code."""
    return _format_response(generate_vcard_qr(full_name, phone, email, organization, title, website, style, fg_color, bg_color))

@mcp.tool()
def create_email_qr(email_address: str, subject: str = "", body: str = "", style: str = "square", fg_color: str = "#000000", bg_color: str = "#FFFFFF") -> str:
    """Generate a QR code that drafts an email."""
    return _format_response(generate_email_qr(email_address, subject, body, style, fg_color, bg_color))

@mcp.tool()
def create_sms_qr(phone_number: str, message: str = "", style: str = "square", fg_color: str = "#000000", bg_color: str = "#FFFFFF") -> str:
    """Generate a QR code that drafts an SMS text message."""
    return _format_response(generate_sms_qr(phone_number, message, style, fg_color, bg_color))

@mcp.tool()
def create_event_qr(event_name: str, start_datetime: str, end_datetime: str, location: str = "", description: str = "", organizer_name: str = "", organizer_email: str = "", reminder_minutes: int = 15, style: str = "square", fg_color: str = "#000000", bg_color: str = "#FFFFFF") -> str:
    """Generate a QR code for an iCalendar event."""
    return _format_response(generate_event_qr(event_name, start_datetime, end_datetime, location, description, organizer_name, organizer_email, reminder_minutes, style, fg_color, bg_color))

@mcp.tool()
def create_medical_id_qr(full_name: str, date_of_birth: str = "", blood_type: str = "", allergies: str = "", medications: str = "", medical_conditions: str = "", emergency_contact_name: str = "", emergency_contact_phone: str = "", emergency_contact_relation: str = "", organ_donor: bool = False, additional_notes: str = "", style: str = "square", fg_color: str = "#000000", bg_color: str = "#FFFFFF") -> str:
    """Generate a QR code for an Emergency Medical ID."""
    return _format_response(generate_medical_id_qr(full_name, date_of_birth, blood_type, allergies, medications, medical_conditions, emergency_contact_name, emergency_contact_phone, emergency_contact_relation, organ_donor, additional_notes, style, fg_color, bg_color))

if __name__ == "__main__":
    # Start the server using standard stdio for local debugging, or use `mcp run server.py` for SSE
    mcp.run()


if __name__ == "__main__":
    # Render assigns a dynamic port using the $PORT environment variable
    port = int(os.environ.get("PORT", 8000))
    
    # Start the server explicitly in SSE streaming mode
    mcp.run(transport="sse", host="0.0.0.0", port=port)
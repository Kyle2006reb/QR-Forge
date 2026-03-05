"""
QR Forge - Vercel Serverless API
==================================
Single endpoint: POST /api/generate

Request body (JSON):
{
    "type": "url",          // required: url, wifi, vcard, email, sms, event, medical_id
    "url": "https://...",   // fields vary by type - see /api/generate?info=true
    "style": "rounded",     // optional: square, rounded, circle
    "fg_color": "#000000",  // optional: hex foreground color
    "bg_color": "#FFFFFF"   // optional: hex background color
}

Response (JSON):
{
    "success": true,
    "type": "url",
    "summary": "QR code for https://...",
    "pdf_base64": "JVBERi0xLjQK...",
    "instructions": "Decode the pdf_base64 string and save as .pdf"
}
"""

import json
import sys
import os
from http.server import BaseHTTPRequestHandler

# Add parent directory to path so we can import qr_core
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qr_core import GENERATORS, list_supported_types, _error


class handler(BaseHTTPRequestHandler):

    def _send_json(self, data: dict, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self._send_json({}, 204)

    def do_GET(self):
        """GET /api/generate - returns supported types and usage info."""
        info = list_supported_types()
        info["usage"] = {
            "method": "POST",
            "endpoint": "/api/generate",
            "body": {
                "type": "(required) one of: url, wifi, vcard, email, sms, event, medical_id",
                "...fields": "See 'types' above for required/optional fields per type",
                "style": "(optional) square, rounded, or circle",
                "fg_color": "(optional) hex color like #000000",
                "bg_color": "(optional) hex color like #FFFFFF",
            },
        }
        self._send_json(info)

    def do_POST(self):
        """POST /api/generate - generate a QR code."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                self._send_json(_error("Empty request body. Send JSON with at least a 'type' field."), 400)
                return

            raw_body = self.rfile.read(content_length)
            body = json.loads(raw_body)
        except (json.JSONDecodeError, ValueError):
            self._send_json(_error("Invalid JSON in request body."), 400)
            return

        qr_type = body.get("type", "").strip().lower()
        if not qr_type:
            self._send_json(_error("Missing 'type' field. Options: url, wifi, vcard, email, sms, event, medical_id"), 400)
            return

        generator = GENERATORS.get(qr_type)
        if not generator:
            self._send_json(
                _error(f"Unknown type: '{qr_type}'. Valid types: {', '.join(GENERATORS.keys())}"),
                400,
            )
            return

        # Extract shared styling params
        style = body.get("style", "square")
        fg_color = body.get("fg_color", "#000000")
        bg_color = body.get("bg_color", "#FFFFFF")

        # Build kwargs for the specific generator
        kwargs = {"style": style, "fg_color": fg_color, "bg_color": bg_color}

        # Map request body fields to function parameters
        field_mappings = {
            "url": ["url"],
            "wifi": ["ssid", "password", "encryption", "hidden"],
            "vcard": ["full_name", "phone", "email", "organization", "title", "website"],
            "email": ["email_address", "subject", "body"],
            "sms": ["phone_number", "message"],
            "event": [
                "event_name", "start_datetime", "end_datetime", "location",
                "description", "organizer_name", "organizer_email", "reminder_minutes",
            ],
            "medical_id": [
                "full_name", "date_of_birth", "blood_type", "allergies", "medications",
                "medical_conditions", "emergency_contact_name", "emergency_contact_phone",
                "emergency_contact_relation", "organ_donor", "additional_notes",
            ],
        }

        for field in field_mappings.get(qr_type, []):
            if field in body:
                kwargs[field] = body[field]

        try:
            result = generator(**kwargs)
            status = 200 if result.get("success") else 400
            self._send_json(result, status)
        except TypeError as e:
            self._send_json(_error(f"Missing or invalid parameter: {e}"), 400)
        except Exception as e:
            self._send_json(_error(f"Server error: {e}"), 500)

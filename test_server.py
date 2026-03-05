"""
QR Forge - Local API Server
=============================
Run this to test the API locally before deploying to Vercel.

Usage:
    python test_server.py

Then test with curl or your browser:
    GET  http://localhost:8000/api/generate          -> shows usage info
    POST http://localhost:8000/api/generate           -> generates a QR code

Example curl commands:

    # URL QR
    curl -X POST http://localhost:8000/api/generate \
      -H "Content-Type: application/json" \
      -d "{\"type\": \"url\", \"url\": \"https://github.com\"}"

    # WiFi QR
    curl -X POST http://localhost:8000/api/generate \
      -H "Content-Type: application/json" \
      -d "{\"type\": \"wifi\", \"ssid\": \"MyWiFi\", \"password\": \"secret123\"}"

    # Medical ID QR
    curl -X POST http://localhost:8000/api/generate \
      -H "Content-Type: application/json" \
      -d "{\"type\": \"medical_id\", \"full_name\": \"Jane Doe\", \"blood_type\": \"O+\", \"allergies\": \"Penicillin\", \"fg_color\": \"#CC0000\"}"
"""

import json
import sys
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qr_core import GENERATORS, list_supported_types, _error


class LocalHandler(BaseHTTPRequestHandler):

    def _send_json(self, data: dict, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    def do_OPTIONS(self):
        self._send_json({}, 204)

    def do_GET(self):
        info = list_supported_types()
        info["usage"] = {
            "method": "POST",
            "endpoint": "/api/generate",
            "example": {
                "type": "url",
                "url": "https://github.com",
                "style": "rounded",
            },
        }
        self._send_json(info)

    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                self._send_json(_error("Empty request body."), 400)
                return
            raw_body = self.rfile.read(content_length)
            body = json.loads(raw_body)
        except (json.JSONDecodeError, ValueError):
            self._send_json(_error("Invalid JSON."), 400)
            return

        qr_type = body.get("type", "").strip().lower()
        if not qr_type:
            self._send_json(_error("Missing 'type' field."), 400)
            return

        generator = GENERATORS.get(qr_type)
        if not generator:
            self._send_json(_error(f"Unknown type: '{qr_type}'."), 400)
            return

        kwargs = {
            "style": body.get("style", "square"),
            "fg_color": body.get("fg_color", "#000000"),
            "bg_color": body.get("bg_color", "#FFFFFF"),
        }

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


def main():
    port = 8000
    print(f"QR Forge API running at http://localhost:{port}")
    print(f"  GET  http://localhost:{port}/api/generate   -> usage info")
    print(f"  POST http://localhost:{port}/api/generate   -> generate QR")
    print()
    print("Example:")
    print(f'  curl -X POST http://localhost:{port}/api/generate \\')
    print(f'    -H "Content-Type: application/json" \\')
    print(f'    -d \'{{"type": "url", "url": "https://github.com"}}\'')
    print()
    print("Press Ctrl+C to stop.")
    print()

    server = HTTPServer(("", port), LocalHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()

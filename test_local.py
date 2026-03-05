"""
QR Forge - Local Test Script
==============================
Run this to verify QR code generation works on your machine
before starting the MCP server.

Usage:
    python test_local.py

This will generate 5 sample QR codes (one per type) as PDFs
in a "test_output/" folder.
"""

import base64
import json
import os
import sys

# Add parent dir to path so we can import server functions
sys.path.insert(0, os.path.dirname(__file__))

try:
    from server import (
        generate_email_qr,
        generate_event_qr,
        generate_medical_id_qr,
        generate_sms_qr,
        generate_url_qr,
        generate_vcard_qr,
        generate_wifi_qr,
        list_supported_types,
    )
except ImportError as e:
    print(f"ERROR: Failed to import server functions: {e}")
    print()
    print("Make sure you have the required packages installed:")
    print("  pip install qrcode[pil] reportlab Pillow")
    print()
    print("Note: The 'mcp' package is NOT required for testing.")
    sys.exit(1)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "test_output")


def save_pdf(result_json: str, filename: str) -> bool:
    """Parse the tool result and save the PDF if successful."""
    result = json.loads(result_json)

    if not result.get("success"):
        print(f"  FAILED: {result.get('error', 'Unknown error')}")
        return False

    pdf_bytes = base64.b64decode(result["pdf_base64"])
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(pdf_bytes)

    size_kb = len(pdf_bytes) / 1024
    print(f"  OK: Saved {filepath} ({size_kb:.1f} KB)")
    return True


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    passed = 0
    total = 0

    # -------------------------------------------------------------------
    print("\n=== QR Forge Local Tests ===\n")

    # Test 1: URL
    print("[1/6] URL QR Code")
    total += 1
    result = generate_url_qr(url="https://github.com", style="rounded")
    if save_pdf(result, "test_url.pdf"):
        passed += 1

    # Test 2: WiFi
    print("[2/6] WiFi QR Code")
    total += 1
    result = generate_wifi_qr(ssid="MyHomeWiFi", password="supersecret123", encryption="WPA2")
    if save_pdf(result, "test_wifi.pdf"):
        passed += 1

    # Test 3: vCard
    print("[3/6] vCard QR Code")
    total += 1
    result = generate_vcard_qr(
        full_name="Jane Doe",
        phone="+1-555-123-4567",
        email="jane@example.com",
        organization="Acme Corp",
        title="CTO",
        website="https://janedoe.dev",
        style="circle",
    )
    if save_pdf(result, "test_vcard.pdf"):
        passed += 1

    # Test 4: Email
    print("[4/6] Email QR Code")
    total += 1
    result = generate_email_qr(
        email_address="hello@example.com",
        subject="Quick Question",
        body="Hi, I had a question about your product.",
    )
    if save_pdf(result, "test_email.pdf"):
        passed += 1

    # Test 5: SMS
    print("[5/8] SMS QR Code")
    total += 1
    result = generate_sms_qr(
        phone_number="+1-555-987-6543",
        message="Hey! Are we still on for lunch?",
        style="rounded",
        fg_color="#1a73e8",
    )
    if save_pdf(result, "test_sms.pdf"):
        passed += 1

    # Test 6: Calendar Event
    print("[6/8] Event / Calendar QR Code")
    total += 1
    result = generate_event_qr(
        event_name="Athena AI Contest Finals",
        start_datetime="2026-03-06T15:00:00",
        end_datetime="2026-03-06T17:00:00",
        location="Online (Zoom)",
        description="Present QR Forge to the judges. Good luck!",
        organizer_email="contest@athenachat.bot",
        reminder_minutes=30,
        style="rounded",
        fg_color="#6d28d9",
    )
    if save_pdf(result, "test_event.pdf"):
        passed += 1

    # Test 7: Emergency Medical ID
    print("[7/8] Emergency Medical ID QR Code")
    total += 1
    result = generate_medical_id_qr(
        full_name="Alex Rivera",
        date_of_birth="1988-11-22",
        blood_type="O+",
        allergies="Penicillin, Sulfa drugs, Bee stings",
        medications="Metformin 500mg (twice daily), Lisinopril 10mg",
        medical_conditions="Type 2 Diabetes, Hypertension",
        emergency_contact_name="Maria Rivera",
        emergency_contact_phone="+1-555-444-3210",
        emergency_contact_relation="Spouse",
        organ_donor=True,
        additional_notes="Pacemaker installed (2024). DNR order on file.",
        fg_color="#CC0000",
    )
    if save_pdf(result, "test_medical_id.pdf"):
        passed += 1

    # Test 8: List supported types
    print("[8/8] List Supported Types")
    total += 1
    result = list_supported_types()
    types = json.loads(result)
    if "types" in types and len(types["types"]) == 7:
        print(f"  OK: {len(types['types'])} types returned")
        passed += 1
    else:
        print(f"  FAILED: Expected 7 types, got {len(types.get('types', {}))}")

    # -------------------------------------------------------------------
    print(f"\n=== Results: {passed}/{total} passed ===")
    if passed == total:
        print("All tests passed! Your MCP server is ready to go.\n")
    else:
        print("Some tests failed. Check the errors above.\n")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())

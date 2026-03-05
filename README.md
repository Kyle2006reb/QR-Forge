# QR Forge - Vercel Deployment

A serverless QR code generation API. Generates QR codes for URLs, WiFi, vCards, Email, SMS, Calendar Events, and Emergency Medical IDs. Returns results as base64-encoded PDFs.

---

## Project Structure

```
qr-forge-vercel/
  api/
    generate.py       Vercel serverless function (the API endpoint)
  qr_core.py          Core QR generation logic
  test_server.py      Local HTTP server for testing
  requirements.txt    Python dependencies
  vercel.json         Vercel routing config
```

---

## Test Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Start local server
python test_server.py
```

Then in another terminal:

```bash
# Test URL QR
curl -X POST http://localhost:8000/api/generate ^
  -H "Content-Type: application/json" ^
  -d "{\"type\": \"url\", \"url\": \"https://github.com\"}"

# Test WiFi QR
curl -X POST http://localhost:8000/api/generate ^
  -H "Content-Type: application/json" ^
  -d "{\"type\": \"wifi\", \"ssid\": \"MyWiFi\", \"password\": \"secret123\"}"

# Test Medical ID
curl -X POST http://localhost:8000/api/generate ^
  -H "Content-Type: application/json" ^
  -d "{\"type\": \"medical_id\", \"full_name\": \"Jane Doe\", \"blood_type\": \"O+\", \"allergies\": \"Penicillin\", \"fg_color\": \"#CC0000\"}"

# See all available types
curl http://localhost:8000/api/generate
```

The response will include a `pdf_base64` field. To save it as a PDF, you can use:

```python
import base64, json
result = json.loads(response_text)
with open("qr.pdf", "wb") as f:
    f.write(base64.b64decode(result["pdf_base64"]))
```

---

## Deploy to Vercel

### Option A: Vercel CLI (recommended)

```bash
# Install Vercel CLI
npm install -g vercel

# Deploy (from the qr-forge-vercel folder)
cd qr-forge-vercel
vercel

# Follow the prompts. Once deployed, your API will be at:
# https://your-project-name.vercel.app/api/generate
```

### Option B: GitHub integration

1. Push this folder to a GitHub repo
2. Go to vercel.com and import the repo
3. Vercel auto-detects the config and deploys

---

## API Reference

### GET /api/generate

Returns all supported QR types and their required fields.

### POST /api/generate

Generate a QR code. Send JSON body with these fields:

**Always required:**
- `type` - one of: `url`, `wifi`, `vcard`, `email`, `sms`, `event`, `medical_id`

**Always optional:**
- `style` - `"square"` (default), `"rounded"`, or `"circle"`
- `fg_color` - hex foreground color, default `"#000000"`
- `bg_color` - hex background color, default `"#FFFFFF"`

**Per-type required fields:**

| Type         | Required Fields                                  |
|-------------|--------------------------------------------------|
| `url`       | `url`                                            |
| `wifi`      | `ssid`, `password`                               |
| `vcard`     | `full_name`, and `phone` or `email`              |
| `email`     | `email_address`                                  |
| `sms`       | `phone_number`                                   |
| `event`     | `event_name`, `start_datetime`, `end_datetime`   |
| `medical_id`| `full_name`                                      |

**Response:**

```json
{
  "success": true,
  "type": "url",
  "summary": "QR code for https://github.com",
  "pdf_base64": "JVBERi0xLjQK...",
  "instructions": "Decode the pdf_base64 string and save it as a .pdf file."
}
```

---

## Connecting to Athena AI

Once deployed, your API URL will be something like:

```
https://qr-forge.vercel.app/api/generate
```

Use this URL in your Athena agent's MCP/tool configuration to connect the QR generation backend to your chat agent.

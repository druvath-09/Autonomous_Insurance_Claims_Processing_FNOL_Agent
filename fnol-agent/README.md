# FNOL Claims Processing Agent

An autonomous **First Notice of Loss (FNOL)** processing system that extracts structured data from ACORD Automobile Loss Notice PDFs, classifies claims, and routes them intelligently.

## 🎯 What it Does

1. **Accepts** PDF uploads via a FastAPI REST endpoint
2. **Extracts** structured claim data using a 3-tier hybrid strategy:
   - **Form fields** (PyMuPDF widgets) — highest fidelity
   - **Text extraction** (pdfplumber) — broad coverage
   - **OCR fallback** (Tesseract) — only when text is sparse (<100 chars)
3. **Validates** extracted data against mandatory fields
4. **Classifies** the claim type (damage / injury / theft)
5. **Routes** claims based on priority business rules
6. **Returns** a structured JSON response with confidence score

---

## ⚙️ Tech Stack

| Component     | Library       |
|---------------|---------------|
| API Framework | FastAPI       |
| Form fields   | PyMuPDF (fitz)|
| Text parsing  | pdfplumber    |
| OCR fallback  | pytesseract   |
| PDF → images  | pdf2image     |
| Pattern match | regex (stdlib)|

---

## 📦 Project Structure

```
fnol-agent/
├── main.py            # FastAPI app + /process-claim/ endpoint
├── extractor.py       # Hybrid extraction pipeline
├── utils.py           # Routing, validation, confidence scoring
├── requirements.txt   # Python dependencies
├── Sample1.pdf        # Test ACORD form (filled)
└── sample.pdf         # Blank ACORD template
```

---

## 🚀 Setup & Run

### Prerequisites

- Python 3.10+
- Tesseract OCR (`brew install tesseract` on macOS)
- Poppler (`brew install poppler` on macOS — needed for `pdf2image`)

### Install

```bash
cd fnol-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Run the API

```bash
uvicorn main:app --reload --port 8000
```

### Test with curl

```bash
curl -X POST http://127.0.0.1:8000/process-claim/ \
  -F "file=@Sample1.pdf" | python3 -m json.tool
```

### Quick CLI Test (no server needed)

```bash
python main.py
```

### Run the Test Suite

The test suite dynamically generates test PDFs covering all routing scenarios, runs them against the API, and cleans up the files afterwards.

Make sure the API is running, then run:

```bash
python test_suite.py
```

---

## 📡 API Endpoints

### `GET /`
Health check.

### `POST /process-claim/`
Upload a PDF and get structured extraction results.

**Request:** `multipart/form-data` with a `file` field containing a PDF.

**Response:**
```json
{
  "extractedFields": {
    "policy_number": "POL123456",
    "policyholder_name": "Rajesh",
    "effective_dates": null,
    "date_of_loss": "04/25/2026",
    "time": null,
    "location": "Bangalore, India, Karnataka, 505432",
    "description": "Minor car accident, rear bumper damaged, no injury",
    "claimant": null,
    "third_parties": null,
    "contact": "9876054321",
    "asset_type": "VEHICLE",
    "asset_id": null,
    "estimated_damage": "18000",
    "claim_type": "damage",
    "attachments": "yes",
    "initial_estimate": "18000"
  },
  "missingFields": [],
  "recommendedRoute": "Fast-track",
  "reasoning": "Estimated damage (₹18,000) is below ₹25,000 threshold",
  "confidence": "High"
}
```

---

## 🧠 Extraction Pipeline

```
PDF Upload
    │
    ├─ Step 1: PyMuPDF form widgets (highest priority)
    │          Maps ACORD-specific widget names to canonical fields
    │
    ├─ Step 2: pdfplumber text extraction
    │          Regex-based field matching from full-text
    │
    └─ Step 3: Tesseract OCR (ONLY if text < 100 chars)
               For scanned/image-only PDFs
```

---

## 🚦 Routing Logic (Priority Order)

| Priority | Condition | Route |
|----------|-----------|-------|
| 1 | Description contains "fraud", "staged", "fake" | Investigation |
| 2 | "injury" in description AND "no injury" NOT in description | Specialist Queue |
| 3 | Any mandatory field missing | Manual Review |
| 4 | Estimated damage < ₹25,000 | Fast-track |
| 5 | Default | Standard Processing |

---

## 📊 Confidence Score

| Missing Fields | Confidence |
|----------------|------------|
| 0              | High       |
| 1–2            | Medium     |
| 3+             | Low        |

---

## 🔒 Safety Guards

- **Policy number**: Rejects form labels ("CONTACT", "PHONE", etc.)
- **Claimant**: Rejects legal disclaimer text ("defraud", "penalty", etc.)
- **Location**: Deduplicates, fixes misspellings (Banglore → Bangalore)
- **Description**: Strips ACORD boilerplate instructions
- **Claim type**: "no injury" → damage (not injury)
- **VIN**: Requires digits to avoid matching text labels like "DESCRIBE"
- **Empty strings**: Treated as `null` (not valid values)

---

## 📋 Mandatory Fields

- `policy_number`
- `policyholder_name`
- `date_of_loss`
- `location`
- `description`
- `estimated_damage`
- `claim_type`

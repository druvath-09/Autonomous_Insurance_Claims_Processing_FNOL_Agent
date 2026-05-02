"""
main.py — FastAPI application for FNOL claim processing.

Single entry point: POST /process-claim/
Accepts a PDF upload, runs the hybrid extraction pipeline,
and returns structured JSON with routing + confidence.
"""

import os
import shutil
import tempfile

from fastapi import FastAPI, File, HTTPException, UploadFile

from extractor import process_pdf

# ────────────────────────────────────────────────────────────
# APP SETUP
# ────────────────────────────────────────────────────────────

app = FastAPI(
    title="FNOL Claims Processing API",
    description="Extracts structured data from ACORD Automobile Loss Notice PDFs",
    version="1.0.0",
)


# ────────────────────────────────────────────────────────────
# HEALTH CHECK
# ────────────────────────────────────────────────────────────

@app.get("/")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "message": "FNOL Processing API is running 🚀"}


# ────────────────────────────────────────────────────────────
# MAIN ENDPOINT
# ────────────────────────────────────────────────────────────

@app.post("/process-claim/")
async def process_claim(file: UploadFile = File(...)):
    """Accept a PDF upload and return structured FNOL extraction results.

    Response format:
    {
        "extractedFields": {...},
        "missingFields": [...],
        "recommendedRoute": "...",
        "reasoning": "...",
        "confidence": "High/Medium/Low"
    }
    """
    # Validate file type
    if not file.filename or not (file.filename.lower().endswith(".pdf") or file.filename.lower().endswith(".txt")):
        raise HTTPException(status_code=400, detail="Only PDF and TXT files are accepted")

    # Save to a secure temp file (auto-cleaned up in finally block)
    tmp_path = None
    try:
        # Create a unique temporary file securely
        ext = ".txt" if file.filename.lower().endswith(".txt") else ".pdf"
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        # Run the full extraction pipeline
        result = process_pdf(tmp_path)
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

    finally:
        # Always clean up the temp file
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


# ────────────────────────────────────────────────────────────
# STANDALONE EXECUTION (for quick local testing)
# ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("❌ Please provide PDF file path")
        print("Usage: python main.py sample.pdf")
        exit()

    pdf_path = sys.argv[1]

    result = process_pdf(pdf_path)

    print(json.dumps(result, indent=2))
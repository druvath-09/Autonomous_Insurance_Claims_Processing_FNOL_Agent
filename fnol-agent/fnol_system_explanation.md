# FNOL System Explanation

## 1. High-Level Overview (What the system does)
This project is an **Automated First Notice of Loss (FNOL) Processing API**. It acts as an intelligent initial claims handler. It accepts ACORD Automobile Loss Notice PDFs, automatically extracts structured data (like policy number, damage estimates, and location), validates the completeness of the claim, and uses a rule-based engine to route the claim to the correct queue (e.g., Fast-track, Specialist, or Fraud Investigation). 

## 2. End-to-End Workflow & File Explanations

### End-to-End Workflow
1. **Input:** A client sends a `POST` request with a PDF file.
2. **Pre-processing:** The system securely saves the file to a temporary location.
3. **Extraction Engine:** The system attempts to read interactive form fields. It also extracts raw text, falling back to OCR if the document is a scanned image.
4. **Parsing & Cleaning:** Raw data is cleaned (stripping boilerplate legal text and form instructions) and mapped to 16 canonical fields.
5. **Validation:** The system checks if the 7 mandatory fields are present.
6. **Decision/Routing:** Business rules evaluate the extracted data to determine a confidence score and assign the claim to a specific processing queue.
7. **Output:** A structured JSON response is returned, and the temporary file is deleted.

### File-by-File & Function-Level Breakdown

**`main.py` (The API Layer)**
Acts as the entry point and handles HTTP requests, separating web logic from business logic.
*   `process_claim()`: Accepts the upload, validates the file extension, securely writes it to a `tempfile`, calls the extraction pipeline, and guarantees cleanup in a `finally` block to prevent storage leaks.

**`extractor.py` (The Heavy Lifter)**
Handles all PDF interaction and data parsing.
*   `extract_form_data()`: Uses PyMuPDF to extract high-fidelity interactive widgets.
*   `_form_get()`: A clever helper that uses substring matching to handle verbose and unpredictable ACORD widget names.
*   `extract_text()`: Uses `pdfplumber` to pull raw, selectable text from flattened PDFs.
*   `extract_text_ocr()`: Uses `pytesseract` to read text from scanned images.
*   `_clean_location()` & `_clean_description()`: Data sanitization functions that remove form labels, deduplicate words, and fix common misspellings (e.g., "banglore" -> "Bangalore").
*   `extract_fields()`: The core parsing logic. It tries to map data to our 16 canonical fields by looking at the form data first, and falling back to safe Regex (`_safe_regex`) on the raw text.
*   `process_pdf()`: The orchestrator. It runs the extraction, calls validation, routing, and returns the final dictionary.

**`utils.py` (The Brains / Business Logic)**
Contains zero PDF logic—strictly validation and decision-making.
*   `find_missing()`: Iterates over the `MANDATORY_FIELDS` list to flag incomplete claims.
*   `normalize_damage()`: Safely converts string currencies (like "15,000") to integers.
*   `route_claim()`: The rule-based decision tree that evaluates the claim data to assign a queue.
*   `calculate_confidence()`: Determines High/Medium/Low confidence based solely on the count of missing mandatory fields.

## 3. Agent-Like Behavior
Why is this called an "agent" rather than just a script? Because it exhibits autonomous decision-making and resilience:

*   **Handling Uncertainty:** Real-world PDFs are messy. The system adapts dynamically:
    *   *Format uncertainty:* If the PDF is flattened, it falls back to text extraction. If the text length is under 100 characters, it autonomously decides to trigger OCR.
    *   *Data uncertainty:* It uses `_form_get()` to vaguely match form fields when exact keys fail, and it strips out legal boilerplate when it accidentally captures instruction text.
*   **Making Decisions (Prioritized Rules):** It doesn't just pass data through; it analyzes the context chronologically by severity:
    1.  **Fraud** (Highest Risk): If words like "staged" appear, it routes to Investigation immediately.
    2.  **Injury** (High Liability): Routes to Specialists, cleanly avoiding false positives like "no injury".
    3.  **Missing Data**: Routes to Manual Review because the system knows it cannot safely process incomplete data.
    4.  **Low Damage**: Safely Fast-tracks claims under 25,000 to save human operational costs.

## 4 & 5. The Pipeline Stage-by-Stage

1.  **PDF Input:** The raw ACORD form. 
2.  **Form Extraction (PyMuPDF):** 
    *   *Why needed:* It's the most accurate way to get key-value pairs. 
    *   *Edge case:* If the PDF is "printed to PDF" (flattened), widgets don't exist.
3.  **Text Extraction (pdfplumber):** 
    *   *Why needed:* Grabs text from flattened PDFs. 
    *   *Problem:* Text is often out of order and mixed with visual noise.
4.  **OCR Fallback (Tesseract):** 
    *   *Why needed:* For physical documents that were scanned.
    *   *Edge case:* OCR is slow and error-prone. *Code handling:* It is safely gated behind a condition (`len(text) < 100`) so it only runs when absolutely necessary.
5.  **Field Extraction:** 
    *   *Why needed:* Translates unstructured blobs of text into structured JSON.
    *   *Problem:* ACORD forms include instructions like "(ACORD 101 required)". *Code handling:* Blacklists and Regex cleaning functions strip this out.
6.  **Validation:** 
    *   *Why needed:* Downstream systems (like a database) will crash if a policy number is missing.
7.  **Routing:** 
    *   *Why needed:* Automates the human triage process, saving time and money.
8.  **Output:** Returns a standardized JSON payload for the frontend/database.

## 6. Important Design Decisions

*   **Why Hybrid Extraction?** Relying purely on OCR is slow and inaccurate. Relying purely on Form Fields breaks on scanned docs. Hybrid ensures the fastest, most accurate method is used first, with safety nets beneath it.
*   **Why Rule-Based Routing instead of AI/LLMs?** For strict financial/insurance logic, deterministic rules are superior. They are 100x faster, cheaper, and strictly auditable. You don't want an AI "hallucinating" a fraud claim into the fast-track queue.
*   **Handling Noisy Text:** Instead of relying on perfect Regex, the system actively sanitizes inputs to strip out form-label words like "CITY" or "STATE" that accidentally bleed into the extracted values.
*   **Mandatory Fields:** Hardcoding 7 mandatory fields creates a strict boundary between "machine-processable" and "needs human review," maintaining data integrity.

## 7. The "Interview Explanation" Version

**The 30-Second Pitch:**
> "For this assignment, I built a production-ready API that automates the first step of insurance claims processing. It takes an uploaded ACORD PDF form and runs it through a hybrid extraction pipeline using PyMuPDF, pdfplumber, and Tesseract OCR. It extracts the raw data, sanitizes it using regex, validates it for completeness, and then runs it through a deterministic business rules engine to automatically route the claim—like fast-tracking minor damages or flagging fraud—returning a structured JSON response."

**The 1-Minute Deep Dive:**
> *(Add this to the 30-second pitch)*: "A major focus of my design was resilience. Real-world PDFs are messy, so the system is built to degrade gracefully. It prioritizes interactive form fields for high accuracy, falls back to text extraction if the PDF is flattened, and autonomously triggers OCR only if the document is a scanned image. I also wrote custom sanitization functions to strip out boilerplate ACORD instructions that often corrupt the data. Finally, I specifically chose a rule-based decision tree for routing rather than an LLM, because in an insurance context, deterministic, auditable logic is much safer and faster than generative AI."

**Key points to emphasize to the interviewer:**
*   **Separation of Concerns:** "I specifically separated the API (`main.py`), the Extraction (`extractor.py`), and the Business Logic (`utils.py`)."
*   **Performance:** "I gated the OCR behind a length check so the API remains fast for digital PDFs."
*   **Business value:** "The routing logic is designed to save operational costs by automatically fast-tracking low-value claims while escalating high-risk ones."

## 8. Potential Issues & Improvements

1.  **Blocking Operations in FastAPI:** Tesseract OCR and PyMuPDF are synchronous. In a high-traffic production environment, processing a heavy PDF will block the FastAPI event loop. 
    *   *Improvement:* Offload the `process_pdf` function to a background task using Celery/Redis, or wrap it in `asyncio.to_thread()`.
2.  **Hardcoded Misspellings:** The `_CITY_CORRECTIONS` dict is currently hardcoded.
    *   *Improvement:* Use a fuzzy string matching library like `FuzzyWuzzy` or `RapidFuzz` against a canonical database of cities.
3.  **Observability:** The code currently uses `print()` for warnings.
    *   *Improvement:* Implement Python's standard `logging` module so errors can be tracked in tools like Datadog or AWS CloudWatch.
4.  **Regex Brittleness:** If an ACORD form drastically changes its layout, the Regex might fail. 
    *   *Improvement:* Implement a very small, structured LLM call (like GPT-4o-mini) as a *final* fallback if both form-fields and Regex fail to find mandatory fields.

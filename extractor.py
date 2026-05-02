"""
extractor.py — Hybrid PDF extraction pipeline for FNOL documents.

Strategy (in priority order):
  1. Form field extraction via PyMuPDF widgets  (highest fidelity)
  2. Text extraction via pdfplumber             (good for text-based PDFs)
  3. OCR fallback via Tesseract                  (only when text < 100 chars)
"""

import re

import fitz  # PyMuPDF
import pdfplumber
import pytesseract
from pdf2image import convert_from_path


# ────────────────────────────────────────────────────────────
# STEP 1: FORM FIELD EXTRACTION (Highest Priority)
# ────────────────────────────────────────────────────────────

def extract_form_data(pdf_path: str) -> dict:
    """Extract interactive form-field values using PyMuPDF widgets.

    Returns a raw dict with the original (normalized) widget names as keys.
    Keys are lowercased and stripped but NOT remapped here — remapping
    to our canonical field names happens in extract_fields().
    """
    data: dict[str, str] = {}
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            widgets = page.widgets()
            if widgets:
                for w in widgets:
                    if w.field_name and w.field_value:
                        key = w.field_name.strip().lower()
                        value = str(w.field_value).strip()
                        if value:  # Skip empty strings
                            data[key] = value
    except Exception as e:
        print(f"[WARN] Form extraction error: {e}")
    return data


def _form_get(form_data: dict, *candidate_keys: str) -> str | None:
    """Try multiple candidate keys against the form data dict.

    ACORD forms have long/inconsistent widget names like:
      'description of accident acord 101 additional remarks ...'
    This helper does a substring match: if any candidate appears
    *inside* any form-data key, we return the value.
    """
    for candidate in candidate_keys:
        candidate_lower = candidate.lower()
        # Exact match first
        if candidate_lower in form_data:
            return form_data[candidate_lower]
        # Substring match (handles verbose ACORD widget names)
        for key, value in form_data.items():
            if candidate_lower in key:
                return value
    return None


# ────────────────────────────────────────────────────────────
# STEP 2: TEXT EXTRACTION (pdfplumber)
# ────────────────────────────────────────────────────────────

def extract_text(pdf_path: str) -> str:
    """Extract all text from every page using pdfplumber."""
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"[WARN] Text extraction error: {e}")
    return text


# ────────────────────────────────────────────────────────────
# STEP 3: OCR FALLBACK (Tesseract) — only if text is sparse
# ────────────────────────────────────────────────────────────

def extract_text_ocr(pdf_path: str) -> str:
    """Convert PDF pages to images and run Tesseract OCR."""
    text = ""
    try:
        images = convert_from_path(pdf_path)
        for img in images:
            text += pytesseract.image_to_string(img) + "\n"
    except Exception as e:
        print(f"[WARN] OCR error: {e}")
    return text


# ────────────────────────────────────────────────────────────
# HELPER: Safe regex extraction
# ────────────────────────────────────────────────────────────

def _safe_regex(text: str, pattern: str) -> str | None:
    """Extract first regex match safely.

    • If the pattern has a capture group → return group(1)
    • Otherwise → return the full match
    • Returns None on no match or empty result
    """
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    result = match.group(1).strip() if match.lastindex else match.group(0).strip()
    return result if result else None  # Treat empty string as None


# ────────────────────────────────────────────────────────────
# HELPER: Location cleaning
# ────────────────────────────────────────────────────────────

_LOCATION_BLACKLIST = [
    "LOCATION", "LOSS", "STREET", "CITY", "STATE", "ZIP",
    "REPORT", "NUMBER", "POLICE", "FIRE",
    "DEPARTMENT", "CONTACTED", "COUNTRY", "NO", "OR",
]

# Common misspelling corrections
_CITY_CORRECTIONS = {
    "banglore": "Bangalore",
    "bangalor": "Bangalore",
    "bengaluru": "Bangalore",
    "hyderbad": "Hyderabad",
    "mumabi": "Mumbai",
    "chnnai": "Chennai",
    "dlehi": "Delhi",
}


def _clean_location(raw: str | None) -> str | None:
    """Remove form-label noise, deduplicate, and fix common misspellings."""
    if not raw:
        return None

    text = raw
    # Remove instructional text that sometimes leaks in
    text = re.sub(r'DESCRIBE.*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'IF NOT AT SPECIFIC ADDRESS', '', text, flags=re.IGNORECASE)

    # Strip blacklisted form-label words
    for word in _LOCATION_BLACKLIST:
        text = re.sub(rf'\b{word}\b', '', text, flags=re.IGNORECASE)

    # Normalize punctuation and whitespace
    text = re.sub(r'[^a-zA-Z0-9, ]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r',+', ',', text)

    # Fix common city misspellings FIRST, then deduplicate
    parts = [p.strip() for p in text.split(",") if p.strip()]
    parts = [_CITY_CORRECTIONS.get(p.lower(), p) for p in parts]

    # Deduplicate (case-insensitive)
    seen: set[str] = set()
    unique: list[str] = []
    for part in parts:
        if part.lower() not in seen:
            seen.add(part.lower())
            unique.append(part)

    result = ", ".join(unique)
    return result if result else None


# ────────────────────────────────────────────────────────────
# HELPER: Description cleaning
# ────────────────────────────────────────────────────────────

def _clean_description(raw: str | None) -> str | None:
    """Remove ACORD instruction text and normalize whitespace."""
    if not raw:
        return None

    text = raw
    # Remove ACORD boilerplate instructions
    text = re.sub(r'\(ACORD.*?required\)', '', text, flags=re.IGNORECASE)
    # Remove legal disclaimer fragments
    text = re.sub(
        r'for the purpose of defrauding.*',
        '', text, flags=re.IGNORECASE
    )
    text = re.sub(r'\s+', ' ', text).strip()
    return text if text else None


# ────────────────────────────────────────────────────────────
# CORE: Field extraction from text + form data
# ────────────────────────────────────────────────────────────

def extract_fields(text: str, form_data: dict) -> dict:
    """Extract all FNOL fields using form data (priority) + regex fallback.

    Form data keys from ACORD widgets are verbose/inconsistent, e.g.:
      - "text7" might contain the policy number
      - "description of accident acord 101 ..." contains the description
      - "street location of loss" contains the location
      - "name of insured first middle last" contains the policyholder

    We use _form_get() with substring matching to handle this.
    Returns a dict with all 16 required field keys. Missing values are None.
    """
    fields: dict[str, str | None] = {}

    # ── POLICY INFORMATION ──────────────────────────────────

    # Policy number: try form field first, then regex on text
    # IMPORTANT: avoid matching "CONTACT" or other form labels
    policy_from_form = _form_get(form_data, "policy number", "policy_number")
    if not policy_from_form:
        # Some ACORD forms store it in generic "TextN" fields
        # Try to find a value that looks like a policy number (starts with POL or alphanumeric)
        for key, val in form_data.items():
            if re.match(r'^text\d+$', key, re.IGNORECASE) and re.match(r'POL\d+', val):
                policy_from_form = val
                break

    policy_candidate = (
        policy_from_form
        or _safe_regex(text, r'\bPOL\d{4,}\b')
        or _safe_regex(text, r'POLICY\s*(?:NUMBER|NO)[:\s]*([A-Z0-9]{3,})')
    )
    # Reject form-label words that sometimes get falsely captured
    _POLICY_BLACKLIST = {"CONTACT", "PHONE", "AGENCY", "NAME", "CODE",
                         "NUMBER", "INSURED", "CARRIER", "NAIC"}
    if policy_candidate and policy_candidate.upper() in _POLICY_BLACKLIST:
        policy_candidate = None
    fields["policy_number"] = policy_candidate

    # Policyholder name — use form data with ACORD's verbose key
    name_candidate = (
        _form_get(form_data, "name of insured", "policyholder_name", "insured")
        or _safe_regex(text, r'NAME OF INSURED.*?\n([A-Za-z ]{3,40})')
        or _safe_regex(text, r'INSURED[:\s]*([A-Za-z ]{3,40})')
    )
    # Validate: reject if it contains form-label keywords
    if name_candidate and not any(
        w in name_candidate.upper()
        for w in ["DATE", "LOSS", "TIME", "CODE", "CONTACT", "POLICY",
                   "NUMBER", "MAILING", "ADDRESS", "FIRST", "MIDDLE", "LAST"]
    ):
        fields["policyholder_name"] = name_candidate.strip()
    else:
        fields["policyholder_name"] = None

    fields["effective_dates"] = (
        form_data.get("text2")
        or _form_get(form_data, "effective_dates", "effective dates")
        or _safe_regex(text, r'(\d{2}/\d{2}/\d{4}\s*-\s*\d{2}/\d{2}/\d{4})')
    )

    # ── INCIDENT INFORMATION ────────────────────────────────

    # Date of loss — ACORD often stores this in a generic "TextN" widget
    # In ACORD forms, "Text3" is consistently the date-of-loss field
    # while "Text1" is the form submission date
    dol_candidate = _form_get(form_data, "date of loss", "date_of_loss")
    if not dol_candidate:
        # Check Text3 first (ACORD standard position for date of loss)
        text3_val = form_data.get("text3", "")
        if re.match(r'\d{1,2}/\d{1,2}/\d{4}$', text3_val):
            dol_candidate = text3_val
        else:
            # Fall back to scanning all TextN fields
            for key, val in form_data.items():
                if re.match(r'^text\d+$', key, re.IGNORECASE):
                    if re.match(r'\d{1,2}/\d{1,2}/\d{4}$', val):
                        dol_candidate = val
                        break
    fields["date_of_loss"] = (
        dol_candidate
        or _safe_regex(text, r'DATE OF LOSS.*?(\d{1,2}/\d{1,2}/\d{4})')
        or _safe_regex(text, r'(\d{1,2}/\d{1,2}/\d{4})')
    )

    # Time — validate hour:minute ranges
    raw_time = form_data.get("text4") or _form_get(form_data, "time") or _safe_regex(text, r'(\d{1,2}:\d{2})')
    if raw_time:
        try:
            h, m = map(int, raw_time.split(":"))
            fields["time"] = raw_time if (0 <= h < 24 and 0 <= m < 60) else None
        except (ValueError, AttributeError):
            fields["time"] = None
    else:
        fields["time"] = None

    # ── LOCATION ────────────────────────────────────────────

    # Build location from form fields (ACORD splits into street / city,state,zip / country)
    loc_parts = []
    street = _form_get(form_data, "street location of loss", "street")
    city_state = _form_get(form_data, "city state zip", "city, state, zip")
    country = _form_get(form_data, "country")
    if street:
        loc_parts.append(street)
    if city_state:
        loc_parts.append(city_state)
    if country:
        loc_parts.append(country)

    if loc_parts:
        raw_loc = ", ".join(loc_parts)
        fields["location"] = _clean_location(raw_loc)
    else:
        # Fallback: extract from full text between section headers
        loc_match = re.search(
            r'LOCATION OF LOSS(.*?)(DESCRIPTION OF ACCIDENT|POLICE|FIRE)',
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if loc_match:
            fields["location"] = _clean_location(
                " ".join(loc_match.group(1).split())
            )
        else:
            fields["location"] = None

    # ── DESCRIPTION ─────────────────────────────────────────

    desc_from_form = _form_get(
        form_data,
        "description of accident",
        "description",
    )
    if desc_from_form:
        fields["description"] = _clean_description(desc_from_form)
    else:
        # Fallback: extract from text between section headers
        desc_match = re.search(
            r'DESCRIPTION OF ACCIDENT(.*?)'
            r'(INSURED VEHICLE|ESTIMATE AMOUNT|DAMAGE TO|VEH\s*#)',
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if desc_match:
            fields["description"] = _clean_description(
                " ".join(desc_match.group(1).split())
            )
        else:
            fields["description"] = None

    # ── INVOLVED PARTIES ────────────────────────────────────

    # Claimant — be very careful NOT to match legal disclaimer text
    claimant_candidate = (
        _form_get(form_data, "claimant", "name contact")
        or _safe_regex(text, r'CLAIMANT[:\s]*([A-Za-z ]{3,40})')
    )
    if claimant_candidate:
        # Reject if it looks like legal boilerplate
        legal_words = ["defraud", "purpose", "fraud", "penalty", "law",
                        "statute", "knowingly", "felony", "insurer"]
        if any(w in claimant_candidate.lower() for w in legal_words):
            fields["claimant"] = None
        else:
            fields["claimant"] = claimant_candidate
    else:
        fields["claimant"] = None

    fields["third_parties"] = (
        form_data.get("text99")
        or _form_get(form_data, "third_parties", "third party")
        or _safe_regex(text, r'THIRD PARTY[:\s]*([A-Za-z ]{3,40})')
    )

    # Contact — try form phone fields, then regex
    fields["contact"] = (
        _form_get(form_data, "phone  cell", "phone", "primary phone")
        or _safe_regex(text, r'(\+?\d[\d\s\-]{8,}\d)')
    )

    # ── ASSET DETAILS ───────────────────────────────────────

    fields["asset_type"] = (
        _form_get(form_data, "asset_type", "type body")
        or _safe_regex(text, r'\b(car|vehicle|bike|truck|motorcycle|sedan|suv)\b')
    )

    # VIN — use exact-key lookup only (substring match would hit 'owner's name...')
    vin_from_form = form_data.get("v.i.n.") or form_data.get("vin")
    if not vin_from_form:
        # Regex: require same-line match AND at least one digit (real VINs always have digits)
        vin_regex = _safe_regex(text, r'V\.?I\.?N\.?[:\s]+([A-HJ-NPR-Z0-9]{5,17}(?<!\n))')
        if vin_regex and any(c.isdigit() for c in vin_regex):
            vin_from_form = vin_regex
    fields["asset_id"] = vin_from_form

    # Estimated damage — try form fields with ACORD-specific names
    damage_from_form = _form_get(
        form_data, "estimate amount", "estimated_damage", "text45"
    )
    fields["estimated_damage"] = (
        damage_from_form
        or _safe_regex(text, r'ESTIMATE\s*AMOUNT[^\d]*(\d[\d,]+)')
        or _safe_regex(text, r'ESTIMATED\s*DAMAGE[^\d]*(\d[\d,]+)')
    )

    # ── CLAIM TYPE (strict rule-based) ──────────────────────

    desc_lower = (fields.get("description") or "").lower()

    if "no injury" in desc_lower:
        fields["claim_type"] = "damage"
    elif "injury" in desc_lower:
        fields["claim_type"] = "injury"
    elif "theft" in desc_lower:
        fields["claim_type"] = "theft"
    else:
        fields["claim_type"] = None

    # ── OTHER ───────────────────────────────────────────────

    fields["attachments"] = "yes" if "attached" in text.lower() else None
    fields["initial_estimate"] = fields["estimated_damage"]

    return fields


# ────────────────────────────────────────────────────────────
# MAIN PIPELINE — called by the API layer
# ────────────────────────────────────────────────────────────

def process_pdf(pdf_path: str) -> dict:
    """Run the full hybrid extraction pipeline on a PDF.

    1. Extract form fields (PyMuPDF)
    2. Extract text (pdfplumber)
    3. OCR fallback if text < 100 chars
    4. Parse fields, identify missing, route, score confidence
    """
    from utils import find_missing, calculate_confidence, route_claim

    # Step 1 & 2: parallel extraction
    if pdf_path.lower().endswith(".txt"):
        form_data = {}
        with open(pdf_path, "r", encoding="utf-8") as f:
            text = f.read()
    else:
        form_data = extract_form_data(pdf_path)
        text = extract_text(pdf_path)

        # Step 3: OCR fallback only if text extraction yielded very little
        if len(text.strip()) < 100:
            print("[INFO] Text too sparse — falling back to OCR")
            text = extract_text_ocr(pdf_path)

    # Step 4: extract structured fields
    fields = extract_fields(text, form_data)

    # Step 5: identify missing mandatory fields
    missing = find_missing(fields)

    # Step 6: route claim
    route, reason = route_claim(fields, missing)

    # Step 7: confidence score
    confidence = calculate_confidence(missing)

    return {
        "extractedFields": fields,
        "missingFields": missing,
        "recommendedRoute": route,
        "reasoning": reason,
        "confidence": confidence,
    }
"""
utils.py — Validation, routing, and confidence scoring for FNOL claims.

All business logic for post-extraction processing lives here.
No extraction or PDF handling — that belongs in extractor.py.
"""


# ────────────────────────────────────────────────────────────
# MANDATORY FIELDS
# ────────────────────────────────────────────────────────────

MANDATORY_FIELDS = [
    "policy_number",
    "policyholder_name",
    "date_of_loss",
    "location",
    "description",
    "estimated_damage",
    "claim_type",
]


# ────────────────────────────────────────────────────────────
# MISSING FIELD DETECTION
# ────────────────────────────────────────────────────────────

def find_missing(fields: dict) -> list[str]:
    """Return list of mandatory field names that are missing or empty."""
    missing = []
    for key in MANDATORY_FIELDS:
        value = fields.get(key)
        # None, empty string, and whitespace-only are all "missing"
        if not value or (isinstance(value, str) and not value.strip()):
            missing.append(key)
    return missing


# ────────────────────────────────────────────────────────────
# DAMAGE NORMALIZATION
# ────────────────────────────────────────────────────────────

def normalize_damage(value) -> int | None:
    """Convert a damage string like '15,000' or '15000' to an integer."""
    if not value:
        return None
    try:
        return int(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


# ────────────────────────────────────────────────────────────
# ROUTING LOGIC (priority-based, no duplicates)
# ────────────────────────────────────────────────────────────

def route_claim(fields: dict, missing_fields: list[str]) -> tuple[str, str]:
    """Determine the claim's processing route.

    Priority order (first match wins):
      1. Fraud keywords → Investigation
      2. Injury (excluding "no injury") → Specialist Queue
      3. Missing mandatory fields → Manual Review
      4. Low damage (< ₹25,000) → Fast-track
      5. Default → Standard Processing

    Returns (route_name, reasoning_string).
    """
    description = (fields.get("description") or "").lower()
    damage = normalize_damage(fields.get("estimated_damage"))

    # ── PRIORITY 1: Fraud detection ─────────────────────────
    fraud_keywords = ["fraud", "staged", "fake"]
    if any(word in description for word in fraud_keywords):
        return "Investigation", "Fraud-related keywords detected in description"

    # ── PRIORITY 2: Injury detection (STRICT) ───────────────
    # "no injury" → NOT an injury claim (it's damage)
    if "injury" in description and "no injury" not in description:
        return "Specialist Queue", "Injury-related claim requires specialist handling"

    # ── PRIORITY 3: Missing mandatory fields ────────────────
    if missing_fields:
        return (
            "Manual Review",
            f"Missing mandatory fields: {', '.join(missing_fields)}",
        )

    # ── PRIORITY 4: Low damage → fast-track ─────────────────
    if damage is not None and damage < 25000:
        return "Fast-track", f"Estimated damage (₹{damage:,}) is below ₹25,000 threshold"

    # ── PRIORITY 5: Default ─────────────────────────────────
    return "Standard Processing", "No special conditions detected"


# ────────────────────────────────────────────────────────────
# CONFIDENCE SCORING
# ────────────────────────────────────────────────────────────

def calculate_confidence(missing_fields: list[str]) -> str:
    """Confidence based on number of missing mandatory fields.

    • 0 missing → High
    • 1-2 missing → Medium
    • 3+ missing → Low
    """
    count = len(missing_fields)
    if count == 0:
        return "High"
    elif count <= 2:
        return "Medium"
    else:
        return "Low"
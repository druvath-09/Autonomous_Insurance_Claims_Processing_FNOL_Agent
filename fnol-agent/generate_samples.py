import fitz  # PyMuPDF
import os

TEMPLATE_PATH = "sample.pdf"

# Base data that satisfies all mandatory fields so it doesn't fall into "Manual Review"
base_data = {
    "Text7": "POL99999",  # Policy Number
    "NAME OF INSURED First Middle Last": "John Doe",  # Policyholder Name
    "Text3": "05/01/2026",  # Date of Loss
    "STREET LOCATION OF LOSS": "123 Main St",  # Location
    "CITY STATE ZIP": "New York, NY 10001",
    "COUNTRY": "USA",
}

# The 4 test cases to cover all routes
test_cases = [
    {
        "filename": "test_investigation.pdf",
        "fields": {
            **base_data,
            "DESCRIPTION OF ACCIDENT ACORD 101 Additional Remarks Schedule may be attached if more space is required": "The accident seemed staged and possibly a fake claim for fraud.",
            "Text45": "30000"  # Damage
        }
    },
    {
        "filename": "test_specialist_injury.pdf",
        "fields": {
            **base_data,
            "DESCRIPTION OF ACCIDENT ACORD 101 Additional Remarks Schedule may be attached if more space is required": "Severe collision at intersection. Driver sustained a neck injury and was taken to hospital.",
            "Text45": "50000"
        }
    },
    {
        "filename": "test_standard_processing.pdf",
        "fields": {
            **base_data,
            "DESCRIPTION OF ACCIDENT ACORD 101 Additional Remarks Schedule may be attached if more space is required": "Backed into a pole in the parking lot. Vehicle rear damaged. No injury.",
            "Text45": "45000"  # >= 25000 for standard
        }
    },
    {
        "filename": "test_fast_track.pdf",
        "fields": {
            **base_data,
            "DESCRIPTION OF ACCIDENT ACORD 101 Additional Remarks Schedule may be attached if more space is required": "Scratched the side door against a shopping cart. No injury.",
            "Text45": "5000"  # < 25000 for fast track
        }
    },
    {
        "filename": "test_perfect_all_fields.pdf",
        "fields": {
            **base_data,
            "Text1": "01/01/2026", # Form date
            "Text2": "01/01/2026 - 12/31/2026", # Effective dates
            "Text4": "14:30", # Time
            "Text99": "Mike Johnson", # Third party name (often maps to generic text fields in ACORD)
            "VIN": "1HGCM82633A004123", # Asset ID / VIN (must be 17 chars with digits)
            "TYPE BODY": "Sedan", # Asset type
            "NAME CONTACT": "Jane Smith", # Claimant
            "PHONE  CELL HOME BUS PRIMARY": "800-555-1234", # Contact
            "DESCRIPTION OF ACCIDENT ACORD 101 Additional Remarks Schedule may be attached if more space is required": "Collision at 14:30. Third party driver Mike Johnson involved. Police report attached. No injury.",
            "Text45": "12000"
        }
    }
]

def generate_pdfs():
    if not os.path.exists(TEMPLATE_PATH):
        print(f"Error: Template {TEMPLATE_PATH} not found!")
        return

    for case in test_cases:
        doc = fitz.open(TEMPLATE_PATH)
        for page in doc:
            widgets = page.widgets()
            if widgets:
                for w in widgets:
                    if w.field_name in case["fields"]:
                        w.field_value = case["fields"][w.field_name]
                        w.update()
        
        doc.save(case["filename"])
        print(f"Generated PDF: {case['filename']}")

def generate_txt():
    # Generate a pure text file to test the text extraction fallback
    txt_content = """
    FIRST NOTICE OF LOSS REPORT
    
    POLICY NUMBER: POL55555
    NAME OF INSURED: Jane Smith
    DATE OF LOSS: 12/15/2025
    TIME: 14:30
    
    LOCATION OF LOSS: 456 Market St, San Francisco, CA
    DESCRIPTION OF ACCIDENT: Rear-ended by another vehicle at a stop sign. Minor damage. No injury.
    
    ESTIMATE AMOUNT: 15000
    CLAIMANT: Jane Smith
    """
    with open("test_text_fallback.txt", "w") as f:
        f.write(txt_content.strip())
    print("Generated TXT: test_text_fallback.txt")

if __name__ == "__main__":
    generate_pdfs()
    generate_txt()

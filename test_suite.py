import requests
import json
import os
import generate_samples

API_URL = "http://127.0.0.1:8000/process-claim/"

TEST_CASES = [
    {"file": "Sample1.pdf", "expected_route": "Fast-track"},
    {"file": "sample2.pdf", "expected_route": "Manual Review"},
    {"file": "sample.pdf", "expected_route": "Manual Review"},
    {"file": "test_investigation.pdf", "expected_route": "Investigation"},
    {"file": "test_specialist_injury.pdf", "expected_route": "Specialist Queue"},
    {"file": "test_fast_track.pdf", "expected_route": "Fast-track"},
    {"file": "test_standard_processing.pdf", "expected_route": "Standard Processing"},
    {"file": "test_perfect_all_fields.pdf", "expected_route": "Fast-track"},
    {"file": "test_text_fallback.txt", "expected_route": "Manual Review"},
]

def run_tests():
    print("=" * 60)
    print("Generating test files...")
    generate_samples.generate_pdfs()
    generate_samples.generate_txt()
    
    print("=" * 60)
    print(f"{'FILE':<30} | {'EXPECTED':<20} | {'ACTUAL':<20} | STATUS")
    print("=" * 60)
    
    passed = 0
    total = 0
    
    for case in TEST_CASES:
        filename = case["file"]
        if not os.path.exists(filename):
            continue
            
        total += 1
        with open(filename, "rb") as f:
            files = {"file": f}
            try:
                resp = requests.post(API_URL, files=files)
                if resp.status_code == 200:
                    data = resp.json()
                    actual_route = data.get("recommendedRoute")
                    status = "✅ PASS" if actual_route == case["expected_route"] else "❌ FAIL"
                    if status == "✅ PASS":
                        passed += 1
                    
                    print(f"{filename:<30} | {case['expected_route']:<20} | {actual_route:<20} | {status}")
                else:
                    print(f"{filename:<30} | {case['expected_route']:<20} | HTTP {resp.status_code:<15} | ❌ FAIL")
            except Exception as e:
                print(f"{filename:<30} | {case['expected_route']:<20} | {str(e)[:19]:<20} | ❌ FAIL")
                
    print("=" * 60)
    print(f"TEST RUN COMPLETE: {passed}/{total} tests passed.")
    print("=" * 60)

    # Clean up generated files
    print("Cleaning up generated test files...")
    generated_files = [
        "test_investigation.pdf",
        "test_specialist_injury.pdf",
        "test_standard_processing.pdf",
        "test_fast_track.pdf",
        "test_perfect_all_fields.pdf",
        "test_text_fallback.txt"
    ]
    for file in generated_files:
        if os.path.exists(file):
            os.remove(file)
            print(f"Removed {file}")

if __name__ == "__main__":
    run_tests()

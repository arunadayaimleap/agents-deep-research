import csv
import subprocess
import sys
from pathlib import Path

def main():
    csv_path = Path(r"C:\aimleap\agents-deep-research\final_top_10000_enriched_appended_dominio_updated.csv")
    if not csv_path.exists():
        print(f"Error: CSV file not found at {csv_path}")
        return

    company_names = []
    
    # 1. Read up to 100 companies from the CSV
    with open(csv_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= 100:
                break
            
            company = row.get("RAZÓN SOCIAL", "").strip()
            if company:
                company_names.append(company)

    if not company_names:
        print("No companies found in CSV.")
        return

    print(f"Loaded {len(company_names)} companies. Starting sequential deep research runs...")

    # 2. Sequential execution
    for i, company in enumerate(company_names, start=1):
        print("\n" + "="*60)
        print(f"[{i}/{len(company_names)}] Starting research for: {company}")
        print("="*60 + "\n")
        
        # Execute run_email_pattern_research.py
        # Using subprocess to run the exact command required
        cmd = ["python", "run_email_pattern_research.py", company, "--max-iterations", "6"]
        
        try:
            # We use subprocess.run so it blocks and waits until this company is completely finished
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"\n[ERROR] Research script failed for '{company}'. Moving to next company.")
        except KeyboardInterrupt:
            print("\n[INFO] Batch run explicitly cancelled by user.")
            sys.exit(1)

    print("\n=== Batch run completely finished! ===")

if __name__ == "__main__":
    main()

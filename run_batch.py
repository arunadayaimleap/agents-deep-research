import argparse
import csv
import subprocess
import sys
import os
from pathlib import Path
from pymongo import MongoClient
from dotenv import load_dotenv

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100, help="Max companies to process (default 100). Use 1 for testing.")
    parser.add_argument("--csv", type=str, default=None, help="Path to CSV file (default: final_top_10000_enriched_appended_dominio_updated.csv)")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    default_csv = base_dir / "final_top_10000_enriched_appended_dominio_updated.csv"
    csv_path = Path(args.csv) if args.csv else default_csv
    if not csv_path.exists():
        print(f"Error: CSV file not found at {csv_path}")
        return

    company_names = []
    
    # 1. Read companies from the CSV
    with open(csv_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= args.limit:
                break
            
            company = row.get("RAZÓN SOCIAL", "").strip()
            if company:
                company_names.append(company)

    if not company_names:
        print("No companies found in CSV.")
        return

    # 2. Check MongoDB for already completed companies
    load_dotenv()
    completed_companies = set()
    try:
        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
        db_name = os.getenv("MONGO_DB_NAME", "deep_research_db")
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
        # Verify connection
        client.server_info()
        db = client[db_name]
        
        # We can check the 'reports' or 'company_research' collection for completed companies
        completed_companies = set(db.reports.distinct("company_name"))
        print(f"[INFO] Found {len(completed_companies)} already processed companies in MongoDB.")
    except Exception as e:
        print(f"[WARNING] Could not connect to MongoDB to verify prior runs: {e}")

    print(f"Loaded {len(company_names)} companies. Starting sequential deep research runs...")

    # 3. Sequential execution
    for i, company in enumerate(company_names, start=1):
        if company in completed_companies:
            print(f"[{i}/{len(company_names)}] Skipping '{company}' (Already completed previously)")
            continue

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

import csv
import sys
from pathlib import Path

csv_path = Path(r"C:\aimleap\agents-deep-research\final_top_10000_enriched_appended_dominio_updated.csv")

commands = []
with open(csv_path, mode="r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for i, row in enumerate(reader):
        if i >= 100:
            break
        
        company = row.get("RAZÓN SOCIAL", "").strip()
        if company:
            # Escape double quotes inside the company name just in case
            safe_company = company.replace('"', '\\"')
            cmd = f'python run_email_pattern_research.py "{safe_company}" --max-iterations 6'
            commands.append(cmd)

if commands:
    final_command = " ; ".join(commands)
    print("=== DRY RUN COMMAND (to be copied) ===")
    print(final_command)
    print(f"\nTotal commands generated: {len(commands)}")
else:
    print("No commands generated.")

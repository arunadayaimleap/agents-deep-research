# test_mongo_save.py
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_email_pattern_research import save_to_mongodb

mock_report_md = """# Executive Summary
**TestCompany SAS** is a fake company for testing database insertion.

# Research and Report
Everything seems to be working correctly with the script enhancements.
"""

mock_extracted = {
    "company_research": {
        "common_name": "TestCompany",
        "industries": ["Software", "Data Integration"],
        "sub_industries": ["AI Workflows"],
        "activities_by_industry": {
            "Software": ["Coding", "Testing"],
            "Data Integration": ["ETL", "DB Ops"]
        },
        "additional_details": "Testing the new pipeline."
    },
    "employees": [
        {
            "name": "Arunaday",
            "position": "CEO",
            "details": "Linkedln profile test."
        },
        {
            "name": "AI Agent",
            "position": "Lead Researcher",
            "details": "Operates autonomously."
        }
    ],
    "metadata": {
        "empresa": "TestCompany SAS",
        "nombre_fantasia": "TestCompany",
        "dominio": "testcompany.com.co",
        "pais": "Colombia",
        "total_emails_encontrados": 2
    },
    "formula_dominante": "first.last",
    "detalles": [
        {
            "patron": "first.last",
            "confianza": 99,
            "es_recomendado": True,
            "frecuencia": 2
        }
    ],
    "ejemplo_emails": [
        {"email": "arunaday.ceo@testcompany.com.co"},
        {"email": "ai.agent@testcompany.com.co"}
    ],
    "ord_email_patterns": {
        "formula": [["first.last", 99, True]],
        "primary_pattern": "first.last",
        "primary_confidence": 99
    }
}

print("Simulating a research finish. Calling save_to_mongodb()...")
save_to_mongodb("TestCompany SAS", mock_report_md, mock_extracted)
print("Done. If no errors occurred, check your local MongoDB GUI for 'deep_research_db'!")

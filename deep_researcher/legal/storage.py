"""MongoDB storage for legal cases, citations, and citation graph."""

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pymongo import MongoClient

from .models import CaseRecord, CitationRelationship


def _get_db():
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    db_name = os.getenv("MONGO_DB_NAME", "deep_research_db")
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    return client[db_name]


class LegalDB:
    """
    MongoDB-backed storage for legal pipeline.
    Provides find_case_by_citation for citation resolver and insert_citation_relationships for graph.
    """

    def __init__(self, db=None):
        self._db = db or _get_db()
        self.cases = self._db.legal_cases
        self.citations = self._db.legal_citations
        self.citation_relationships = self._db.legal_citation_relationships
        self.statutes = self._db.legal_statutes
        self.processing_log = self._db.legal_processing_log

    def find_case_by_citation(self, citation_text: str) -> Optional[str]:
        """Return case_id if this citation string is indexed, else None."""
        doc = self.citations.find_one({"citation_text": citation_text})
        if doc:
            return doc.get("case_id")
        return None

    def insert_case(self, record: CaseRecord) -> str:
        """Insert a case record; index its citations; return judgment_id."""
        doc = record.model_dump(mode="json")
        doc["inserted_at"] = datetime.now(timezone.utc)
        self.cases.insert_one(doc)
        judgment_id = record.judgment_id or doc.get("judgment_id")
        for c in record.citations:
            self.citations.update_one(
                {"citation_text": c.citation_text},
                {"$set": {"case_id": judgment_id, "citation_text": c.citation_text}},
                upsert=True,
            )
        return judgment_id

    def insert_citation_relationships(self, relationships: List[CitationRelationship]) -> None:
        """Persist citation graph edges."""
        for r in relationships:
            doc = r.model_dump(mode="json")
            doc["inserted_at"] = datetime.now(timezone.utc)
            self.citation_relationships.insert_one(doc)

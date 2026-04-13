"""
Persist ``CaseRecord`` to Neo4j: case nodes, precedent relationships, statutes, issues, topics.

Environment (``DR_`` prefix supported via ``get_env_with_prefix``):

- ``NEO4J_URI`` — e.g. ``bolt://localhost:7687`` or ``neo4j+s://xxxx.databases.neo4j.io``
- ``NEO4J_USER`` — default ``neo4j``
- ``NEO4J_PASSWORD``
- ``NEO4J_DATABASE`` — optional, default ``neo4j``

Enable by setting ``NEO4J_URI``; use ``run_legal_research.py --no-neo4j`` to skip.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from ..utils.os import get_env_with_prefix
from .models import CaseRecord, PrecedentRelationship

if TYPE_CHECKING:
    from neo4j import Driver

logger = logging.getLogger(__name__)

_REL_TYPES: set[str] = {e.value for e in PrecedentRelationship}


class LegalNeo4jStore:
    """Upsert a judgment graph from a pipeline ``CaseRecord``."""

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        *,
        database: Optional[str] = None,
    ):
        from neo4j import GraphDatabase

        self._driver: Driver = GraphDatabase.driver(uri, auth=(user, password))
        self._database = database or "neo4j"
        self._schema_checked = False

    def close(self) -> None:
        self._driver.close()

    def _ensure_schema(self, session) -> None:
        if self._schema_checked:
            return
        try:
            session.run(
                "CREATE CONSTRAINT case_judgment_id IF NOT EXISTS "
                "FOR (c:Case) REQUIRE c.judgment_id IS UNIQUE"
            )
        except Exception as e:
            logger.debug("Neo4j constraint (may already exist): %s", e)
        self._schema_checked = True

    def sync_case_record(self, record: CaseRecord) -> None:
        if not record.judgment_id:
            raise ValueError("CaseRecord.judgment_id is required for Neo4j sync")
        with self._driver.session(database=self._database) as session:
            self._ensure_schema(session)
            session.execute_write(self._tx_sync, record)

    @staticmethod
    def _tx_sync(tx, record: CaseRecord) -> None:
        jd = record.judgment_id
        meta = record.metadata
        jd_str = jd or ""
        is_stub_source = jd_str.startswith("unresolved:")

        props: Dict[str, Any] = {
            "case_name": meta.case_name,
            "court": meta.court,
            "bench": meta.bench or "",
            "judgment_date": meta.judgment_date.isoformat() if meta.judgment_date else None,
            "citation_string": meta.citation_string or "",
            "case_summary": record.case_summary or "",
            "stub": is_stub_source,
            "source_pipeline": "deep_researcher.legal",
        }
        if record.ratio:
            props["ratio_text"] = record.ratio.ratio
            props["ratio_paragraphs"] = record.ratio.supporting_paragraphs or []
        else:
            props["ratio_text"] = None
            props["ratio_paragraphs"] = []

        # Denormalized JSON for analytics / LLM context (optional queries)
        props["headnotes_json"] = json.dumps(
            [h.model_dump(mode="json") for h in record.headnotes], ensure_ascii=False
        )
        props["taxonomy_json"] = json.dumps(
            [t.model_dump(mode="json") for t in record.taxonomy_tags], ensure_ascii=False
        )
        props["citations_json"] = json.dumps(
            [c.model_dump(mode="json") for c in record.citations], ensure_ascii=False
        )

        flat = {k: v for k, v in props.items() if v is not None}
        tx.run(
            """
            MERGE (c:Case {judgment_id: $judgment_id})
            SET c.judgment_id = $judgment_id
            SET c += $props
            """,
            judgment_id=jd_str,
            props=flat,
        )

        # Precedent edges (dynamic relationship type, whitelist only)
        for rel in record.citation_relationships:
            tgt = rel.target_case_id
            if not tgt:
                continue
            stub = tgt.startswith("unresolved:")
            rtype = rel.relationship.value if isinstance(rel.relationship, PrecedentRelationship) else str(rel.relationship)
            if rtype not in _REL_TYPES:
                rtype = PrecedentRelationship.REFERS_TO.value
            tx.run(
                f"""
                MERGE (s:Case {{judgment_id: $source_id}})
                SET s.stub = coalesce(s.stub, false)
                MERGE (t:Case {{judgment_id: $target_id}})
                SET t.stub = $target_stub
                MERGE (s)-[r:`{rtype}`]->(t)
                SET r.citation_text = $citation_text
                """,
                source_id=rel.source_case_id,
                target_id=tgt,
                target_stub=stub,
                citation_text=rel.citation_text or "",
            )

        # Statutes
        for st in record.statutes:
            act = st.statute or ""
            sec = st.section or ""
            tx.run(
                """
                MATCH (c:Case {judgment_id: $jid})
                MERGE (s:Statute {act: $act, section: $section})
                SET s.section = $section
                MERGE (c)-[r:REFERENCES_STATUTE]->(s)
                SET r.paragraph = $paragraph
                """,
                jid=jd_str,
                act=act,
                section=sec,
                paragraph=st.paragraph,
            )

        # Issues (keyed by text hash surrogate for stable MERGE)
        for iss in record.issues:
            text = (iss.issue_text or "").strip()
            if not text:
                continue
            key = hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]
            paras = iss.supporting_paragraphs or []
            tx.run(
                """
                MATCH (c:Case {judgment_id: $jid})
                MERGE (i:Issue {issue_key: $ikey})
                SET i.text = $text
                MERGE (c)-[r:ADDRESSES]->(i)
                SET r.supporting_paragraphs = $paras
                """,
                jid=jd_str,
                ikey=key,
                text=text[:8000],
                paras=paras,
            )

        # Taxonomy as Topic nodes (flat path string)
        for tag in record.taxonomy_tags:
            path = tag.path or []
            if not path:
                continue
            full = " — ".join(path)
            tx.run(
                """
                MATCH (c:Case {judgment_id: $jid})
                MERGE (t:Topic {full_path: $full_path})
                SET t.path = $path_list
                MERGE (c)-[:CLASSIFIED_AS]->(t)
                """,
                jid=jd_str,
                full_path=full,
                path_list=path,
            )


def legal_neo4j_from_env() -> Optional[LegalNeo4jStore]:
    """Return a store if ``NEO4J_URI`` and password are set; else ``None``."""
    uri = get_env_with_prefix("NEO4J_URI")
    password = get_env_with_prefix("NEO4J_PASSWORD")
    if not uri or not password:
        return None
    user = get_env_with_prefix("NEO4J_USER", default="neo4j") or "neo4j"
    database = get_env_with_prefix("NEO4J_DATABASE", default="neo4j")
    return LegalNeo4jStore(uri, user, password, database=database)

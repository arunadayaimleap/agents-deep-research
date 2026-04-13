#!/usr/bin/env python3
"""
End-to-end Neo4j legal graph test (no LLM calls).

1. Load .env from repo root
2. Connect using legal_neo4j_from_env()
3. Upsert a minimal synthetic CaseRecord (same path as LegalPipeline step 16)
4. Run Cypher to verify nodes and relationships

Requires NEO4J_URI + NEO4J_PASSWORD (or DR_ prefixed).

Optional local Neo4j (Docker Desktop running):
  docker run -d --rm --name neo4j-legal-e2e -p 7474:7474 -p 7687:7687 \\
    -e NEO4J_AUTH=neo4j/legal-e2e-test neo4j:5-community

Then in .env:
  NEO4J_URI=bolt://localhost:7687
  NEO4J_USER=neo4j
  NEO4J_PASSWORD=legal-e2e-test
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

_root = Path(__file__).resolve().parent.parent
load_dotenv(_root / ".env", override=True)
sys.path.insert(0, str(_root))

from deep_researcher.legal.models import (  # noqa: E402
    CaseMetadata,
    CaseRecord,
    CitationRelationship,
    LegalIssue,
    PrecedentRelationship,
    RatioDecidendi,
    StatuteReference,
    TaxonomyTag,
)
from deep_researcher.legal.neo4j_graph import legal_neo4j_from_env  # noqa: E402


def _sample_record() -> CaseRecord:
    jid = "e2e-test-001"
    return CaseRecord(
        judgment_id=jid,
        metadata=CaseMetadata(
            case_name="Test State v. Demo Respondent",
            court="Supreme Court of India",
            bench="J. Example",
            judgment_date=date(2026, 1, 15),
            citation_string="(2026) 1 SCC 999",
        ),
        citation_relationships=[
            CitationRelationship(
                source_case_id=jid,
                target_case_id="unresolved:(1996) 2 SCC 384",
                relationship=PrecedentRelationship.RELIES_ON,
                citation_text="(1996) 2 SCC 384",
            ),
        ],
        statutes=[
            StatuteReference(
                statute="Code of Criminal Procedure",
                section="482",
                paragraph=12,
            ),
        ],
        issues=[
            LegalIssue(
                issue_text="Whether the appeal is maintainable?",
                supporting_paragraphs=[5, 6],
            ),
        ],
        ratio=RatioDecidendi(
            ratio="Courts may exercise inherent jurisdiction sparingly.",
            supporting_paragraphs=[40],
        ),
        taxonomy_tags=[
            TaxonomyTag(path=["Criminal Law", "Procedure", "Appeal"]),
        ],
        case_summary="Synthetic E2E record for Neo4j verification.",
    )


def _verify(session, expected_jid: str) -> None:
    q = """
    MATCH (c:Case {judgment_id: $jid})
    OPTIONAL MATCH (c)-[pr:RELIES_ON]->(t:Case)
    OPTIONAL MATCH (c)-[:REFERENCES_STATUTE]->(s:Statute)
    OPTIONAL MATCH (c)-[:ADDRESSES]->(i:Issue)
    OPTIONAL MATCH (c)-[:CLASSIFIED_AS]->(top:Topic)
    RETURN c.case_name AS name,
           c.court AS court,
           type(pr) AS rel_type,
           t.judgment_id AS target_id,
           collect(DISTINCT s.act + ' ' + coalesce(s.section,'')) AS statutes,
           count(DISTINCT i) AS issues,
           count(DISTINCT top) AS topics
    """
    row = session.run(q, jid=expected_jid).single()
    print("\n--- Cypher verification (MATCH Case + edges) ---")
    if not row or row["name"] is None:
        raise RuntimeError(f"No Case node for judgment_id={expected_jid!r}")
    print(f"  case_name: {row['name']}")
    print(f"  court:     {row['court']}")
    print(f"  RELIES_ON: -> {row['target_id']}")
    print(f"  statutes:  {row['statutes']}")
    print(f"  issues:    {row['issues']}")
    print(f"  topics:    {row['topics']}")

    counts = session.run(
        """
        MATCH (c:Case) WITH count(c) AS cases
        MATCH (s:Statute) WITH cases, count(s) AS statutes
        MATCH (i:Issue) WITH cases, statutes, count(i) AS issues
        MATCH ()-[r]->() WITH cases, statutes, issues, count(r) AS rels
        RETURN cases, statutes, issues, rels
        """
    ).single()
    print("\n--- Graph counts ---")
    print(f"  Case nodes: {counts['cases']}")
    print(f"  Statute nodes: {counts['statutes']}")
    print(f"  Issue nodes: {counts['issues']}")
    print(f"  Total relationships: {counts['rels']}")


def main() -> int:
    print("=== Neo4j legal graph E2E (synthetic CaseRecord, no LLM) ===\n")
    store = legal_neo4j_from_env()
    if store is None:
        print(
            "NEO4J_URI and NEO4J_PASSWORD are not both set. Add them to .env or use the Docker snippet in this script's docstring.",
            file=sys.stderr,
        )
        return 1

    record = _sample_record()
    print(f"Syncing judgment_id={record.judgment_id!r} ...")
    try:
        store.sync_case_record(record)
    except Exception as e:
        print(f"sync_case_record failed: {e}", file=sys.stderr)
        store.close()
        return 2

    with store._driver.session(database=store._database) as session:
        _verify(session, record.judgment_id or "")

    store.close()
    print("\n=== E2E OK ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Neo4j legal graph helpers (no live DB required for env helper test)."""

import pytest


def test_legal_neo4j_from_env_returns_none_without_uri(monkeypatch):
    monkeypatch.delenv("NEO4J_URI", raising=False)
    monkeypatch.delenv("DR_NEO4J_URI", raising=False)
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
    monkeypatch.delenv("DR_NEO4J_PASSWORD", raising=False)

    from deep_researcher.legal.neo4j_graph import legal_neo4j_from_env

    assert legal_neo4j_from_env() is None

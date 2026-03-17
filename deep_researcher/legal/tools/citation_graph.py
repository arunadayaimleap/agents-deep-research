"""Update precedent graph (citation relationships) in storage."""

from typing import List, Optional

from ..models import CitationRelationship


async def update_citation_graph(
    relationships: List[CitationRelationship],
    db: Optional[object] = None,
) -> None:
    """
    Persist citation relationships to the graph DB / adjacency store.

    db: object with .insert_citation_relationships(relationships) or similar.
    If db is None, no-op.
    """
    if not db or not relationships:
        return
    try:
        if hasattr(db, "insert_citation_relationships"):
            db.insert_citation_relationships(relationships)
    except Exception:
        pass

"""Sequential legal pipeline: judgment text -> structured CaseRecord."""

import asyncio
import uuid
from typing import List, Optional

from ..llm_config import LLMConfig
from ..tools.pdf_tools import extract_text

from .models import (
    CaseRecord,
    CaseMetadata,
    Citation,
    CitationRelationship,
    PrecedentRelationship,
    RatioDecidendi,
    Headnote,
    TaxonomyTag,
)
from .tools.citation_extraction import extract_citations
from .tools.statute_extraction import extract_statutes
from .tools.text_cleaning import run_text_cleaning
from .tools.metadata_extraction import run_metadata_extraction
from .tools.precedent_classifier import run_precedent_classifier
from .tools.issue_detection import run_issue_detection
from .tools.ratio_extraction import run_ratio_extraction
from .tools.headnote_generator import run_headnote_generator
from .tools.taxonomy_classifier import run_taxonomy_classifier
from .tools.case_summary import run_case_summary
from .tools.citation_resolver import resolve_citations
from .tools.citation_graph import update_citation_graph


class LegalPipeline:
    """Orchestrates sequential judgment processing steps."""

    def __init__(
        self,
        config: LLMConfig,
        db: Optional[object] = None,
        graph_store: Optional[object] = None,
    ):
        self.config = config
        self.db = db
        self.graph_store = graph_store

    async def process_judgment(
        self,
        text: Optional[str] = None,
        pdf_path: Optional[str] = None,
        url: Optional[str] = None,
        docx_path: Optional[str] = None,
    ) -> CaseRecord:
        """
        Run the full pipeline: extract text (if needed), clean, extract metadata,
        citations, statutes, issues, ratio, headnotes, taxonomy, summary; resolve
        citations; update citation graph.
        """
        # 1. Extract text
        raw_text = await extract_text(
            text=text,
            pdf_path=pdf_path,
            url=url,
            docx_path=docx_path,
        )
        if not raw_text or len(raw_text.strip()) < 100:
            raise ValueError("Extracted text is empty or too short")

        # 2. Clean text
        cleaned_text = await run_text_cleaning(raw_text, self.config)

        # 3. Metadata
        metadata = await run_metadata_extraction(cleaned_text, self.config)
        judgment_id = str(uuid.uuid4())[:8]

        # 4. Citations (regex)
        citations = extract_citations(cleaned_text)

        # 5. Resolve citations (DB lookup)
        db_lookup = self.db if self.db and hasattr(self.db, "find_case_by_citation") else None
        citations = await resolve_citations(
            citations,
            source_case_id=judgment_id,
            db_lookup=db_lookup,
            config=self.config,
        )

        # 6. Precedent classification
        context_excerpt = cleaned_text[:8000]
        citation_texts = [c.citation_text for c in citations]
        classifications = await run_precedent_classifier(
            citation_texts,
            context_excerpt,
            self.config,
        )
        # Build citation relationships (source = this case, target = resolved id)
        citation_relationships: List[CitationRelationship] = []
        for cl in classifications:
            target_id = None
            for c in citations:
                if c.citation_text == cl.citation_text and c.resolved_case_id:
                    target_id = c.resolved_case_id
                    break
            if not target_id:
                target_id = f"unresolved:{cl.citation_text}"
            citation_relationships.append(
                CitationRelationship(
                    source_case_id=judgment_id,
                    target_case_id=target_id,
                    relationship=cl.relationship,
                    citation_text=cl.citation_text,
                )
            )

        # 7. Statutes (regex)
        statutes = extract_statutes(cleaned_text)

        # 8. Issues
        issues = await run_issue_detection(cleaned_text, self.config)

        # 9. Ratio
        ratio = await run_ratio_extraction(cleaned_text, self.config)

        # 10. Headnotes
        headnotes = await run_headnote_generator(cleaned_text, self.config)

        # 11. Taxonomy
        taxonomy_tags = await run_taxonomy_classifier(cleaned_text, self.config)

        # 12. Summary
        case_summary = await run_case_summary(cleaned_text, self.config)

        # 13. Citation graph
        await update_citation_graph(citation_relationships, self.db)

        # 14. Build record
        record = CaseRecord(
            judgment_id=judgment_id,
            metadata=metadata,
            citations=citations,
            citation_relationships=citation_relationships,
            statutes=statutes,
            issues=issues,
            ratio=ratio,
            headnotes=headnotes,
            taxonomy_tags=taxonomy_tags,
            case_summary=case_summary,
            raw_text=None,
        )
        # 15. Save to MongoDB
        if self.db and hasattr(self.db, "insert_case"):
            self.db.insert_case(record)

        # 16. Sync to Neo4j (optional; driver is sync — offload to thread)
        if self.graph_store and hasattr(self.graph_store, "sync_case_record"):
            await asyncio.to_thread(self.graph_store.sync_case_record, record)

        return record

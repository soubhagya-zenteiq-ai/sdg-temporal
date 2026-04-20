from temporalio import workflow
from temporalio.common import RetryPolicy
from datetime import timedelta
import asyncio

# Import activities (IMPORTANT: use inside workflow-safe import)
with workflow.unsafe.imports_passed_through():
    from app.activities.parse_md import parse_md
    from app.activities.chunk_md import chunk_md
    from app.activities.generate_kb import generate_kb_chunk
    from app.activities.generate_qa import generate_qa_chunk
    from app.activities.store_results import store_results

    from app.schemas.pydantic_models import (
        ParsedMarkdown,
        Chunk,
        KBEntry,
        QAPair,
        StoreResult
    )


@workflow.defn
class MarkdownProcessingWorkflow:
    """
    Orchestrates full pipeline:
    MD → chunks → KB + QA → PostgreSQL
    """

    @workflow.run
    async def run(self, file_path: str) -> dict:
        """
        Entry point for workflow.
        """

        # =========================
        # 1. Parse Markdown
        # =========================
        parsed_dict = await workflow.execute_activity(
            parse_md,
            file_path,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )

        parsed = ParsedMarkdown(**parsed_dict)

        # =========================
        # 2. Chunk Markdown
        # =========================
        chunks_dict = await workflow.execute_activity(
            chunk_md,
            parsed.model_dump(),
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )

        chunks = [Chunk(**c) for c in chunks_dict]

        # =========================
        # 3 & 4. Parallel KB & QA per chunk
        # =========================
        
        # Prepare activity inputs
        chunk_dicts = [c.model_dump() for c in chunks]

        # Execute activities in parallel
        # Note: We use workflow-safe execution
        kb_tasks = [
            workflow.execute_activity(
                generate_kb_chunk,
                cd,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(maximum_attempts=2)
            )
            for cd in chunk_dicts
        ]

        qa_tasks = [
            workflow.execute_activity(
                generate_qa_chunk,
                cd,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(maximum_attempts=2)
            )
            for cd in chunk_dicts
        ]

        # Wait for all results
        kb_results = await asyncio.gather(*kb_tasks)
        qa_results_nested = await asyncio.gather(*qa_tasks)

        # Reconstitution & Deduplication
        kb_entries = [KBEntry(**k) for k in kb_results]
        
        # Flatten and deduplicate QAs
        seen_questions = set()
        qa_pairs = []
        for qlist in qa_results_nested:
            for q in qlist:
                question_text = q["question"].strip().lower()
                if question_text not in seen_questions:
                    seen_questions.add(question_text)
                    qa_pairs.append(QAPair(**q))

        # =========================
        # 5. Store Results
        # =========================
        result = await workflow.execute_activity(
            store_results,
            args=[
                parsed.model_dump(),
                [c.model_dump() for c in chunks],
                [k.model_dump() for k in kb_entries],
                [q.model_dump() for q in qa_pairs]
            ],
            start_to_close_timeout=timedelta(minutes=3),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )

        store_result = StoreResult(**result)

        # =========================
        # FINAL OUTPUT
        # =========================
        return {
            "document_id": str(store_result.document_id),
            "chunks": len(chunks),
            "kb_entries": len(kb_entries),
            "qa_pairs": len(qa_pairs)
        }
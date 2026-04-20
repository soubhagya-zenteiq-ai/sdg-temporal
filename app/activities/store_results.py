from temporalio import activity
from app.db.repository import Repository


repo = Repository()


@activity.defn
def store_results(
    parsed: dict,
    chunks: list,
    kb_entries: list,
    qa_pairs: list
):
    """
    Stores everything into PostgreSQL.
    """

    # 1. Create document
    document_id = repo.create_document(
        file_path=parsed["file_path"],
        title=parsed["title"]
    )

    # 2. Insert chunks
    chunk_id_map = repo.insert_chunks(document_id, chunks)

    # 3. Insert KB
    repo.insert_kb(chunk_id_map, kb_entries)

    # 4. Insert QA
    repo.insert_qa(document_id, qa_pairs)

    return {"document_id": document_id}
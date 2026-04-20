from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.db.connection import SessionLocal
from app.db.models import Document, Chunk, KnowledgeBase, QAPair


class Repository:
    """
    DB access layer with idempotent-safe operations.
    """

    def __init__(self):
        self.db: Session = SessionLocal()

    # =========================
    # DOCUMENT
    # =========================
    def create_document(self, file_path: str, title: str):
        """
        Create or fetch existing document (idempotent).
        """
        existing = (
            self.db.query(Document)
            .filter(Document.file_path == file_path)
            .first()
        )

        if existing:
            return existing.id

        doc = Document(
            file_path=file_path,
            title=title
        )

        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)

        return doc.id

    # =========================
    # CHUNKS
    # =========================
    def insert_chunks(self, document_id, chunks: list):
        """
        Insert chunks and return mapping {chunk_index: chunk_id}
        """
        chunk_map = {}

        for chunk in chunks:
            existing = (
                self.db.query(Chunk)
                .filter(
                    Chunk.document_id == document_id,
                    Chunk.chunk_index == chunk["chunk_index"]
                )
                .first()
            )

            if existing:
                chunk_map[chunk["chunk_index"]] = existing.id
                continue

            db_chunk = Chunk(
                document_id=document_id,
                content=chunk["content"],
                chunk_index=chunk["chunk_index"]
            )

            self.db.add(db_chunk)
            self.db.flush()  # get ID without full commit

            chunk_map[chunk["chunk_index"]] = db_chunk.id

        self.db.commit()
        return chunk_map

    # =========================
    # KNOWLEDGE BASE
    # =========================
    def insert_kb(self, chunk_id_map: dict, kb_entries: list):
        """
        Insert KB entries linked to chunks.
        """
        for entry in kb_entries:
            chunk_id = chunk_id_map.get(entry["chunk_index"])
            if not chunk_id:
                continue

            existing = (
                self.db.query(KnowledgeBase)
                .filter(KnowledgeBase.chunk_id == chunk_id)
                .first()
            )

            if existing:
                continue

            kb = entry["kb"]

            db_kb = KnowledgeBase(
                chunk_id=chunk_id,
                summary=kb.get("summary"),
                key_points=kb.get("key_points"),
                entities=kb.get("entities"),
                relationships=kb.get("relationships"),
            )

            self.db.add(db_kb)

        self.db.commit()

    # =========================
    # QA PAIRS
    # =========================
    def insert_qa(self, document_id, qa_pairs: list):
        """
        Insert QA pairs (avoid duplicates).
        """
        for qa in qa_pairs:
            existing = (
                self.db.query(QAPair)
                .filter(
                    QAPair.document_id == document_id,
                    QAPair.question == qa.get("question")
                )
                .first()
            )

            if existing:
                continue

            db_qa = QAPair(
                document_id=document_id,
                question=qa.get("question"),
                answer=qa.get("answer"),
                difficulty=qa.get("difficulty"),
            )

            self.db.add(db_qa)

        self.db.commit()

    # =========================
    # CLEANUP
    # =========================
    def close(self):
        self.db.close()
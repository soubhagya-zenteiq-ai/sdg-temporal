from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID


# =========================
# PARSE OUTPUT
# =========================
class ParsedMarkdown(BaseModel):
    file_path: str
    title: str
    content: str


# =========================
# CHUNKING
# =========================
class Chunk(BaseModel):
    chunk_index: int
    content: str


class ChunkList(BaseModel):
    chunks: List[Chunk]


# =========================
# KNOWLEDGE BASE
# =========================
class KnowledgeBaseData(BaseModel):
    summary: Optional[str] = ""
    key_points: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)
    relationships: List[str] = Field(default_factory=list)


class KBEntry(BaseModel):
    chunk_index: int
    kb: KnowledgeBaseData


class KBList(BaseModel):
    entries: List[KBEntry]


# =========================
# QA PAIRS
# =========================
class QAPair(BaseModel):
    question: str
    answer: str
    difficulty: Optional[str] = "medium"


class QAList(BaseModel):
    qa_pairs: List[QAPair]


# =========================
# STORE RESULT RESPONSE
# =========================
class StoreResult(BaseModel):
    document_id: UUID


# =========================
# INTERNAL TRANSFER OBJECTS
# =========================
class WorkflowInput(BaseModel):
    file_path: str


class WorkflowOutput(BaseModel):
    document_id: UUID
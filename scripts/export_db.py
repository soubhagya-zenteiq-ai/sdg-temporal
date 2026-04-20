import os
import sys
import csv
from sqlalchemy.orm import Session

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import SessionLocal
from app.db.models import Document, Chunk, KnowledgeBase, QAPair

def export_to_txt(filename="db_export.txt"):
    session: Session = SessionLocal()
    try:
        docs = session.query(Document).all()
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write("=== SDG TEMPORAL DB EXPORT ===\n\n")
            
            for doc in docs:
                f.write(f"📄 DOCUMENT: {doc.title}\n")
                f.write(f"ID: {doc.id}\n")
                f.write(f"Path: {doc.file_path}\n")
                f.write("-" * 30 + "\n\n")
                
                # Fetch chunks
                chunks = session.query(Chunk).filter(Chunk.document_id == doc.id).order_by(Chunk.chunk_index).all()
                for chunk in chunks:
                    f.write(f"  📦 CHUNK {chunk.chunk_index}\n")
                    f.write(f"  Content: {chunk.content[:200]}...\n")
                    
                    # KB
                    kb = session.query(KnowledgeBase).filter(KnowledgeBase.chunk_id == chunk.id).first()
                    if kb:
                        f.write(f"    🧠 KB SUMMARY: {kb.summary}\n")
                        f.write(f"    Key Points: {kb.key_points}\n")
                        f.write(f"    Entities: {kb.entities}\n")
                        f.write(f"    Relationships: {kb.relationships}\n")
                    
                    f.write("\n")
                
                # QA
                qas = session.query(QAPair).filter(QAPair.document_id == doc.id).all()
                f.write(f"  ❓ Q&A PAIRS ({len(qas)} total):\n")
                for qa in qas:
                    f.write(f"    Q: {qa.question}\n")
                    f.write(f"    A: {qa.answer}\n")
                    f.write(f"    [{qa.difficulty.upper()}]\n\n")
                
                f.write("=" * 50 + "\n\n")
                
        print(f"✅ Exported to {filename}")

    finally:
        session.close()

if __name__ == "__main__":
    export_to_txt()

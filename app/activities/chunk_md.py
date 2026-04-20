from temporalio import activity
import re


MAX_CHUNK_SIZE = 1200  # characters (adjust later with tokenization)


def split_by_headings(content: str):
    sections = re.split(r"\n#+ ", content)
    return [s.strip() for s in sections if s.strip()]


@activity.defn
def chunk_md(parsed: dict) -> list:
    """
    Splits markdown into semantic chunks.
    """

    content = parsed["content"]

    sections = split_by_headings(content)

    chunks = []
    idx = 0

    for section in sections:
        if len(section) <= MAX_CHUNK_SIZE:
            chunks.append({
                "chunk_index": idx,
                "content": section
            })
            idx += 1
        else:
            # fallback splitting
            for i in range(0, len(section), MAX_CHUNK_SIZE):
                chunks.append({
                    "chunk_index": idx,
                    "content": section[i:i + MAX_CHUNK_SIZE]
                })
                idx += 1

    return chunks
from temporalio import activity
from pathlib import Path
import re


@activity.defn
def parse_md(file_path: str) -> dict:
    """
    Reads and cleans markdown file.
    Returns structured content.
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"{file_path} not found")

    content = path.read_text(encoding="utf-8")

    # Remove code blocks
    content = re.sub(r"```.*?```", "", content, flags=re.DOTALL)

    # Normalize whitespace
    content = re.sub(r"\n{3,}", "\n\n", content)

    # Extract title (first heading or filename)
    title_match = re.search(r"# (.+)", content)
    title = title_match.group(1).strip() if title_match else path.stem

    return {
        "file_path": file_path,
        "title": title,
        "content": content.strip()
    }
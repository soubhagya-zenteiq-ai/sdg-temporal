import asyncio
import uuid
from pathlib import Path

from temporalio.client import Client

from app.config.settings import get_settings
from app.workflows.md_workflow import MarkdownProcessingWorkflow

settings = get_settings()


async def start_workflow(client: Client, file_path: str):
    """
    Start a workflow for a single markdown file.
    """

    workflow_id = f"md-pipeline-{Path(file_path).stem}-{uuid.uuid4()}"

    result = await client.start_workflow(
        MarkdownProcessingWorkflow.run,
        file_path,
        id=workflow_id,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
    )

    print(f"✅ Started workflow: {workflow_id} for {file_path}")
    return result


async def process_directory(directory: str):
    """
    Scan directory and trigger workflows for all .md files.
    """

    client = await Client.connect(settings.TEMPORAL_HOST)

    md_files = list(Path(directory).glob("*.md"))

    if not md_files:
        print("⚠️ No markdown files found.")
        return

    print(f"📂 Found {len(md_files)} markdown files")

    tasks = []

    for file in md_files:
        tasks.append(start_workflow(client, str(file)))

    await asyncio.gather(*tasks)


async def process_single_file(file_path: str):
    """
    Trigger workflow for one file.
    """

    client = await Client.connect(settings.TEMPORAL_HOST)
    await start_workflow(client, file_path)


# =========================
# ENTRYPOINT
# =========================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Markdown → KB + QA Pipeline")

    parser.add_argument(
        "--file",
        type=str,
        help="Path to a single markdown file"
    )

    parser.add_argument(
        "--dir",
        type=str,
        help="Directory containing markdown files"
    )

    args = parser.parse_args()

    if args.file:
        asyncio.run(process_single_file(args.file))

    elif args.dir:
        asyncio.run(process_directory(args.dir))

    else:
        print("❌ Provide either --file or --dir")
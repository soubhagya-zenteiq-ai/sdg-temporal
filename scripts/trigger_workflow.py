import asyncio
import uuid
from pathlib import Path

from temporalio.client import Client

from app.config.settings import get_settings
from app.workflows.md_workflow import MarkdownProcessingWorkflow

settings = get_settings()


async def trigger_single_file(client: Client, file_path: str):
    """
    Trigger workflow for a single markdown file.
    """

    workflow_id = f"md-{Path(file_path).stem}-{uuid.uuid4()}"

    await client.start_workflow(
        MarkdownProcessingWorkflow.run,
        file_path,
        id=workflow_id,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
    )

    print(f"🚀 Started workflow: {workflow_id}")


async def trigger_directory(directory: str):
    """
    Trigger workflows for all .md files in a directory.
    """

    client = await Client.connect(settings.TEMPORAL_HOST)

    md_files = list(Path(directory).glob("*.md"))

    if not md_files:
        print("⚠️ No markdown files found")
        return

    print(f"📂 Found {len(md_files)} markdown files")

    tasks = []

    for file in md_files:
        tasks.append(trigger_single_file(client, str(file)))

    await asyncio.gather(*tasks)

    print("✅ All workflows triggered")


async def trigger_single(file_path: str):
    """
    Trigger workflow for one file.
    """
    client = await Client.connect(settings.TEMPORAL_HOST)
    await trigger_single_file(client, file_path)


# =========================
# ENTRYPOINT
# =========================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Trigger Temporal workflows")

    parser.add_argument(
        "--file",
        type=str,
        help="Path to markdown file"
    )

    parser.add_argument(
        "--dir",
        type=str,
        help="Directory containing markdown files"
    )

    args = parser.parse_args()

    if args.file:
        asyncio.run(trigger_single(args.file))

    elif args.dir:
        asyncio.run(trigger_directory(args.dir))

    else:
        print("❌ Provide --file or --dir")
import asyncio
from datetime import timedelta

from temporalio.client import Client
from temporalio.worker import Worker

# Workflows
from app.workflows.md_workflow import MarkdownProcessingWorkflow

# Activities
from app.activities.parse_md import parse_md
from app.activities.chunk_md import chunk_md
from app.activities.generate_kb import generate_kb_chunk
from app.activities.generate_qa import generate_qa_chunk
from app.activities.store_results import store_results

from app.config.settings import get_settings

settings = get_settings()


from concurrent.futures import ThreadPoolExecutor

async def main():
    """
    Starts Temporal worker and registers workflows + activities.
    """

    # Connect to Temporal server
    client = await Client.connect(settings.TEMPORAL_HOST)

    # Create worker
    with ThreadPoolExecutor(max_workers=10) as activity_executor:
        worker = Worker(
            client,
            task_queue=settings.TEMPORAL_TASK_QUEUE,

            workflows=[MarkdownProcessingWorkflow],

            activities=[
                parse_md,
                chunk_md,
                generate_kb_chunk,
                generate_qa_chunk,
                store_results,
            ],

            activity_executor=activity_executor,

            # Optional but recommended tuning
            max_concurrent_activities=5,
            max_concurrent_workflow_tasks=5,
        )

        print("🚀 Worker started. Listening on task queue:", settings.TEMPORAL_TASK_QUEUE)

        await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
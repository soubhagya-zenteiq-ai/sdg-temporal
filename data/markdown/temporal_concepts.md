# Temporal Orchestration: Building Resilient Systems

Temporal is an open-source workflow orchestration engine used to build and operate resilient applications. It allows developers to write code that is "invincible" to common infrastructure failures.

## What is a Workflow?

In Temporal, a Workflow is a stateful function. It can run for seconds, days, or even years. The magic of Temporal is that the workflow state (variables, stacks, local state) is automatically persisted.

### Key Components

1. **Temporal Server**: The central brain that maintains the state and history of execution.
2. **Worker**: Your code that hosts the Workflows and Activities. Workers poll the Temporal server for tasks.
3. **Activity**: A function that performs an external action (like calling an API, writing to a DB, or running an LLM). Activities can have complex retry policies.

## Handling Failures

Traditional code fails when a server reboots or a network cable is unplugged. In Temporal, the system simply "pauses." When the worker comes back online, it resumes from the exact line of code where it stopped.

### Why use Temporal for AI Pipelines?
AI tasks (like LLM inference) are slow and prone to timeouts.
- **Retries**: If an LLM times out, Temporal retries the activity automatically.
- **State management**: If you are processing 1000 files, Temporal tracks exactly which ones are finished.
- **Parallelism**: Using `asyncio.gather` in a workflow allows fanning out tasks across multiple workers easily.

## Task Queues
Workers listen on specific Task Queues. This allows you to route tasks to different hardware. For example:
- Send "Data Cleaning" to a cheap CPU worker.
- Send "LLM Inference" to a GPU-powered worker.

## Conclusion
Temporal shifts the burden of reliability from the developer to the infrastructure, allowing you to focus on business logic rather than error handling code.

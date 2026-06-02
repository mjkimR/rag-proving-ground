"""Small SDK client for testing the local Aegra server."""

import asyncio
import os

from langgraph_sdk import get_client


async def main() -> None:
    url = os.getenv("AEGRA_URL", "http://localhost:2026")
    prompt = os.getenv("AEGRA_PROMPT", "langgraph와 aegra를 한 문단으로 설명해줘")

    client = get_client(url=url)
    thread = await client.threads.create()

    async for chunk in client.runs.stream(
        thread_id=thread["thread_id"],
        assistant_id="agent",
        input={"messages": [{"type": "human", "content": prompt}]},
        stream_mode=["messages-tuple"],
    ):
        if getattr(chunk, "data", None):
            print(chunk.data)


if __name__ == "__main__":
    asyncio.run(main())

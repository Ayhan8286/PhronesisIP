import httpx
import asyncio

async def test_stream():
    url = "http://localhost:8000/api/v1/drafting/generate"
    data = {
        "description": "A hospital voice assistant that routes commands",
        "technical_field": "Digital Health"
    }

    print("Sending request...")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream("POST", url, json=data) as resp:
                print(f"Status: {resp.status_code}")
                async for chunk in resp.aiter_text():
                    print(chunk, end="")
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(test_stream())

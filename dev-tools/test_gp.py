import asyncio
import httpx
from urllib.parse import quote_plus

async def test():
    q = "voice assistant"
    url = f"https://patents.google.com/xhr/query?url=q%3D{quote_plus(q)}%26num%3D5&exp="
    print(f"Making request to: {url}")
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        })
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            total = data.get("results", {}).get("total_num_results", 0)
            print(f"Total results: {total}")
            cluster = data.get("results", {}).get("cluster", [])
            for g in cluster[:1]:
                for r in g.get("result", [])[:3]:
                    p = r.get("patent", {})
                    print(f"  {p.get('publication_number')}: {p.get('title','')[:60]}")
        else:
            print(f"Response: {resp.text[:200]}")

asyncio.run(test())

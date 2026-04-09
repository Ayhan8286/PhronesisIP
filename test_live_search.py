import httpx
import json

URL = "https://phronesisip-gumsumqi7-ayhan8286s-projects.vercel.app/api/v1/search/"

payload = {
    "query": "pizza delivery invention",
    "search_type": "semantic",
    "top_k": 5
}

def test_search():
    print(f"Testing search at {URL}...")
    # Note: This will likely 403 because we don't have a Clerk token here
    # but we can see if it's a 403 (Auth) or 500 (DB Error)
    try:
        response = httpx.post(URL, json=payload, timeout=10.0)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_search()

import asyncio
import uuid
import sys
import os

# Add apps/api to sys.path
sys.path.append(os.path.join(os.getcwd()))

from app.services.epo_ops import epo_client
from app.config import settings

async def test_epo():
    print(f"Testing EPO with Client ID: {settings.EPO_CLIENT_ID[:5]}...")
    
    try:
        # 1. Test Search
        query = 'ti="pizza"'
        print(f"Running search for: {query}")
        results = await epo_client.search(query, max_results=5)
        
        # DEBUG: Print raw response if empty
        if not results.get("patents"):
            print("DEBUG: Results structure is empty. Check parsing.")
        
        print(f"Results found: {results.get('total', 0)}")
        for i, p in enumerate(results.get("patents", [])):
            print(f"{i+1}. {p['patent_number']} - {p['title']}")
            
        if results.get("patents"):
            print("\nSUCCESS: EPO Integration is working!")
        else:
            print("\nWARNING: No results found (might be query or EPO being EPO).")
            
    except Exception as e:
        print(f"\nFAILED: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_epo())

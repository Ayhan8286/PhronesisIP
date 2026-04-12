"""
European Patent Office (EPO) Open Patent Services (OPS).
Handles OAuth2 authentication and patent search via the EPO REST APIs.
Supports the modern MyEPO Machine-to-Machine (M2M) OIDC flow.
"""

import time
import uuid
import logging
from typing import Optional, List, Dict, Any

import httpx
from app.config import settings

logger = logging.getLogger(__name__)

# --- EPO Constants ---
# Production Token URL for MyEPO M2M
EPO_TOKEN_URL = "https://ops.epo.org/3.2/auth/accesstoken"
EPO_BASE_URL = "http://ops.epo.org/3.2/rest-services"

class EPOClient:
    """
    Client for interacting with the European Patent Office (EPO) APIs.
    Handles automatic OAuth2 token management.
    """
    
    def __init__(self):
        self.client_id = settings.EPO_CLIENT_ID
        self.client_secret = settings.EPO_CLIENT_SECRET
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0
        
    async def _get_access_token(self) -> str:
        """
        Retrieves a valid OAuth2 access token, using an in-memory cache if it's still valid.
        """
        # Return cached token if still valid (with 60s buffer)
        if self._access_token and time.time() < self._token_expires_at - 60:
            return self._access_token

        if not self.client_id or not self.client_secret:
            raise ValueError("EPO_CLIENT_ID and EPO_CLIENT_SECRET must be configured.")

        logger.info("Fetching new access token from EPO...")
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                EPO_TOKEN_URL,
                auth=(self.client_id, self.client_secret),
                data={"grant_type": "client_credentials"},
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if resp.status_code != 200:
                logger.error(f"Failed to authenticate with EPO: {resp.text}")
                raise Exception(f"EPO Authentication Failed: {resp.status_code}")
                
            data = resp.json()
            self._access_token = data["access_token"]
            expires_in = int(data.get("expires_in", 3600))
            self._token_expires_at = time.time() + expires_in
            
            return self._access_token

    async def search(self, query: str, max_results: int = 20) -> Dict[str, Any]:
        """
        Search for patents in the EPO database using the OPS search service.
        Query follows the CQL (Command Query Language) format.
        """
        if not self.client_id:
            return {"patents": [], "total": 0, "error": "EPO not configured"}

        token = await self._get_access_token()
        
        # Endpoint for bibliographic search
        endpoint = f"{EPO_BASE_URL}/published-data/search/biblio"
        
        params = {
            "q": query,
            "Range": f"1-{max_results}"
        }
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(endpoint, params=params, headers=headers)
            
            if resp.status_code == 404:
                return {"patents": [], "total": 0}
            elif resp.status_code != 200:
                logger.warning(f"EPO search returned error: {resp.status_code} - {resp.text}")
                return {"patents": [], "total": 0, "error": resp.text}
                
            data = resp.json()
            return self._parse_search_results(data)

    def _parse_search_results(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parses the complex EPO JSON response. 
        Uses a recursive search to find the results because the nested structure
        varies depending on whether 0, 1, or many results are returned.
        """
        def find_key_recursive(obj: Any, target_key: str) -> List[Any]:
            """Helper to find all occurrences of a key in a nested dict/list."""
            results = []
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k == target_key:
                        results.append(v)
                    else:
                        results.extend(find_key_recursive(v, target_key))
            elif isinstance(obj, list):
                for item in obj:
                    results.extend(find_key_recursive(item, target_key))
            return results

        try:
            # 1. Find the total count (usually @total-result-count)
            counts = find_key_recursive(data, "@total-result-count")
            total_count = int(counts[0]) if counts else 0
            
            # 2. Find all publication references
            # In OPS JSON, these are usually nested under ops:biblio-search -> ops:search-result -> ops:publication-reference
            pub_refs = find_key_recursive(data, "ops:publication-reference")
            if not pub_refs:
                # Try without prefix
                pub_refs = find_key_recursive(data, "publication-reference")
            
            # Flatten if we found a list of lists
            flat_refs = []
            for item in pub_refs:
                if isinstance(item, list):
                    flat_refs.extend(item)
                else:
                    flat_refs.append(item)
                
            def _clean_val(v: Any) -> str:
                """Handles the weird {'$': 'val'} structure in some XML-to-JSON conversions."""
                if isinstance(v, dict) and "$" in v:
                    return str(v["$"])
                return str(v)

            patents = []
            for ref in flat_refs:
                # Each ref should be a publication reference with document-id
                doc_ids = find_key_recursive(ref, "document-id")
                if not doc_ids:
                    continue
                
                # Flatten doc_ids and pick the best format
                flat_ids = []
                for d in doc_ids:
                    if isinstance(d, list): flat_ids.extend(d)
                    else: flat_ids.append(d)
                
                # Prefer 'epodoc' format
                id_obj = next((d for d in flat_ids if d.get("@format") == "epodoc"), flat_ids[0])
                
                doc_num = _clean_val(id_obj.get("doc-number", ""))
                country = _clean_val(id_obj.get("country", ""))
                kind = _clean_val(id_obj.get("kind", ""))
                
                # Try to find a title in the biblio data if present
                title = "EP Patent Reference"
                abstract = "European Patent Office result."
                
                # EPO often puts titles in 'exchange-documents' or 'bibliographic-data'
                titles = find_key_recursive(ref, "invention-title")
                if titles:
                    # titles[0] might be {'@lang': 'en', '$': 'Title text'}
                    for t in titles:
                        if isinstance(t, dict) and t.get("@lang") == "en":
                            title = _clean_val(t)
                            break
                    if title == "EP Patent Reference":
                        title = _clean_val(titles[0])

                abstracts = find_key_recursive(ref, "abstract")
                if abstracts:
                    for a in abstracts:
                        # abstracts might be a list of dicts with lang
                        if isinstance(a, dict) and a.get("@lang") == "en":
                            p_tags = find_key_recursive(a, "p")
                            if p_tags:
                                abstract = " ".join([_clean_val(p) for p in p_tags])
                            break

                patents.append({
                    "patent_number": f"{country}{doc_num}{kind}",
                    "title": title,
                    "abstract": abstract,
                    "date": "",
                    "type": "international",
                    "source": "epo_ops",
                })
                
            return {"patents": patents, "total": total_count}
            
        except Exception as e:
            logger.error(f"Error parsing EPO response: {e}")
            return {"patents": [], "total": 0, "error": str(e)}

# Global instance
epo_client = EPOClient()

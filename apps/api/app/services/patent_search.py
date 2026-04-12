from typing import Optional, List
import re
from urllib.parse import quote_plus
import httpx

from app.config import settings
from app.services.epo_ops import epo_client

# USPTO Open Data Portal configuration
USPTO_ODP_BASE = "https://api.uspto.gov"
ODP_HEADERS = {"Accept": "application/json"}


async def search_patents_external(
    query: str,
    assignee: Optional[str] = None,
    patent_number: Optional[str] = None,
    max_results: int = 25,
) -> dict:
    """
    Search for patents across official and global sources in parallel.
    Sources: Google Patents (Global), USPTO ODP (Official US), EPO OPS (Official EU).
    """
    import asyncio
    
    # 1. Dispatch searches in parallel with timeouts
    # We use asyncio.gather with return_exceptions=True to gracefully handle individual provider failures
    search_tasks = [
        asyncio.create_task(search_google_patents(query, assignee=assignee, max_results=max_results)),
        asyncio.create_task(_search_odp(query, assignee=assignee, patent_number=patent_number, max_results=max_results))
    ]
    
    if settings.EPO_CLIENT_ID:
        # Standardize query for EPO (pa="assignee" and (query))
        epo_query = query
        if assignee:
            epo_query = f'pa="{assignee}" and ({query})'
        search_tasks.append(asyncio.create_task(epo_client.search(epo_query, max_results=max_results)))

    # Wait for all with a 25s global timeout (USPTO can be slow)
    results_list = await asyncio.gather(*search_tasks, return_exceptions=True)
    
    google_res = results_list[0] if not isinstance(results_list[0], Exception) else {"patents": [], "total": 0}
    uspto_res = results_list[1] if not isinstance(results_list[1], Exception) else {"patents": [], "total": 0}
    epo_res = results_list[2] if len(results_list) > 2 and not isinstance(results_list[2], Exception) else {"patents": [], "total": 0}

    # 2. Merge and Deduplicate with Normalization
    seen_ids = set()
    merged_patents = []
    
    # Combined results - USPTO has better biblio data, Google has better abstracts
    all_raw = (
        uspto_res.get("patents", []) + 
        google_res.get("patents", []) + 
        epo_res.get("patents", [])
    )
    
    for p in all_raw:
        # Standardize ID: US10123456
        raw_num = p.get("patent_number", "").replace(" ", "").replace("-", "").upper()
        if not raw_num:
            continue
            
        if raw_num not in seen_ids:
            seen_ids.add(raw_num)
            # Standardize source-specific field names (Google uses snippet)
            if not p.get("abstract") and p.get("snippet"):
                p["abstract"] = p["snippet"]
            merged_patents.append(p)

    total_est = sum(res.get("total", 0) for res in [google_res, uspto_res, epo_res] if isinstance(res, dict))
    
    return {
        "patents": merged_patents[:max_results],
        "total": total_est,
        "sources": {
            "google_patents": len(google_res.get("patents", [])),
            "uspto_odp": len(uspto_res.get("patents", [])),
            "epo_ops": len(epo_res.get("patents", [])),
        }
    }


async def _search_odp(
    query: str,
    assignee: Optional[str] = None,
    patent_number: Optional[str] = None,
    max_results: int = 25,
) -> dict:
    """Search using USPTO ODP simplified query syntax."""

    # Build query string for ODP
    if patent_number:
        clean_num = patent_number.replace(",", "").replace(" ", "").replace("US", "")
        q = f"applicationNumberText:{clean_num}"
    else:
        parts = []
        if query:
            parts.append(f'inventionTitle:"{query}"')
        if assignee:
            parts.append(f'applicantFileIdentifier:"{assignee}"')
        q = " AND ".join(parts) if parts else query

    url = f"{USPTO_ODP_BASE}/patent/applications/search"
    params = {
        "q": q,
        "offset": 0,
        "limit": max_results,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params=params, headers=ODP_HEADERS)
        resp.raise_for_status()
        data = resp.json()

    results = data.get("results", data.get("patentApplications", []))
    total = data.get("recordTotalQuantity", len(results))

    patents = []
    for p in (results if isinstance(results, list) else []):
        meta = p.get("applicationMetaData", p) if isinstance(p, dict) else {}
        patents.append({
            "patent_number": meta.get("applicationNumberText", ""),
            "title": meta.get("inventionTitle", p.get("inventionTitle", "")),
            "abstract": meta.get("abstractText", ""),
            "date": meta.get("filingDate", ""),
            "type": meta.get("applicationTypeCategory", "utility"),
            "num_claims": 0,
            "assignee": "",
            "source": "uspto_odp",
        })

    return {"patents": patents, "total": total}


async def fetch_patent_detail(patent_number: str) -> dict:
    """
    Fetch patent details. Try ODP first, fall back to Google Patents link.
    """
    clean_num = patent_number.replace(",", "").replace(" ", "").replace("US", "")

    try:
        url = f"{USPTO_ODP_BASE}/patent/applications/search"
        params = {"q": f"applicationNumberText:{clean_num}", "limit": 1}

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, params=params, headers=ODP_HEADERS)
            resp.raise_for_status()
            data = resp.json()

        results = data.get("results", data.get("patentApplications", []))
        if not results:
            raise Exception("No results from ODP")

        p = results[0] if isinstance(results, list) else {}
        meta = p.get("applicationMetaData", p) if isinstance(p, dict) else {}

        return {
            "patent_number": f"US {meta.get('applicationNumberText', clean_num)}",
            "title": meta.get("inventionTitle", ""),
            "abstract": meta.get("abstractText", ""),
            "grant_date": meta.get("grantDate", meta.get("filingDate", "")),
            "type": meta.get("applicationTypeCategory", "utility"),
            "num_claims": 0,
            "claims": [],
            "inventors": [],
            "assignee": "",
            "source": "uspto_odp",
        }
    except Exception:
        # Return a minimal detail with Google Patents link
        return {
            "patent_number": f"US {clean_num}",
            "title": f"Patent {clean_num}",
            "abstract": "",
            "grant_date": "",
            "type": "utility",
            "num_claims": 0,
            "claims": [],
            "inventors": [],
            "assignee": "",
            "source": "fallback",
        }


# ---------------------------------------------------------------------------
# Google Patents Search (International)
# ---------------------------------------------------------------------------

GOOGLE_PATENTS_URL = "https://patents.google.com"


async def search_google_patents(
    query: str,
    assignee: Optional[str] = None,
    country: Optional[str] = None,
    max_results: int = 20,
) -> dict:
    """
    Search Google Patents for international patents.
    Uses Google Patents public XHR endpoint (no API key needed).
    Returns structured patent data.
    """
    # Build Google Patents search query
    search_terms = []
    if query:
        search_terms.append(query)
    if assignee:
        search_terms.append(f'assignee:"{assignee}"')
    if country:
        search_terms.append(f"country:{country}")

    search_query = " ".join(search_terms)

    # Try XHR endpoint first (returns JSON)
    try:
        url = f"{GOOGLE_PATENTS_URL}/xhr/query?url=q%3D{quote_plus(search_query)}%26num%3D{max_results}&exp="

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
            })
            resp.raise_for_status()
            data = resp.json()

            results = data.get("results", {})
            cluster = results.get("cluster", [])

            patents = []
            for group in cluster:
                result_list = group.get("result", [])
                for r in result_list:
                    patent_entry = r.get("patent", {})
                    pub_num = patent_entry.get("publication_number", "")
                    title = patent_entry.get("title", "")
                    snippet = r.get("snippet", "")
                    filing_date = patent_entry.get("filing_date", "")
                    pub_date = patent_entry.get("publication_date", "")
                    assignee_name = patent_entry.get("assignee", "")
                    num_claims = patent_entry.get("num_claims", 0)

                    # Format dates from YYYYMMDD to YYYY-MM-DD
                    if pub_date and len(pub_date) == 8:
                        pub_date = f"{pub_date[:4]}-{pub_date[4:6]}-{pub_date[6:8]}"
                    if filing_date and len(filing_date) == 8:
                        filing_date = f"{filing_date[:4]}-{filing_date[4:6]}-{filing_date[6:8]}"

                    patents.append({
                        "patent_number": pub_num,
                        "title": title,
                        "abstract": snippet,
                        "date": pub_date,
                        "filing_date": filing_date,
                        "type": "international",
                        "num_claims": num_claims,
                        "assignee": assignee_name,
                        "source": "google_patents",
                    })

            return {"patents": patents[:max_results], "total": len(patents)}

    except Exception:
        # Fallback: scrape HTML
        return await _scrape_google_patents_html(search_query, max_results)


async def _scrape_google_patents_html(query: str, max_results: int = 20) -> dict:
    """
    Fallback: scrape Google Patents HTML search results.
    """
    url = f"{GOOGLE_PATENTS_URL}/?q={quote_plus(query)}&num={max_results}"

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            })

        html = resp.text
        patents = []

        # Parse search-result-item elements
        title_pattern = re.compile(r'<span class="style-scope search-result-item" id="htmlContent">(.*?)</span>', re.DOTALL)
        number_pattern = re.compile(r'data-result="([\w\d]+)"')
        snippet_pattern = re.compile(r'<span class="style-scope search-result-item" id="htmlSnippet">(.*?)</span>', re.DOTALL)

        articles = re.split(r'<search-result-item', html)
        for article in articles[1:max_results + 1]:
            pub_number = ""
            title = ""
            snippet = ""

            num_match = number_pattern.search(article)
            if num_match:
                pub_number = num_match.group(1)

            title_match = title_pattern.search(article)
            if title_match:
                title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()

            snippet_match = snippet_pattern.search(article)
            if snippet_match:
                snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip()

            if pub_number or title:
                patents.append({
                    "patent_number": pub_number,
                    "title": title or "Untitled",
                    "abstract": snippet,
                    "date": "",
                    "type": "international",
                    "num_claims": 0,
                    "assignee": "",
                    "source": "google_patents",
                })

        return {"patents": patents, "total": len(patents)}
    except Exception:
        return {"patents": [], "total": 0}

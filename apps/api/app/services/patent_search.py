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
    Search for patents using Google Patents (Global).
    """
    # 1. Search Google Patents (Broad, Global)
    search_terms = query
    if assignee:
        search_terms += f' assignee:"{assignee}"'
    if patent_number:
        search_terms += f" {patent_number}"

    google_results = await search_google_patents(
        search_terms,
        assignee=None,
        country=None,  # Search globally
        max_results=max_results,
    )

    # 2. Search EPO (Official European Source)
    epo_results = {"patents": [], "total": 0}
    if settings.EPO_CLIENT_ID:
        try:
            # Convert simple query to CQL-like for EPO
            epo_query = query
            if assignee:
                # Basic personal name or corp name search in EPO
                epo_query = f'pa="{assignee}" and ({query})'
            epo_results = await epo_client.search(epo_query, max_results=max_results)
        except Exception:
            pass

    # 3. Merge and Deduplicate
    all_patents = google_results.get("patents", []) + epo_results.get("patents", [])

    # Deduplicate by patent number
    seen = set()
    unique_patents = []
    for p in all_patents:
        pnum = p.get("patent_number", "").replace(" ", "").upper()
        if pnum and pnum not in seen:
            seen.add(pnum)
            unique_patents.append(p)

    return {
        "patents": unique_patents[:max_results],
        "total": max(google_results.get("total", 0), epo_results.get("total", 0)),
        "sources": ["google_patents"] + (["epo_ops"] if epo_results.get("patents") else [])
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

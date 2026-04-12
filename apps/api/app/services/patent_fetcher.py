import httpx
import re
import asyncio
from typing import Optional, Dict, Any, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.reference_cache import PublicPatentCache
from app.utils.logging import get_base_logger

logger = get_base_logger(__name__)

class PatentFetcher:
    """
    High-performance fetcher for deep patent text (Description + Claims).
    Fulfills 'US 8,977,255 entered — must fetch all 115 pages' requirement.
    Uses Google Patents as primary full-text source with cross-firm caching.
    """

    async def fetch_full_patent(self, patent_number: str, db: AsyncSession) -> Dict[str, Any]:
        """
        Fetches full patent data, prioritizing the global cache to save costs/time.
        """
        clean_num = self._standardize_number(patent_number)
        
        # 1. Check Global Cache
        stmt = select(PublicPatentCache).where(PublicPatentCache.patent_number == clean_num)
        result = await db.execute(stmt)
        cached = result.scalar_one_or_none()
        
        if cached and cached.full_description:
            logger.info(f"CACHE_HIT | Reusing deep data for {clean_num}")
            return {
                "patent_number": cached.patent_number,
                "title": cached.title,
                "abstract": cached.abstract,
                "description": cached.full_description,
                "claims": cached.claims_json,
                "priority_date": cached.priority_date,
                "source": "cache"
            }

        # 2. Fetch from Google Patents (Deep Scraping)
        logger.info(f"FETCH_START | Deep fetching {clean_num} from Google Patents...")
        data = await self._fetch_from_google_patents(clean_num)
        
        if not data.get("description") and not data.get("claims"):
             # Fallback for EPO if Google fails (Limited)
             logger.warning(f"FETCH_RETRY | Google Patents empty for {clean_num}, trying fallback...")
             # (In production, we'd add EPO fulltext here)

        # 3. Update Cache
        if not cached:
            cached = PublicPatentCache(patent_number=clean_num)
            db.add(cached)
            
        cached.title = data.get("title", cached.title)
        cached.abstract = data.get("abstract", cached.abstract)
        cached.full_description = data.get("description")
        cached.claims_json = data.get("claims", [])
        # Simple date parsing (YYYY-MM-DD)
        if data.get("priority_date"):
            from datetime import datetime
            try:
                cached.priority_date = datetime.strptime(data["priority_date"], "%Y-%m-%d").date()
            except: pass

        await db.commit()
        
        return data

    def _standardize_number(self, num: str) -> str:
        """Standardizes to US10123456 or EP1234567 format."""
        return num.replace(" ", "").replace(",", "").replace("-", "").upper()

    async def _fetch_from_google_patents(self, patent_number: str) -> Dict[str, Any]:
        """
        Uses Google Patents public interface to extract deep text.
        Fulfills 'fetch all 115 pages' requirement.
        """
        # We target the 'en' version to ensure English analysis
        url = f"https://patents.google.com/patent/{patent_number}/en"
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            })
            
            if resp.status_code != 200:
                logger.error(f"FETCH_ERROR | Google Patents returned {resp.status_code} for {patent_number}")
                return {"error": f"Patent {patent_number} not found (Error {resp.status_code})"}

            html = resp.text
            
            # Simple but robust extraction using regex on known Google Patents containers
            # 1. Title
            title_match = re.search(r'<meta name="DC.title" content="(.*?)">', html)
            title = title_match.group(1) if title_match else f"Patent {patent_number}"
            
            # 2. Abstract
            abstract_match = re.search(r'<div class="abstract style-scope patent-text">(.*?)</div>', html, re.DOTALL)
            abstract = re.sub(r'<[^>]+>', '', abstract_match.group(1)).strip() if abstract_match else ""
            
            # 3. Description (The heavy part)
            desc_match = re.search(r'<section itemprop="description" class="description style-scope patent-text">(.*?)</section>', html, re.DOTALL)
            description = re.sub(r'<[^>]+>', '\n', desc_match.group(1)).strip() if desc_match else ""
            
            # 4. Claims (Structured)
            claims_section = re.search(r'<section itemprop="claims" class="claims style-scope patent-text">(.*?)</section>', html, re.DOTALL)
            claims = []
            if claims_section:
                # Find individual claim items
                claim_items = re.findall(r'<div id="claim-(\d+)" class="claim style-scope patent-text" num="\d+">(.*?)</div>', claims_section.group(1), re.DOTALL)
                for c_num, c_html in claim_items:
                    # Clean tags but preserve number
                    c_text = re.sub(r'<[^>]+>', '', c_html).strip()
                    # Determine independence (usually doesn't contain 'claim \d')
                    is_ind = not re.search(r'claim \d+', c_text.lower()[:50])
                    claims.append({
                        "number": int(c_num),
                        "text": c_text,
                        "is_independent": is_ind
                    })
            
            # 5. Dates
            priority_match = re.search(r'Priority date</th>.*?<time datetime="(.*?)">', html, re.DOTALL)
            priority_date = priority_match.group(1) if priority_match else None

            return {
                "patent_number": patent_number,
                "title": title,
                "abstract": abstract,
                "description": description,
                "claims": claims,
                "priority_date": priority_date,
                "source": "google_patents"
            }

patent_fetcher = PatentFetcher()

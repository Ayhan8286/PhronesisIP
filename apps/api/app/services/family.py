import uuid
from typing import List, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Patent, PatentFamily

class FamilyService:
    """
    Intelligent family tracking for global patent portfolios.
    Fulfills 'US patent and its EP equivalent linked as family' requirement.
    """

    async def auto_link_family(self, patent_id: uuid.UUID, db: AsyncSession):
        """
        Automatically identifies and links family members based on shared inventors
        and priority dates.
        """
        patent = await db.get(Patent, patent_id)
        if not patent or not patent.priority_date:
            return

        # 1. Search for other patents with the same priority_date in the same firm
        # (Excluding the current one)
        query = select(Patent).where(
            and_(
                Patent.firm_id == patent.firm_id,
                Patent.priority_date == patent.priority_date,
                Patent.id != patent.id
            )
        )
        result = await db.execute(query)
        candidates = result.scalars().all()

        if not candidates:
            return

        # 2. Check for inventor overlap (Simplified: at least one matching name)
        # Assuming inventors is a list of dicts: [{"name": "John Doe"}, ...]
        p_inventors = {i.get("name", "").lower() for i in (patent.inventors or []) if i.get("name")}
        
        family_members = []
        for cand in candidates:
            c_inventors = {i.get("name", "").lower() for i in (cand.inventors or []) if i.get("name")}
            if p_inventors.intersection(c_inventors):
                family_members.append(cand)

        if not family_members:
            return

        # 3. Create or join existing family
        # Check if any detected member already has a family_id
        family_id = patent.family_id
        if not family_id:
            for m in family_members:
                if m.family_id:
                    family_id = m.family_id
                    break

        if not family_id:
            # Create a new family group
            new_family = PatentFamily(
                id=uuid.uuid4(),
                firm_id=patent.firm_id,
                family_name=f"Family: {patent.title[:50]}...",
                description=f"Auto-detected family for {patent.application_number}"
            )
            db.add(new_family)
            family_id = new_family.id

        # Update all members to this family_id
        patent.family_id = family_id
        for m in family_members:
            m.family_id = family_id
        
        await db.commit()
        return family_id

    async def identify_coverage_gaps(self, family_id: uuid.UUID, db: AsyncSession) -> List[str]:
        """
        Identifies major markets where a patent family has NO coverage.
        Fulfills 'Coverage gaps identified automatically' requirement.
        """
        query = select(Patent).where(Patent.family_id == family_id)
        result = await db.execute(query)
        members = result.scalars().all()
        
        # Extract country prefixes (e.g., US, EP, CN, JP)
        # Note: application_number usually starts with country code or we check classification
        countries = set()
        for m in members:
            app_num = m.application_number or ""
            if app_num.startswith("US"): countries.add("US")
            elif app_num.startswith("EP"): countries.add("EP")
            elif app_num.startswith("CN"): countries.add("CN")
            elif app_num.startswith("JP"): countries.add("JP")
            elif app_num.startswith("WO"): countries.add("WO")

        gaps = []
        major_markets = ["US", "EP", "CN", "JP"]
        for m in major_markets:
            if m not in countries:
                gaps.append(m)
        
        return gaps

family_service = FamilyService()

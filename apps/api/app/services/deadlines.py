import uuid
from datetime import date, datetime, timedelta
from typing import List, Optional
from dateutil.relativedelta import relativedelta
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Patent, PatentDeadline, OfficeAction

class DeadlineService:
    """
    Core engine for calculating and managing patent-related legal deadlines.
    Fulfills the 'Deadline tracking' requirements of the production checklist.
    """

    async def recalculate_deadlines(self, patent_id: uuid.UUID, db: AsyncSession):
        """
        Recalculates all automated deadlines for a patent based on its current metadata.
        """
        patent = await db.get(Patent, patent_id)
        if not patent:
            return

        # 1. Clear existing PENDING automated deadlines
        await db.execute(
            delete(PatentDeadline).where(
                PatentDeadline.patent_id == patent_id,
                PatentDeadline.status == "PENDING"
            )
        )

        new_deadlines = []

        # 2. Maintenance Fees (US specific: 3.5, 7.5, 11.5 years from Grant)
        if patent.grant_date and patent.application_number.startswith(("US", "1", "2")):
            intervals = [
                (3, 6, "1st Maintenance Fee (3.5 Year)"),
                (7, 6, "2nd Maintenance Fee (7.5 Year)"),
                (11, 6, "3rd Maintenance Fee (11.5 Year)")
            ]
            for years, months, desc in intervals:
                due_date = patent.grant_date + relativedelta(years=years, months=months)
                if due_date > date.today():
                    new_deadlines.append(PatentDeadline(
                        patent_id=patent.id,
                        firm_id=patent.firm_id,
                        deadline_type="MAINTENANCE_FEE",
                        description=desc,
                        due_date=due_date,
                        status="PENDING"
                    ))

        # 3. PCT National Phase (Global: 30 months from Priority Date)
        if patent.priority_date and "PCT" in (patent.application_number or ""):
            due_date = patent.priority_date + relativedelta(months=30)
            if due_date > date.today():
                new_deadlines.append(PatentDeadline(
                    patent_id=patent.id,
                    firm_id=patent.firm_id,
                    deadline_type="PCT_NATIONAL_PHASE",
                    description="PCT National Phase Entry (30 Month)",
                    due_date=due_date,
                    status="PENDING"
                ))

        # 4. Office Action Responses (Grant date + 3 months or OA date + 3 months)
        # We check the office_actions table
        result = await db.execute(
            select(OfficeAction).where(OfficeAction.patent_id == patent_id)
        )
        for oa in result.scalars().all():
            if oa.mailing_date:
                due_date = oa.mailing_date + relativedelta(months=3)
                if due_date > date.today():
                    new_deadlines.append(PatentDeadline(
                        patent_id=patent.id,
                        firm_id=patent.firm_id,
                        deadline_type="OA_RESPONSE",
                        description=f"Response to Office Action dated {oa.mailing_date}",
                        due_date=due_date,
                        status="PENDING"
                    ))

        # 5. License Expiry (For external licenses)
        if patent.ownership_type == "LICENSED" and patent.license_expiry:
            if patent.license_expiry > date.today():
                new_deadlines.append(PatentDeadline(
                    patent_id=patent.id,
                    firm_id=patent.firm_id,
                    deadline_type="LICENSE_EXPIRY",
                    description=f"License for {patent.title} is reaching its end of term.",
                    due_date=patent.license_expiry,
                    status="PENDING"
                ))

        if new_deadlines:
            db.add_all(new_deadlines)
        
        await db.commit()
        return len(new_deadlines)

    async def mark_complete(self, deadline_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession):
        """Marks a deadline as completed."""
        deadline = await db.get(PatentDeadline, deadline_id)
        if deadline:
            deadline.status = "COMPLETED"
            deadline.completed_at = datetime.now()
            deadline.completed_by = user_id
            await db.commit()
            return True
        return False

deadline_service = DeadlineService()

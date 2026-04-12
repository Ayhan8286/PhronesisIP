import uuid
from datetime import date, datetime
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import PatentDeadline, Patent, User
from app.utils.logging import get_base_logger

logger = get_base_logger(__name__)

class AlertService:
    """
    Dispatcher for automated deadline alerts (90, 60, 30 days).
    Fulfills 'Email alert sent 90/60/30 days before deadline' requirements.
    """

    async def dispatch_daily_alerts(self, db: AsyncSession):
        """
        Finds all active deadlines that hit the 90, 60, or 30 day thresholds
        and triggers a mock email alert.
        """
        today = date.today()
        thresholds = [90, 60, 30]
        
        # Calculate target dates for alerts
        target_dates = {t: today + relativedelta(days=t) for t in thresholds}
        
        # We check for deadlines due exactly on those target dates
        # AND that haven't been alerted for those thresholds yet (bitmask alert_flags)
        # thresholds[0]=90 -> flag 1, [1]=60 -> flag 2, [2]=30 -> flag 4
        
        for i, t in enumerate(thresholds):
            target_date = today + relativedelta(days=t)
            flag = 1 << i
            
            stmt = select(PatentDeadline).where(
                and_(
                    PatentDeadline.due_date == target_date,
                    PatentDeadline.status == "PENDING",
                    (PatentDeadline.alert_flags & flag) == 0
                )
            )
            result = await db.execute(stmt)
            deadlines = result.scalars().all()
            
            for d in deadlines:
                await self._send_mock_email(d, t, db)
                # Update alert flags
                d.alert_flags |= flag
                
        await db.commit()

    async def _send_mock_email(self, deadline: PatentDeadline, threshold: int, db: AsyncSession):
        """
        Simulates an email send with bank-grade logging.
        """
        # Load patent and firm title
        patent = await db.get(Patent, deadline.patent_id)
        
        subject = f"Friendly Reminder: {deadline.deadline_type} due in {threshold} days"
        if threshold <= 30:
            subject = f"URGENT: Legal Deadline Approach - {deadline.deadline_type} in {threshold} days"
            
        message = (
            f"Dear Attorney,\n\n"
            f"This is an automated alert for Patent {patent.application_number or patent.patent_number} ({patent.title}).\n"
            f"Type: {deadline.deadline_type}\n"
            f"Due Date: {deadline.due_date}\n"
            f"Description: {deadline.description}\n\n"
            f"Please ensure the necessary action is taken to avoid abandonment or surcharges."
        )
        
        # In production, we'd use a real mailer here.
        # For now, we log it forensically.
        logger.info(f"MOCK_EMAIL_SEND | To: Firm {deadline.firm_id} | Subject: {subject}")
        print(f"--- MOCK EMAIL SENT ---\nSubject: {subject}\nTo: {deadline.firm_id}\n{message}\n----------------------")

from dateutil.relativedelta import relativedelta
alert_service = AlertService()

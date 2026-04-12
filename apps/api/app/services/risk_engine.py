import uuid
from datetime import date, datetime, timedelta
from typing import List, Dict, Any
from app.models.patent import Patent, PatentClaim
from app.services.llm import generate_risk_analysis_stream, DEFAULT_LLM_MODEL
from app.utils.logging import get_base_logger

logger = get_base_logger(__name__)

class RiskEngine:
    """
    Automated risk and strength assessment for patent portfolios.
    Fulfills 'Per-patent scoring', 'Risk flag detection', and 'EP opposition window' requirements.
    """

    async def analyze_patent_dd(self, patent: Patent, db_session) -> Dict[str, Any]:
        """
        Conducts a technical and legal audit of a single patent.
        """
        flags = []
        score = 80 # Baseline score
        
        # 1. Life Context (Requirement: 'Each patent scored on remaining life')
        if patent.grant_date:
            expiry = patent.grant_date + timedelta(days=365*20)
            years_left = (expiry - date.today()).days / 365
            if years_left < 2:
                score -= 40
                flags.append({"text": f"Extreme Priority: Lifecycle expiring within {years_left:.1f} years", "severity": "CRITICAL"})
            elif years_left < 10:
                score -= 10
                flags.append({"text": f"Warning: Less than 10 years of enforceability remaining", "severity": "MEDIUM"})
        
        # 2. EP Opposition Window (Requirement: 'Opposition windows flagged for EP patents')
        # EP patents can be challenged for 9 months after grant
        if patent.patent_number and patent.patent_number.startswith("EP") and patent.grant_date:
            window_end = patent.grant_date + timedelta(days=30*9)
            if date.today() < window_end:
                score -= 15
                flags.append({"text": f"Active Opposition Window: EP patent challengeable until {window_end.isoformat()}", "severity": "HIGH"})

        # 3. Maintenance Fees (Requirement: 'Maintenance fees due within 12 months flagged')
        if patent.grant_date:
            # US maintenance fee milestones: 3.5, 7.5, 11.5 years
            milestones = [3.5, 7.5, 11.5]
            for m in milestones:
                due_date = patent.grant_date + timedelta(days=m*365.25)
                if date.today() <= due_date <= date.today() + timedelta(days=365):
                    flags.append({"text": f"Maintenance Fee Alert: {m}-year fee due on {due_date.isoformat()}", "severity": "HIGH"})

        # 4. Breadth & Claims (Requirement: 'Each patent scored on claim breadth')
        # Heuristic: Shorter claims are generally broader. More independent claims cover more scope.
        claims = [c for c in patent.claims if c.is_independent]
        if not claims:
            score -= 30
            flags.append({"text": "Critical Risk: No independent claims detected in data", "severity": "CRITICAL"})
        else:
            avg_length = sum(len(c.claim_text) for c in claims) / len(claims)
            if avg_length > 2000:
                score -= 10 # Very narrow claim
            if len(claims) < 2:
                score -= 5 # Single point of failure

        # 5. AI Justification (Requirement: 'Score is 0-100 with written justification')
        justification = await self._generate_ai_justification(patent, score, flags)
        
        return {
            "id": str(patent.id),
            "number": patent.patent_number or patent.application_number,
            "title": patent.title,
            "score": max(0, min(100, score)),
            "flags": flags,
            "risk_level": "CRITICAL" if any(f['severity'] == "CRITICAL" for f in flags) else "NORMAL",
            "justification": justification,
            "acquisition_recommendation": "SUPPORTED" if score > 60 else "RECOMMEND PRICE ADJUSTMENT"
        }

    async def _generate_ai_justification(self, patent: Patent, score: int, flags: List[Dict]) -> str:
        """
        Uses LLM to provide the 2-paragraph legal justification.
        """
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage, SystemMessage
        
        llm = ChatGoogleGenerativeAI(model=DEFAULT_LLM_MODEL)
        
        prompt = f"""
        Patent: {patent.title} ({patent.patent_number})
        Calculated Strength Score: {score}/100
        Flags: {", ".join([f['text'] for f in flags])}
        
        Provide a 2-paragraph technical strength justification. 
        Paragraph 1: Discuss the technical scope and benefit of the claims.
        Paragraph 2: Discuss the legal risks or lifecycle considerations based on the flags provided.
        Be professional, forensic, and legally neutral.
        """
        
        messages = [
            SystemMessage(content="You are a senior patent strategist conducting a due diligence score audit."),
            HumanMessage(content=prompt)
        ]
        
        try:
            resp = await llm.ainvoke(messages)
            return resp.content
        except Exception as e:
            logger.error(f"AI Justification failed: {e}")
            return "Justification unavailable due to technical error."

risk_engine = RiskEngine()

import io
import datetime
from typing import List, Dict, Any, Optional
from reportlab.lib.pagesizes import LETTER
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image, HRFlowable
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

class PremiumServiceReportGenerator:
    """
    Generates high-ticket, branded PDF reports for PhronesisIP services.
    Reflects a premium legal aesthetic suitable for US patent professionals.
    """

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        # Design system colors
        self.brand_color = colors.HexColor("#4F46E5") # Brand Indigo
        self.accent_color = colors.HexColor("#F59E0B") # Amber
        self.text_primary = colors.HexColor("#1E293B")
        self.text_secondary = colors.HexColor("#64748B")
        self.bg_light = colors.HexColor("#F8FAFC")

    def _setup_custom_styles(self):
        self.title_style = ParagraphStyle(
            'ReportTitle',
            parent=self.styles['Heading1'],
            fontSize=28,
            leading=34,
            spaceAfter=40,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#1E293B")
        )
        self.subtitle_style = ParagraphStyle(
            'ReportSubtitle',
            parent=self.styles['Heading2'],
            fontSize=16,
            leading=20,
            spaceAfter=20,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#4F46E5")
        )
        self.section_header = ParagraphStyle(
            'SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=16,
            spaceBefore=24,
            spaceAfter=12,
            textColor=colors.HexColor("#1A365D"),
            borderPadding=5,
            borderWidth=0,
            borderStyle=None
        )
        self.body_style = ParagraphStyle(
            'BodyText',
            parent=self.styles['Normal'],
            fontSize=11,
            leading=14,
            spaceAfter=10,
            textColor=colors.HexColor("#334155")
        )
        self.caption_style = ParagraphStyle(
            'Caption',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor("#94A3B8"),
            alignment=TA_LEFT
        )
        self.disclaimer_style = ParagraphStyle(
            'Disclaimer',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.grey,
            alignment=TA_CENTER,
            fontName='Helvetica-Oblique'
        )

    def generate_prior_art_report(self, client_name: str, invention_title: str, results: List[Dict[str, Any]]) -> bytes:
        """Generates a professional Prior Art Search Report."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=LETTER, 
            rightMargin=inch, 
            leftMargin=inch, 
            topMargin=inch, 
            bottomMargin=inch
        )
        
        elements = []

        # --- COVER PAGE ---
        elements.append(Spacer(1, 2*inch))
        elements.append(Paragraph("PRIOR ART SEARCH REPORT", self.title_style))
        elements.append(HRFlowable(width="50%", thickness=2, color=self.brand_color, spaceAfter=20))
        elements.append(Paragraph(f"<b>Invention:</b> {invention_title}", self.subtitle_style))
        elements.append(Spacer(1, 1*inch))
        
        # Cover details table
        data = [
            [Paragraph("<b>PREPARED FOR:</b>", self.body_style), Paragraph(client_name, self.body_style)],
            [Paragraph("<b>DATE:</b>", self.body_style), Paragraph(datetime.date.today().strftime('%B %d, %Y'), self.body_style)],
            [Paragraph("<b>REPORT ID:</b>", self.body_style), Paragraph(f"PA-{datetime.datetime.now().strftime('%Y%m%d')}-001", self.body_style)],
        ]
        t = Table(data, colWidths=[2*inch, 3*inch])
        t.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 12),
        ]))
        elements.append(t)
        
        elements.append(Spacer(1, 2*inch))
        elements.append(Paragraph("CONFIDENTIAL ATTORNEY WORK PRODUCT", self.disclaimer_style))
        elements.append(PageBreak())

        # --- EXECUTIVE SUMMARY ---
        elements.append(Paragraph("1. Executive Summary", self.section_header))
        summary = (
            "This report identifies the most relevant prior art documents located during a deep semantic "
            "search across global patent databases including the USPTO, EPO, and Google Patents. "
            "The search utilized PhronesisIP's proprietary legal LLM engine to rank documents by technical relevance."
        )
        elements.append(Paragraph(summary, self.body_style))
        
        # Methodology summary
        elements.append(Paragraph("<b>Search Methodology:</b>", self.body_style))
        elements.append(Paragraph(
            "• Deep Semantic Search (Voyage-Law-2 Vector Model)<br/>"
            "• Keyword Clustering across USPTO Cooperative Patent Classification (CPC)<br/>"
            "• Hierarchical Relevance Ranking via LLM-facilitated scoring",
            self.body_style
        ))
        
        elements.append(Spacer(1, 20))

        # --- FINDINGS OVERVIEW ---
        elements.append(Paragraph("2. Top Results & Threat Assessment", self.section_header))
        
        # Table of results
        table_data = [["Rank", "Document No.", "Title", "Threat Level"]]
        for i, res in enumerate(results[:10], 1):
            threat = res.get('threat_level', 'Medium')
            table_data.append([
                str(i),
                res.get('number', 'N/A'),
                Paragraph(res.get('title', 'Unknown Title'), self.body_style),
                Paragraph(f"<b>{threat}</b>", ParagraphStyle('Threat', fontSize=10, textColor=self._get_threat_color(threat)))
            ])
            
        rt = Table(table_data, colWidths=[0.5*inch, 1.2*inch, 3.5*inch, 1.3*inch])
        rt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), self.brand_color),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        elements.append(rt)
        
        elements.append(PageBreak())

        # --- DETAILED ANALYSIS ---
        elements.append(Paragraph("3. Detailed Prior Art Analysis", self.section_header))
        for res in results[:5]: # Top 5 detailed
            elements.append(Paragraph(f"<b>{res.get('number')} — {res.get('title')}</b>", self.body_style))
            elements.append(Paragraph(f"<i>Relevance Score: {res.get('score', 0)*100:.1f}%</i>", self.caption_style))
            elements.append(Spacer(1, 6))
            elements.append(Paragraph("<b>AI Narrative Analysis:</b>", self.body_style))
            elements.append(Paragraph(res.get('analysis', "Deep analysis pending."), self.body_style))
            elements.append(Spacer(1, 12))
            elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey, spaceAfter=12))

        # --- DISCLAIMER ---
        elements.append(Spacer(1, 0.5*inch))
        elements.append(Paragraph(
            "<b>Disclaimer:</b> This report is generated by an automated AI search engine and is intended for informational "
            "purposes only. It does not constitute legal advice or a formal patentability opinion from a licensed "
            "patent attorney. Users are advised to consult with a registered patent professional before filing.",
            self.disclaimer_style
        ))

        doc.build(elements)
        return buffer.getvalue()

    def _get_threat_color(self, threat: str):
        threat = threat.upper()
        if 'HIGH' in threat or 'CRITICAL' in threat:
            return colors.HexColor("#EF4444")
        if 'MEDIUM' in threat:
            return colors.HexColor("#F59E0B")
        return colors.HexColor("#22C55E")

# Global instance
service_report_generator = PremiumServiceReportGenerator()

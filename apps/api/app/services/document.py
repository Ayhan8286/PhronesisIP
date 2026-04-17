"""
Document processing: PDF text extraction and USPTO XML parsing.
"""

import io
from typing import Optional
from lxml import etree


def extract_pdf_text(pdf_content: bytes) -> str:
    """
    Extract text from a PDF file using pdfplumber.
    Falls back to PyMuPDF for scanned/image-based PDFs.
    """
    text = ""

    # Try PyMuPDF first (vastly more memory efficient for massive legal docs like MPEP)
    try:
        import fitz  # PyMuPDF
        with fitz.open(stream=pdf_content, filetype="pdf") as doc:
            for page in doc:
                page_text = page.get_text()
                if page_text:
                    text += page_text + "\n\n"
    except Exception:
        pass

    # If PyMuPDF got no text, fallback to pdfplumber (better layout analysis but memory hungry)
    if not text.strip():
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n\n"
        except Exception:
            pass

    # Detect if this is likely a scanned PDF (no text found after multiple methods)
    final_text = text.strip()
    
    # If the file is reasonably large but we got near-zero text, it's likely scanned
    if len(pdf_content) > 10000 and len(final_text) < 100:
         # Note: We don't raise an error here to stay low-level, 
         # but the calling code can now see the "empty" result more clearly.
         # For now, we return a special marker or just let the caller decide.
         pass
         
    return final_text


def extract_docx_text(docx_content: bytes) -> str:
    """
    Extract text from a Word document using python-docx.
    """
    try:
        import docx
        doc = docx.Document(io.BytesIO(docx_content))
        return "\n".join([para.text for para in doc.paragraphs])
    except Exception:
        return ""


def parse_uspto_patent_xml(xml_content: str) -> dict:
    """
    Parse a single USPTO patent application XML document.
    Supports the APPXML format from USPTO Open Data Portal.

    Returns a dict with structured patent data.
    """
    try:
        root = etree.fromstring(xml_content.encode("utf-8"))
    except etree.XMLSyntaxError:
        return {}

    def get_text(element, xpath: str, default: str = "") -> str:
        el = element.find(xpath)
        return el.text.strip() if el is not None and el.text else default

    def get_all_text(element, xpath: str) -> str:
        """Get concatenated text from all matching elements."""
        elements = element.findall(xpath)
        return " ".join(el.text.strip() for el in elements if el.text)

    patent = {
        "title": "",
        "abstract": "",
        "application_number": "",
        "patent_number": "",
        "filing_date": "",
        "inventors": [],
        "assignee": "",
        "claims": [],
        "description": "",
        "classification": {},
    }

    # Try different XML schemas (USPTO has evolved their format)
    # Patent Grant format
    bib_data = root.find(".//bibliographic-data-grant") or root.find(
        ".//bibliographic-data-application"
    )
    if bib_data is None:
        bib_data = root.find(".//us-bibliographic-data-grant") or root.find(
            ".//us-bibliographic-data-application"
        )

    if bib_data is not None:
        # Title
        patent["title"] = get_text(bib_data, ".//invention-title") or get_text(
            bib_data, ".//title-of-invention"
        )

        # Application number
        app_ref = bib_data.find(".//application-reference")
        if app_ref is not None:
            patent["application_number"] = get_text(app_ref, ".//doc-number")
            patent["filing_date"] = get_text(app_ref, ".//date")

        # Patent number
        pub_ref = bib_data.find(".//publication-reference")
        if pub_ref is not None:
            patent["patent_number"] = get_text(pub_ref, ".//doc-number")

        # Inventors
        inventors_el = bib_data.findall(".//inventor") or bib_data.findall(
            ".//us-applicant"
        )
        for inv in inventors_el:
            name = {
                "first_name": get_text(inv, ".//first-name"),
                "last_name": get_text(inv, ".//last-name"),
            }
            if name["first_name"] or name["last_name"]:
                patent["inventors"].append(name)

        # Assignee
        assignee_el = bib_data.find(".//assignee")
        if assignee_el is not None:
            patent["assignee"] = get_text(
                assignee_el, ".//orgname"
            ) or get_text(assignee_el, ".//organization-name")

        # Classification (CPC)
        cpc = bib_data.find(".//classifications-cpc")
        if cpc is not None:
            main_cpc = cpc.find(".//main-cpc/classification-cpc")
            if main_cpc is not None:
                patent["classification"] = {
                    "section": get_text(main_cpc, ".//section"),
                    "class": get_text(main_cpc, ".//class"),
                    "subclass": get_text(main_cpc, ".//subclass"),
                }

    # Abstract
    abstract_el = root.find(".//abstract")
    if abstract_el is not None:
        patent["abstract"] = " ".join(
            p.text.strip() for p in abstract_el.findall(".//p") if p.text
        )

    # Claims
    claims_el = root.find(".//claims")
    if claims_el is not None:
        for claim in claims_el.findall(".//claim"):
            claim_id = claim.get("id", "")
            claim_num = claim.get("num", "0")
            claim_text_parts = []

            for child in claim.iter():
                if child.text:
                    claim_text_parts.append(child.text.strip())
                if child.tail:
                    claim_text_parts.append(child.tail.strip())

            claim_text = " ".join(claim_text_parts)

            # Determine if independent (no dependent-claim reference)
            is_independent = claim.find(".//claim-ref") is None

            patent["claims"].append(
                {
                    "number": int(claim_num) if claim_num.isdigit() else 0,
                    "text": claim_text,
                    "is_independent": is_independent,
                }
            )

    # Description
    description_el = root.find(".//description")
    if description_el is not None:
        desc_parts = []
        for p in description_el.findall(".//p"):
            if p.text:
                desc_parts.append(p.text.strip())
        patent["description"] = "\n\n".join(desc_parts)

    return patent


def split_bulk_xml(bulk_xml: str) -> list[str]:
    """
    Split a USPTO bulk XML file into individual patent documents.
    USPTO concatenates multiple patents in a single file with a marker.
    """
    # Common delimiters in USPTO bulk files
    markers = [
        "<?xml version=",
        '<!DOCTYPE us-patent-grant',
        '<!DOCTYPE us-patent-application',
    ]

    documents = []
    current_doc = []

    for line in bulk_xml.split("\n"):
        if any(line.strip().startswith(marker) for marker in markers):
            if current_doc:
                documents.append("\n".join(current_doc))
                current_doc = []
        current_doc.append(line)

    if current_doc:
        documents.append("\n".join(current_doc))

    return documents

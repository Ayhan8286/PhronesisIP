from reportlab.pdfgen import canvas
import random

def generate_oa_pdf(filename):
    c = canvas.Canvas(filename)
    text = c.beginText(40, 800)
    text.setFont("Helvetica", 12)
    
    oa_body = [
        "UNITED STATES PATENT AND TRADEMARK OFFICE",
        "OFFICE ACTION",
        "",
        "Application Number: 18/123,456",
        "Art Unit: 2120",
        "",
        "NON-FINAL REJECTION",
        "",
        "1. Claims 1-3 are rejected under 35 U.S.C. 103 as being unpatentable over US-8,977,255 (Apple Inc.)",
        "in view of US-10,111,222 (Smith).",
        "Apple '255 discloses a voice assistant computing a pharmacological risk score before routing commands.",
        "Smith discloses validating medical commands via explicit confirmation.",
        "Therefore, it would have been obvious to a PHOSITA to combine Apple and Smith.",
        "",
        "2. Claims 4-5 are rejected under 35 U.S.C. 112(b) for being indefinite.",
        "",
        "Examiner: John Doe"
    ]
    
    for line in oa_body:
        text.textLine(line)
        
    c.drawText(text)
    c.save()

generate_oa_pdf(r"d:\box mation\apps\api\fake_office_action.pdf")
print("fake_office_action.pdf generated successfully.")

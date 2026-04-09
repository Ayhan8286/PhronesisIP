import zipfile
import io

patents = {
    "patent_A.pdf": "This is a dummy patent A text. It describes a cryptographic hashing protocol.",
    "patent_B.pdf": "This is a dummy patent B text. It describes an LLM routing module constraint.",
    "patent_C.pdf": "This is a dummy patent C text. It describes a machine learning memory allocator."
}

with zipfile.ZipFile("test_portfolio.zip", "w") as z:
    for name, content in patents.items():
        z.writestr(name, content)
print("Created test_portfolio.zip")

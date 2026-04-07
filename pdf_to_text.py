import fitz  # PyMuPDF
from pathlib import Path

pdf_path = Path("public/data/ncert_pdfs/desm_s_Biology.pdf")
output_txt = pdf_path.with_suffix(".txt")

with fitz.open(pdf_path) as doc:
    text = ""
    for page in doc:
        text += page.get_text()

# Optional: Clean up extra whitespace
text = '\n'.join([line.strip() for line in text.splitlines() if line.strip()])

with open(output_txt, "w", encoding="utf-8") as f:
    f.write(text)

print(f"Extracted text saved to {output_txt}")

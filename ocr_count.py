import fitz, os

data_dir = "./data"
scanned, digital = 0, 0
for root, _, files in os.walk(data_dir):
    for f in files:
        if f.endswith(".pdf"):
            doc = fitz.open(os.path.join(root, f))
            avg = sum(len(doc[i].get_text()) for i in range(min(3, len(doc)))) / 3
            if avg < 50: scanned += 1
            else: digital += 1
            doc.close()

print(f"Digital: {digital}, Scanned/OCR needed: {scanned}")
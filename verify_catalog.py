from curriculum_importer import _extract_ncert_textbook_catalog

with open("debug_ncert_page.html", encoding="utf-8", errors="replace") as f:
    html = f.read()

catalog = _extract_ncert_textbook_catalog(html)
print("Catalog entries found:", len(catalog))

for row in catalog[:5]:
    titles = [book["book_title"] for book in row["book_options"]]
    print(
        f"  Class {row['class_index']} ({row['class_label']}) / {row['subject']} -> "
        f"{len(row['book_options'])} book(s): {titles}"
    )

print("...")
for row in catalog[-3:]:
    print(
        f"  Class {row['class_index']} ({row['class_label']}) / {row['subject']} -> "
        f"{len(row['book_options'])} book(s)"
    )

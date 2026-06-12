import requests
import re

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://ncert.nic.in/",
}
with open("debug_ncert_page.html", encoding="utf-8", errors="replace") as _f:
    html = _f.read()

print("Length:", len(html))

selects = re.findall(r'<select[^>]+name=["\']([^"\']+)["\']', html, re.IGNORECASE)
print("Select names:", selects)

fns = re.findall(r"function\s+(\w+)\s*\(", html)
print("JS functions:", fns[:30])

for fn in ["change", "change1", "Change", "Change1", "load", "getSubject", "getBook"]:
    idx = html.find(f"function {fn}(")
    if idx < 0:
        idx = html.find(f"function {fn} (")
    print(f"\n--- '{fn}' at index {idx} ---")
    if idx >= 0:
        print(repr(html[idx:idx+400]))

# Show all option values to understand the dropdown data
options = re.findall(r'<option[^>]+value=["\']([^"\']*)["\'][^>]*>([^<]*)', html)
print("\n--- First 30 option (value, text) pairs ---")
for v, t in options[:30]:
    print(repr(v), "->", repr(t.strip()))

# Check if dropdown data might be loaded via AJAX
ajax_hints = re.findall(r"(ajax|fetch|XMLHttpRequest|\.php\?|getJSON|\.get\()", html, re.IGNORECASE)
print("\nAJAX hints:", ajax_hints[:20])

# Save full html for manual inspection
with open("debug_ncert_page.html", "w", encoding="utf-8") as f:
    f.write(html)
print("\nSaved full HTML to debug_ncert_page.html")

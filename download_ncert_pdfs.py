import requests
from pathlib import Path


# Scrape all PDF links from the NCERT syllabus page
from bs4 import BeautifulSoup

def get_pdf_links():
    syllabus_url = "https://ncert.nic.in/syllabus.php?ln=en"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://ncert.nic.in/",
        "Connection": "keep-alive",
    }
    print(f"Fetching syllabus page: {syllabus_url}")
    resp = requests.get(syllabus_url, headers=headers, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    pdf_links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().endswith(".pdf"):
            if href.startswith("http"):
                pdf_links.add(href)
            else:
                pdf_links.add("https://ncert.nic.in/" + href.lstrip("/"))
    print(f"Found {len(pdf_links)} PDF links.")
    return sorted(pdf_links)

output_dir = Path("public/data/ncert_pdfs")
output_dir.mkdir(parents=True, exist_ok=True)


def download_pdf(url):
    import time
    filename = url.split("/")[-1]
    out_path = output_dir / filename
    print(f"Downloading {url} ...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/pdf,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://ncert.nic.in/",
        "Connection": "keep-alive",
    }
    try:
        r = requests.get(url, stream=True, headers=headers, timeout=30)
        if r.status_code == 200 and r.headers.get('Content-Type', '').startswith('application/pdf'):
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)
            print(f"Saved to {out_path}")
        else:
            print(f"Failed to download {url}: {r.status_code} {r.headers.get('Content-Type')}")
    except Exception as e:
        print(f"Error downloading {url}: {e}")
    time.sleep(2)  # polite delay between requests

if __name__ == "__main__":
    try:
        pdf_urls = get_pdf_links()
        for url in pdf_urls:
            download_pdf(url)
    except Exception as e:
        print(f"Error scraping or downloading PDFs: {e}")

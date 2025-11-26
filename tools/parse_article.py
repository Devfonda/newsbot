# tools/parse_article.py
from pathlib import Path
from bs4 import BeautifulSoup

def extract_article(html):
    soup = BeautifulSoup(html, "html.parser")

    # Title heuristics
    title_tag = soup.find("meta", {"property": "og:title"}) or soup.find("meta", {"name": "title"})
    if title_tag and title_tag.get("content"):
        title = title_tag["content"].strip()
    else:
        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else (soup.title.string.strip() if soup.title else "")

    # Content heuristics
    article_selectors = [
        "article", ".article-content", ".post-content", ".entry-content", "#content", ".detail__body"
    ]
    body_text = ""
    for sel in article_selectors:
        el = soup.select_one(sel)
        if el:
            for bad in el(["script", "style", "aside", "noscript"]):
                bad.decompose()
            body_text = "\n\n".join(p.get_text(strip=True) for p in el.find_all("p") if p.get_text(strip=True))
            if len(body_text) > 50:
                break

    if not body_text:
        ps = soup.find_all("p")
        body_text = "\n\n".join(p.get_text(strip=True) for p in ps if p.get_text(strip=True))

    return {"title": title, "content": body_text}

def main():
    p = Path("output.html")
    if not p.exists():
        print("output.html not found")
        return
    html = p.read_text(encoding="utf-8")
    article = extract_article(html)
    print("=== TITLE ===\n")
    print(article["title"])
    print("\n=== CONTENT SNIPPET ===\n")
    print(article["content"][:4000])
    out = Path("output_article.txt")
    out.write_text(f"{article['title']}\n\n{article['content']}", encoding="utf-8")
    print(f"\nSaved to {out.resolve()}")

if __name__ == "__main__":
    main()

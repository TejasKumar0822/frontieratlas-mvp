import re
from bs4 import BeautifulSoup


def html_to_text(html: str, max_chars: int = 50000) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "form"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return text[:max_chars]


def semantic_chunks(text: str, max_chars: int = 12000) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks, current = [], []
    size = 0
    for sentence in sentences:
        if size + len(sentence) + 1 > max_chars and current:
            chunks.append(" ".join(current))
            current, size = [], 0
        current.append(sentence)
        size += len(sentence) + 1
    if current:
        chunks.append(" ".join(current))
    return chunks

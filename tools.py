"""Tools the debaters can reach for: the open web, a page, or the user's own source doc."""

import uuid
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
from langchain_core.tools import tool
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

import config

# the source document, if the user gave us one, lives here for the whole run
_source_store = None


@tool
def current_datetime() -> str:
    """Today's real date and the current time.

    Call this before judging any claim that depends on when it is being asked:
    anything saying current, now, today, latest, still, recent, or naming a year.
    Your training data ends long before today, so you cannot know the date without
    calling this.
    """
    now = datetime.now()
    return (f"Today is {now:%A, %d %B %Y}, {now:%H:%M} local time "
            f"(ISO {now:%Y-%m-%d}). Any knowledge you have from training is older "
            f"than this date.")


@tool
def web_search(query: str, max_results: int = config.RESULTS_PER_SEARCH) -> list:
    """Search the open web and return a list of {title, url, snippet}."""
    try:
        hits = DDGS().text(query, max_results=max_results)
    except Exception as e:
        return [{"title": "search failed", "url": "", "snippet": str(e)}]

    return [
        {
            "title": h.get("title", ""),
            "url": h.get("href", ""),
            "snippet": (h.get("body", "") or "")[:600],
        }
        for h in hits
    ]


@tool
def fetch_page(url: str) -> str:
    """Download a web page and return its readable text (truncated)."""
    try:
        html = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"}).text
    except Exception as e:
        return f"could not fetch page: {e}"

    soup = BeautifulSoup(html, "html.parser")
    for junk in soup(["script", "style", "nav", "footer", "header"]):
        junk.decompose()
    text = " ".join(soup.get_text(" ").split())
    return text[:8000]


def index_source(text):
    """Chunk + embed the user's document so the debaters can quote it directly."""
    global _source_store
    if not text or not text.strip():
        _source_store = None
        return 0

    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
    chunks = splitter.split_text(text)
    _source_store = Chroma.from_texts(
        texts=chunks,
        embedding=config.get_embeddings(),
        collection_name=f"source_{uuid.uuid4().hex[:8]}",
    )
    return len(chunks)


@tool
def search_source(query: str, k: int = 3) -> list:
    """Search the document the user supplied. Empty if they did not supply one."""
    if _source_store is None:
        return []
    docs = _source_store.similarity_search(query, k=k)
    return [
        {
            "title": "user source document",
            "url": "source-document",
            "snippet": d.page_content[:600],
        }
        for d in docs
    ]

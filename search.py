"""
search.py — Vidhyaarthi Hybrid Search Engine
=============================================
Search pipeline (in priority order):
  1. Brave Search API       — best quality, free 2k/mo (set BRAVE_API_KEY)
  2. googlesearch-python    — scrapes Google, handles both package variants
  3. DuckDuckGo HTML        — plain-HTML scraper, no API key
  4. Wikipedia Extracts API — FULL article text (not just summary), always works
  5. DuckDuckGo Instant API — extra context for the query topic

Wikipedia fix: uses /w/api.php?prop=extracts&explaintext=True for full articles
               instead of /api/rest_v1/page/summary (which only gave ~70 words).
"""

import asyncio
import httpx
import urllib.parse
import re
import random
import time
import os
from typing import List, Dict, Any, Optional

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    print("warning: beautifulsoup4 not installed, pip install beautifulsoup4")

MAX_CONTENT_CHARS = 8000

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]

def _ua() -> str:
    return random.choice(USER_AGENTS)

def clean_text(text: str) -> str:
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


# ---------------------------------------------------------------------------
# Method 1 — Brave Search API (free tier, no CC, 2000 req/month)
#   Sign up: https://api.search.brave.com/app/keys
#   Add to .env:  BRAVE_API_KEY=your_key
# ---------------------------------------------------------------------------
async def search_brave(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    api_key = os.environ.get("BRAVE_API_KEY", "")
    if not api_key:
        return []
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": max_results, "search_lang": "en"},
                headers={"Accept": "application/json", "X-Subscription-Token": api_key},
            )
            resp.raise_for_status()
            data = resp.json()
        results = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("description", ""),
            }
            for r in data.get("web", {}).get("results", [])[:max_results]
        ]
        print(f"OK Brave Search: {len(results)} results")
        return results
    except Exception as e:
        print(f"warn Brave Search error: {e}")
        return []


# ---------------------------------------------------------------------------
# Method 2 — googlesearch-python OR google package (handles BOTH variants)
#
#  googlesearch-python: search(term, num_results=N, advanced=True)
#  google package:      search(query, num=N) or search(query, stop=N)
#
#  The user's error "unexpected keyword argument 'num_results'" means they
#  have the 'google' package, not 'googlesearch-python'. We try all variants.
# ---------------------------------------------------------------------------
def _google_search_sync(query: str, max_results: int) -> List[Dict[str, str]]:
    results = []
    try:
        from googlesearch import search
        time.sleep(random.uniform(0.5, 1.2))

        # Variant A: googlesearch-python >= 1.2 (num_results=, advanced=)
        try:
            items = list(search(
                query, num_results=max_results, advanced=True,
                sleep_interval=1, lang="en"
            ))
            for item in items:
                if hasattr(item, "url"):
                    results.append({
                        "title": item.title or item.url,
                        "url": item.url,
                        "snippet": item.description or "",
                    })
                else:
                    results.append({"title": str(item), "url": str(item), "snippet": ""})
            if results:
                print(f"OK googlesearch-python (advanced): {len(results)} results")
                return results
        except TypeError:
            pass

        # Variant B: 'google' package (stop=N)
        try:
            for url in search(query, stop=max_results, pause=1.0):
                results.append({"title": str(url), "url": str(url), "snippet": ""})
            if results:
                print(f"OK google package (stop=): {len(results)} results")
                return results
        except TypeError:
            pass

        # Variant C: positional generator — works with any version
        import itertools
        for url in itertools.islice(search(query), max_results):
            results.append({"title": str(url), "url": str(url), "snippet": ""})
        if results:
            print(f"OK googlesearch (positional): {len(results)} results")

    except ImportError:
        print("warn: no googlesearch package — pip install googlesearch-python")
    except Exception as e:
        print(f"warn Google search: {e}")

    return results


async def search_google(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _google_search_sync, query, max_results)


# ---------------------------------------------------------------------------
# Method 3 — DuckDuckGo plain-HTML scraper
# ---------------------------------------------------------------------------
async def search_duckduckgo_html(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    results = []
    try:
        headers = {
            "User-Agent": _ua(),
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://duckduckgo.com/",
        }
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query, "kl": "us-en"},
                headers=headers,
            )
        html = resp.text

        if BS4_AVAILABLE:
            soup = BeautifulSoup(html, "html.parser")
            for div in soup.select("div.result")[:max_results]:
                a = div.select_one("a.result__a")
                snip = (
                    div.select_one("a.result__snippet") or
                    div.select_one("div.result__snippet")
                )
                if not a:
                    continue
                href = a.get("href", "")
                m = re.search(r"uddg=(https?[^&]+)", href)
                url = urllib.parse.unquote(m.group(1)) if m else href
                if not url.startswith("http"):
                    continue
                results.append({
                    "title": a.get_text(strip=True),
                    "url": url,
                    "snippet": snip.get_text(strip=True) if snip else "",
                })
        else:
            for enc_url, title in re.findall(
                r'uddg=(https?[^&"]+)[^>]*>([^<]+)</a>', html
            ):
                url = urllib.parse.unquote(enc_url)
                results.append({"title": title.strip(), "url": url, "snippet": ""})
                if len(results) >= max_results:
                    break

        print(f"OK DuckDuckGo HTML: {len(results)} results")
    except Exception as e:
        print(f"warn DuckDuckGo HTML: {e}")
    return results


# ---------------------------------------------------------------------------
# Method 4 — Wikipedia: OpenSearch + FULL article via Extracts API
#
#  OLD (wrong): /api/rest_v1/page/summary/{title}  ->  70 words (intro only)
#  NEW (fixed): /w/api.php?prop=extracts&explaintext=True  ->  full article
# ---------------------------------------------------------------------------
async def fetch_wikipedia_full_text(title: str) -> str:
    """
    Fetch the complete plain-text content of a Wikipedia article.
    Uses the MediaWiki Extracts API which returns the ENTIRE article,
    not just the lead paragraph like /page/summary does.
    """
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "titles": title,
                    "prop": "extracts",
                    "exintro": False,       # full article, not just intro
                    "explaintext": True,    # plain text, no HTML markup
                    "exsectionformat": "plain",
                    "format": "json",
                },
                headers={"User-Agent": "VidhyaarthiSearch/1.0 (educational tool)"},
            )
            data = resp.json()
        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            extract = page.get("extract", "")
            if extract:
                return clean_text(extract)[:MAX_CONTENT_CHARS]
    except Exception as e:
        print(f"  warn Wikipedia Extracts API '{title}': {e}")
    return ""


async def search_wikipedia(query: str, max_results: int = 4) -> List[Dict[str, Any]]:
    """
    1. Find relevant Wikipedia article titles via OpenSearch API.
    2. Fetch full article text for each via Extracts API (not summary).
    """
    results = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "opensearch",
                    "search": query,
                    "limit": max_results,
                    "namespace": 0,
                    "format": "json",
                },
                headers={"User-Agent": "VidhyaarthiSearch/1.0 (educational tool)"},
            )
            data = resp.json()

        titles      = data[1] if len(data) > 1 else []
        urls        = data[3] if len(data) > 3 else []

        if not titles:
            print("warn Wikipedia: no articles found")
            return []

        print(f"OK Wikipedia OpenSearch: {len(titles)} articles, fetching full text...")
        full_texts = await asyncio.gather(
            *[fetch_wikipedia_full_text(t) for t in titles]
        )

        for title, url, text in zip(titles, urls, full_texts):
            if text:
                wc = len(text.split())
                results.append({
                    "title":      f"Wikipedia: {title}",
                    "url":        url,
                    "content":    text,
                    "snippet":    text[:300],
                    "source":     "wikipedia_full",
                    "word_count": wc,
                })
                print(f"  OK Wikipedia '{title}' — {wc} words")
            else:
                print(f"  warn Wikipedia '{title}' — no text extracted")

    except Exception as e:
        print(f"warn Wikipedia search: {e}")
    return results


# ---------------------------------------------------------------------------
# Method 5 — DuckDuckGo Instant Answer API (free, no auth)
# ---------------------------------------------------------------------------
async def fetch_ddg_instant(query: str) -> Optional[Dict[str, Any]]:
    """
    DDG Instant Answer API returns an abstract for well-known topics.
    Good supplementary context, especially for definitions and concepts.
    """
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_redirect": 1, "no_html": 1},
                headers={"User-Agent": _ua()},
            )
            data = resp.json()
        abstract = data.get("AbstractText", "").strip()
        source   = data.get("AbstractSource", "")
        src_url  = data.get("AbstractURL", "")
        if abstract and len(abstract) > 80:
            return {
                "title":      f"DDG Instant: {data.get('Heading', query)}",
                "url":        src_url or f"https://duckduckgo.com/?q={urllib.parse.quote_plus(query)}",
                "content":    clean_text(abstract)[:MAX_CONTENT_CHARS],
                "snippet":    abstract[:250],
                "source":     f"ddg_instant ({source})",
                "word_count": len(abstract.split()),
            }
    except Exception as e:
        print(f"warn DDG Instant Answer: {e}")
    return None


# ---------------------------------------------------------------------------
# Generic page content fetcher (for Brave / Google / DDG web results)
# ---------------------------------------------------------------------------
async def fetch_page_content(url: str, snippet: str = "") -> Dict[str, Any]:
    """Fetch a URL and extract clean readable text."""
    empty = {"content": snippet, "title": "", "url": url,
             "word_count": len(snippet.split())}

    # Wikipedia URLs: use Extracts API (much better than scraping)
    wiki_m = re.match(r"https://en\.wikipedia\.org/wiki/(.+)", url)
    if wiki_m:
        article_title = urllib.parse.unquote(wiki_m.group(1).replace("_", " "))
        text = await fetch_wikipedia_full_text(article_title)
        if text:
            return {"content": text, "title": article_title,
                    "url": url, "word_count": len(text.split())}
        return empty

    try:
        async with httpx.AsyncClient(
            timeout=15.0, follow_redirects=True, verify=False
        ) as client:
            resp = await client.get(url, headers={
                "User-Agent": _ua(),
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            })
            resp.raise_for_status()
        html = resp.text

        if BS4_AVAILABLE:
            soup = BeautifulSoup(html, "html.parser")
            title_tag = soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else ""
            for tag in soup(["script", "style", "nav", "header", "footer",
                              "aside", "form", "noscript", "iframe"]):
                tag.decompose()
            block = (
                soup.find("article") or soup.find("main") or
                soup.find(id=re.compile(r"content|main|article", re.I)) or
                soup.find(class_=re.compile(r"content|article|post|entry|body", re.I)) or
                soup.body
            )
            if block:
                paras = block.find_all(["p", "h1", "h2", "h3", "h4", "li"])
                text = " ".join(p.get_text(separator=" ", strip=True) for p in paras)
            else:
                text = soup.get_text(separator=" ", strip=True)
        else:
            title_m = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
            title = title_m.group(1).strip() if title_m else ""
            text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.S | re.I)
            text = re.sub(r"<style[^>]*>.*?</style>",  "", text,  flags=re.S | re.I)
            text = re.sub(r"<[^>]+>", " ", text)

        text = clean_text(text)[:MAX_CONTENT_CHARS]
        return {"content": text, "title": title, "url": url,
                "word_count": len(text.split())}

    except Exception as e:
        print(f"  warn fetch {url[:60]}: {e}")
        return empty


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
async def hybrid_search(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Multi-source search with full content extraction.

    Sources (in priority order):
      Brave API -> Google -> DuckDuckGo HTML -> Wikipedia (always) -> DDG Instant
    Results sorted by word count so richest content appears first.
    """
    print(f"\nSearching for: '{query}'")
    print(f"Max results: {max_results}")

    web_hits: List[Dict[str, str]] = []

    # 1. Brave (best quality when key is set)
    web_hits = await search_brave(query, max_results)

    # 2. Google scraper
    if not web_hits:
        web_hits = await search_google(query, max_results)

    # 3. DuckDuckGo HTML
    if not web_hits:
        print("Trying DuckDuckGo HTML...")
        web_hits = await search_duckduckgo_html(query, max_results)

    # 4 & 5 run concurrently — Wikipedia + DDG Instant
    wiki_task    = asyncio.create_task(
        search_wikipedia(query, max_results=min(4, max_results))
    )
    instant_task = asyncio.create_task(fetch_ddg_instant(query))

    # Fetch web page content
    web_hits = web_hits[:max_results]
    if web_hits:
        print(f"Fetching content for {len(web_hits)} web URLs...")
        page_contents = await asyncio.gather(
            *[fetch_page_content(r["url"], r.get("snippet", "")) for r in web_hits]
        )
    else:
        page_contents = []

    wiki_results = await wiki_task
    instant      = await instant_task

    # Build final list
    final: List[Dict[str, Any]] = []
    seen_urls = {r["url"] for r in wiki_results}

    for sr, cd in zip(web_hits, page_contents):
        if sr["url"] in seen_urls:
            continue
        content = cd["content"] if cd["word_count"] > 30 else sr.get("snippet", "")
        wc      = cd["word_count"] if cd["word_count"] > 30 else len(content.split())
        final.append({
            "title":      cd["title"] or sr["title"],
            "url":        sr["url"],
            "content":    content,
            "snippet":    sr.get("snippet", content[:250]),
            "source":     "web_fetch" if cd["word_count"] > 30 else "snippet_only",
            "word_count": wc,
        })
        label = f"{wc} words" if wc > 30 else "snippet only"
        print(f"  OK {sr['title'][:55]!r} ({label})")
        seen_urls.add(sr["url"])

    # Append Wikipedia full-text results
    for wr in wiki_results:
        if wr["url"] not in seen_urls:
            final.append(wr)
            seen_urls.add(wr["url"])

    # Append DDG Instant if useful
    if instant and instant["url"] not in seen_urls:
        final.append(instant)
        print(f"  OK DDG Instant Answer ({instant['word_count']} words)")

    # Best content first
    final.sort(key=lambda r: r["word_count"], reverse=True)

    avg = sum(r["word_count"] for r in final) // max(len(final), 1)
    print(f"Done — {len(final)} results, avg {avg} words each\n")
    return final
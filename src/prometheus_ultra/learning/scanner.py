"""KnowledgeScanner — Knowledge scanning from multiple external sources.

Based on: MiMo Daily Learning System #2.3 (知识扫描)

Data sources from MiMo:
    - arXiv (AI/ML papers) — real API via export.arxiv.org
    - Hacker News (technical community) — real API via hacker-news.firebaseio.com
    - GitHub Trending (open source projects) — real API via api.github.com
    - Wikipedia (reference knowledge) — real API via en.wikipedia.org

Each source has a specific scan pattern and result format.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

import json
import re
import time
import urllib.request
import urllib.parse
import urllib.error
from dataclasses import dataclass, field
from enum import Enum


class ScanSource(Enum):
    WEB = "web"
    ARXIV = "arxiv"
    HACKERNEWS = "hackernews"
    GITHUB = "github"
    NEWSLETTER = "newsletter"
    BLOG = "blog"
    REPORT = "report"
    WIKI = "wiki"
    LOCAL = "local"
    ACADEMIC = "academic"


@dataclass
class ScanResult:
    title: str = ""
    content: str = ""
    source: str = ""
    tags: list = field(default_factory=list)
    score: float = 0.5
    url: str = ""
    timestamp: float = 0.0
    source_type: str = ""
    relevance: float = 0.0


# Source-specific configuration
SOURCE_CONFIG = {
    ScanSource.ARXIV: {
        "name": "arXiv",
        "url_pattern": "https://arxiv.org/abs/{id}",
        "topics": ["cs.AI", "cs.LG", "cs.CL", "cs.MA"],
        "freshness_days": 7,
    },
    ScanSource.HACKERNEWS: {
        "name": "Hacker News",
        "url_pattern": "https://news.ycombinator.com/item?id={id}",
        "topics": ["AI", "LLM", "agent", "memory"],
        "freshness_days": 1,
    },
    ScanSource.GITHUB: {
        "name": "GitHub Trending",
        "url_pattern": "https://github.com/{owner}/{repo}",
        "topics": ["agent", "llm", "memory", "rag"],
        "freshness_days": 7,
    },
    ScanSource.WIKI: {
        "name": "Wikipedia",
        "url_pattern": "https://en.wikipedia.org/wiki/{title}",
        "topics": [],
        "freshness_days": 365,
    },
}

_TIMEOUT = 15  # seconds


def _http_get(url: str, headers: dict | None = None) -> str | None:
    """Fetch URL with timeout and error handling."""
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "PrometheusUltra/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return None


def _parse_json(text: str) -> dict | list | None:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


class KnowledgeScanner:
    """Knowledge scanning from multiple external sources.

    Based on MiMo Daily Learning System.

    Usage:
        scanner = KnowledgeScanner()

        # Scan arXiv for recent papers
        results = scanner.scan(ScanSource.ARXIV, "agent memory consolidation")

        # Scan Hacker News for discussions
        results = scanner.scan(ScanSource.HACKERNEWS, "LLM agent")

        # Scan GitHub for trending projects
        results = scanner.scan(ScanSource.GITHUB, "agent framework")
    """

    def __init__(self):
        self._scans: list[dict] = []
        self._total_results = 0
        self._source_stats: dict[str, int] = {}
        self._academic_searcher = None

    def scan(self, source: ScanSource, query: str, max_results: int = 5,
             force: bool = False) -> list[ScanResult]:
        results = []

        if source == ScanSource.ARXIV:
            results = self._scan_arxiv(query, max_results)
        elif source == ScanSource.HACKERNEWS:
            results = self._scan_hackernews(query, max_results)
        elif source == ScanSource.GITHUB:
            results = self._scan_github(query, max_results)
        elif source == ScanSource.WIKI:
            results = self._scan_wiki(query, max_results)
        elif source == ScanSource.WEB:
            results = self._scan_web(query, max_results)
        elif source == ScanSource.NEWSLETTER:
            results = self._scan_hackernews(query, max_results)
        elif source == ScanSource.BLOG:
            results = self._scan_github(query, max_results)
        elif source == ScanSource.REPORT:
            results = self._scan_arxiv(query, max_results)
        elif source == ScanSource.LOCAL:
            results = self._scan_local(query, max_results)
        elif source == ScanSource.ACADEMIC:
            results = self._scan_academic(query, max_results)

        self._scans.append({
            "source": source.value, "query": query,
            "results": len(results), "timestamp": time.time(),
        })
        self._total_results += len(results)
        self._source_stats[source.value] = self._source_stats.get(source.value, 0) + len(results)

        return results

    def _scan_arxiv(self, query: str, max_results: int) -> list[ScanResult]:
        """Scan arXiv via the Atom API (export.arxiv.org)."""
        params = urllib.parse.urlencode({
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": min(max_results, 20),
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        })
        url = f"https://export.arxiv.org/api/query?{params}"
        xml_text = _http_get(url)
        if not xml_text:
            logger.debug("Scanner: arXiv unreachable, skipping (no offline fallback)")
            return []

        results = []
        entries = xml_text.split("<entry>")[1:]
        for entry in entries[:max_results]:
            title = _xml_tag(entry, "title").strip().replace("\n", " ")
            summary = _xml_tag(entry, "summary").strip().replace("\n", " ")
            arxiv_id = _xml_tag(entry, "id").strip()
            if not title or not arxiv_id:
                continue
            if arxiv_id.startswith("http"):
                arxiv_id = arxiv_id.split("/abs/")[-1]

            tags = []
            for cat in entry.split("<category"):
                if 'term="' in cat:
                    tag = cat.split('term="')[1].split('"')[0]
                    tags.append(tag)

            results.append(ScanResult(
                title=title[:200],
                content=summary[:500],
                source="arxiv",
                tags=tags[:5],
                score=min(1.0, 0.6 + len(summary) / 2000),
                url=f"https://arxiv.org/abs/{arxiv_id}",
                timestamp=time.time(),
                source_type="paper",
            ))
        return results

    def _scan_hackernews(self, query: str, max_results: int) -> list[ScanResult]:
        """Scan Hacker News via Firebase API."""
        query_lower = query.lower()
        results = []

        ids_text = _http_get("https://hacker-news.firebaseio.com/v0/topstories.json")
        if not ids_text:
            logger.debug("Scanner: HackerNews unreachable, skipping (no offline fallback)")
            return []
        story_ids = _parse_json(ids_text)
        if not story_ids or not isinstance(story_ids, list):
            return []

        checked = 0
        for sid in story_ids[:60]:
            if checked >= max_results * 3 or len(results) >= max_results:
                break
            checked += 1
            item_text = _http_get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json")
            if not item_text:
                continue
            item = _parse_json(item_text)
            if not item or item.get("type") != "story":
                continue
            title = (item.get("title") or "").lower()
            if any(kw in title for kw in query_lower.split()):
                results.append(ScanResult(
                    title=item.get("title", ""),
                    content=item.get("text", "")[:300] or item.get("title", ""),
                    source="hackernews",
                    tags=query_lower.split()[:3],
                    score=min(1.0, 0.5 + item.get("score", 0) / 200),
                    url=f"https://news.ycombinator.com/item?id={sid}",
                    timestamp=item.get("time", time.time()),
                    source_type="discussion",
                ))

        if not results:
            results = [ScanResult(
                title=f"HN: {query}",
                content=f"Hacker News: no trending stories matched '{query}' (fallback).",
                source="hackernews", tags=query_lower.split()[:3], score=0.4,
                url="https://news.ycombinator.com/", timestamp=time.time(), source_type="discussion",
            )]
        return results

    def _scan_github(self, query: str, max_results: int) -> list[ScanResult]:
        """Scan GitHub via Search API."""
        params = urllib.parse.urlencode({"q": query, "sort": "stars", "order": "desc", "per_page": min(max_results, 10)})
        url = f"https://api.github.com/search/repositories?{params}"
        text = _http_get(url, headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "PrometheusUltra/1.0"})
        if not text:
            logger.debug("Scanner: HackerNews unreachable, skipping (no offline fallback)")
            return []
        data = _parse_json(text)
        if not data or "items" not in data or not data["items"]:
            logger.debug("Scanner: GitHub no items, skipping (no offline fallback)")
            return []

        results = []
        for repo in data["items"][:max_results]:
            results.append(ScanResult(
                title=f"{repo['full_name']}: {repo.get('description', '')[:100]}",
                content=f"Language: {repo.get('language', 'N/A')}. "
                        f"Stars: {repo.get('stargazers_count', 0)}. "
                        f"Forks: {repo.get('forks_count', 0)}. "
                        f"{repo.get('description', '')}",
                source="github",
                tags=[repo.get("language", ""), "github", "open-source"],
                score=min(1.0, 0.4 + repo.get("stargazers_count", 0) / 5000),
                url=repo.get("html_url", ""),
                timestamp=time.time(),
                source_type="project",
            ))
        return results

    def _scan_wiki(self, query: str, max_results: int) -> list[ScanResult]:
        """Scan Wikipedia via MediaWiki API."""
        params = urllib.parse.urlencode({"action": "query", "list": "search", "srsearch": query,
                                         "srlimit": min(max_results, 5), "format": "json"})
        url = f"https://en.wikipedia.org/w/api.php?{params}"
        text = _http_get(url)
        if not text:
            logger.debug("Scanner: Wikipedia unreachable, skipping (no offline fallback)")
            return []
        data = _parse_json(text)
        if not data or "query" not in data or not data["query"].get("search"):
            logger.debug("Scanner: Wikipedia no results, skipping (no offline fallback)")
            return []

        results = []
        for item in data["query"].get("search", []):
            snippet = re.sub(r"<[^>]+>", "", item.get("snippet", ""))
            results.append(ScanResult(
                title=item.get("title", ""),
                content=snippet,
                source="wiki",
                tags=[query.split()[0] if query else "", "wikipedia", "reference"],
                score=0.7,
                url=f"https://en.wikipedia.org/wiki/{urllib.parse.quote(item.get('title', ''))}",
                timestamp=time.time(),
                source_type="reference",
            ))
        return results

    def _scan_web(self, query: str, max_results: int) -> list[ScanResult]:
        """Scan web via Wikipedia; no offline fallback (avoid polluting store)."""
        results = self._scan_wiki(query, max_results)
        if not results:
            logger.debug("Scanner: web (wiki) returned nothing, skipping (no offline fallback)")
            return []
        return results

    def _scan_local(self, query: str, max_results: int) -> list[ScanResult]:
        return [ScanResult(
            title=f"Local knowledge: {query}",
            content=f"Local documentation related to {query}.",
            source="local", tags=query.lower().split()[:3] + ["internal"], score=0.6,
            timestamp=time.time(), source_type="local",
        )]

    def get_stats(self) -> dict:
        return {"scans": len(self._scans), "total_results": self._total_results,
                "source_distribution": dict(self._source_stats)}

    def _scan_academic(self, query: str, max_results: int) -> list[ScanResult]:
        """扫描学术论文源（通过 paper-search-mcp）。"""
        try:
            if self._academic_searcher is None:
                from .academic_searcher import AcademicSearcher
                self._academic_searcher = AcademicSearcher()

            papers = self._academic_searcher.search(query, max_results=max_results)
        except Exception as e:
            logger.debug("Academic scan failed: %s", e)
            logger.debug("Scanner: Academic unreachable, skipping (no offline fallback)")
            return []

        results = []
        for p in papers:
            results.append(ScanResult(
                title=(p.get("title") or "")[:200],
                content=(p.get("content") or "")[:500],
                source="academic",
                tags=p.get("tags", [])[:5],
                score=p.get("score", 0.7),
                url=p.get("url", ""),
                timestamp=time.time(),
                source_type="paper",
            ))
        return results


def _xml_tag(text: str, tag: str) -> str:
    """Extract content from an XML tag."""
    start = text.find(f"<{tag}>")
    if start == -1:
        start = text.find(f'<{tag} ')
        if start == -1:
            return ""
        start = text.find(">", start) + 1
    else:
        start += len(f"<{tag}>")
    end = text.find(f"</{tag}>", start)
    if end == -1:
        return text[start:start + 500]
    return text[start:end]

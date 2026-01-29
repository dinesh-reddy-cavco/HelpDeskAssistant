"""
Parse Confluence HTML into clean structured text.
Removes navigation/noise; preserves headings and hierarchy for structure-aware chunking.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, NavigableString, Tag

logger = logging.getLogger(__name__)


# Confluence storage HTML elements we treat as structure
HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")
# Elements to skip (nav, scripts, etc.)
SKIP_TAGS = {"script", "style", "nav", "header", "footer", "noscript", "iframe"}
# Block elements that get a newline after
BLOCK_TAGS = {
    "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
    "br", "hr", "blockquote", "pre", "table", "ul", "ol", "section",
}


@dataclass
class StructuredSection:
    """A section of content with optional heading (for chunker)."""
    heading: str | None  # None for leading content before first heading
    level: int          # 1-6 for h1-h6, 0 for no heading
    text: str


def _normalize_whitespace(text: str) -> str:
    """Collapse whitespace and trim."""
    return re.sub(r"\s+", " ", text).strip()


def _text_of(el: Tag | NavigableString) -> str:
    """Recursive text extraction from an element."""
    if isinstance(el, NavigableString):
        return str(el).strip()
    if el.name in SKIP_TAGS:
        return ""
    if el.name == "br":
        return "\n"
    parts = []
    for child in el.children:
        parts.append(_text_of(child))
    if el.name in BLOCK_TAGS and parts:
        return " ".join(parts) + "\n"
    return " ".join(parts)


def _get_heading_level(tag: Tag) -> int:
    """Return 1-6 for h1-h6, else 0."""
    if tag.name and tag.name in HEADING_TAGS:
        return int(tag.name[1])
    return 0


def html_to_sections(html: str) -> list[StructuredSection]:
    """
    Convert Confluence storage HTML to a list of sections.
    Split by headings; content between two headings is one section. No duplicate text.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(SKIP_TAGS):
        tag.decompose()
    sections: list[StructuredSection] = []
    headings = soup.find_all(HEADING_TAGS)
    if not headings:
        body_text = _normalize_whitespace(soup.get_text(separator=" ", strip=True))
        if body_text:
            sections.append(StructuredSection(heading=None, level=0, text=body_text))
        return sections
    for i, h in enumerate(headings):
        level = _get_heading_level(h)
        title = _normalize_whitespace(h.get_text())
        next_h = headings[i + 1] if i + 1 < len(headings) else None
        content_parts = []
        for sib in h.next_siblings:
            if sib is next_h:
                break
            if isinstance(sib, Tag):
                if sib.name in HEADING_TAGS:
                    break
                content_parts.append(sib.get_text(separator=" ", strip=True))
            elif isinstance(sib, NavigableString) and str(sib).strip():
                content_parts.append(str(sib).strip())
        text = _normalize_whitespace(" ".join(content_parts))
        sections.append(StructuredSection(heading=title, level=level, text=text))
    return sections


def html_to_plain_text(html: str) -> str:
    """
    Convert HTML to a single clean plain-text string (no structure).
    Useful when structure-aware chunking falls back to recursive split.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(SKIP_TAGS):
        tag.decompose()
    return _normalize_whitespace(soup.get_text(separator=" ", strip=True))


def sections_to_plain_text(sections: list[StructuredSection]) -> str:
    """Flatten sections into one text with headings prefixed (for fallback chunking)."""
    parts = []
    for s in sections:
        if s.heading:
            parts.append(s.heading)
        if s.text:
            parts.append(s.text)
    return _normalize_whitespace("\n\n".join(parts))

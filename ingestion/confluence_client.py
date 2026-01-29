"""
Confluence REST API client for fetching all pages in a space.
No parsing; returns raw HTML body and metadata for downstream parser.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, List

import requests

from .config import ConfluenceConfig

logger = logging.getLogger(__name__)


@dataclass
class ConfluencePage:
    """Raw page data from Confluence (HTML + metadata)."""
    page_id: str
    title: str
    version: int
    html_content: str
    space_key: str
    url: str
    last_updated: str | None = None
    ancestors: List[str] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)

    def to_metadata_dict(self) -> dict[str, Any]:
        """Metadata only, for use in chunks."""
        return {
            "page_id": self.page_id,
            "page_title": self.title,
            "version": self.version,
            "space_key": self.space_key,
            "url": self.url,
            "last_updated": self.last_updated or "",
            "ancestors": self.ancestors,
            "labels": self.labels,
        }


class ConfluenceClient:
    """Fetches all pages from a Confluence space via REST API."""

    def __init__(self, config: ConfluenceConfig | None = None):
        self.config = config or ConfluenceConfig()
        self._session = requests.Session()
        self._session.auth = (self.config.email, self.config.api_token)
        self._session.headers["Accept"] = "application/json"
        self._base = self.config.base_url.rstrip("/")

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self._base}{path}"
        r = self._session.get(url, params=params or {}, timeout=60)
        r.raise_for_status()
        return r.json()

    def get_space_homepage_id(self, space_key: str | None = None) -> str:
        """Return the page id of the space's homepage."""
        key = space_key or self.config.space_key
        data = self._get(f"/rest/api/space/{key}")
        # _expandable.homepage is like "/rest/api/content/12345"
        homepage_ref = data.get("_expandable", {}).get("homepage")
        if not homepage_ref:
            raise ValueError(f"Space {key} has no homepage in response")
        return homepage_ref.split("/")[-1]

    def get_page_content_and_metadata(self, page_id: str) -> tuple[str, dict]:
        """Fetch one page: HTML body and metadata. Used internally."""
        path = f"/rest/api/content/{page_id}"
        params = {"expand": "body.storage,version,ancestors,metadata.labels"}
        data = self._get(path, params)
        html = (data.get("body") or {}).get("storage") or {}
        content = html.get("value") or ""
        version = (data.get("version") or {}).get("number", 0)
        last_updated = (data.get("version") or {}).get("when")
        ancestors = [a.get("title", "") for a in data.get("ancestors", [])]
        labels_res = (data.get("metadata") or {}).get("labels") or {}
        labels = [l.get("name", "") for l in labels_res.get("results", [])]
        return content, {
            "id": data.get("id", page_id),
            "title": data.get("title", ""),
            "version": version,
            "last_updated": last_updated,
            "ancestors": ancestors,
            "labels": labels,
        }

    def get_child_page_ids(self, parent_id: str) -> list[str]:
        """Return list of child page ids under parent."""
        path = f"/rest/api/content/{parent_id}/child/page"
        params = {"limit": self.config.page_limit}
        data = self._get(path, params)
        return [c["id"] for c in data.get("results", [])]

    def fetch_page(self, page_id: str, space_key: str | None = None) -> ConfluencePage:
        """Fetch a single page as ConfluencePage."""
        key = space_key or self.config.space_key
        content, meta = self.get_page_content_and_metadata(page_id)
        url = f"{self._base}/pages/viewpage.action?pageId={meta['id']}"
        return ConfluencePage(
            page_id=meta["id"],
            title=meta["title"],
            version=meta["version"],
            html_content=content,
            space_key=key,
            url=url,
            last_updated=meta.get("last_updated"),
            ancestors=meta.get("ancestors", []),
            labels=meta.get("labels", []),
        )

    def fetch_all_pages_in_space(self, space_key: str | None = None) -> list[ConfluencePage]:
        """
        Recursively fetch all pages in the space (from homepage down).
        Idempotent from API perspective; returns full list every time.
        """
        key = space_key or self.config.space_key
        root_id = self.get_space_homepage_id(key)
        pages: list[ConfluencePage] = []

        def recurse(pid: str) -> None:
            try:
                page = self.fetch_page(pid, key)
                pages.append(page)
                for child_id in self.get_child_page_ids(pid):
                    recurse(child_id)
            except requests.HTTPError as e:
                logger.warning("Skipping page %s: %s", pid, e)

        recurse(root_id)
        logger.info("Fetched %d pages from space %s", len(pages), key)
        return pages

#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import re
import sys
import unicodedata
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
MEMBERS_PATH = ROOT / "data" / "air_members.json"
OUTPUT_PATH = ROOT / "data" / "publications.json"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/csv;q=0.8,*/*;q=0.5",
    "Accept-Language": "en-US,en;q=0.9,it-IT;q=0.8,it;q=0.7",
}
TIMEOUT = 45

TITLE_KEYS = {
    "title",
    "titolo",
    "dc.title",
    "citation_title",
}
YEAR_KEYS = {
    "year",
    "publication_year",
    "publicationdate",
    "date",
    "issued",
    "issuedate",
    "dateofpublication",
    "datadipubblicazione",
}
AUTHORS_KEYS = {
    "authors",
    "author",
    "autori",
    "dc.contributor.author",
}
TYPE_KEYS = {
    "type",
    "tipo",
    "publicationtype",
    "dc.type",
}
URL_KEYS = {
    "url",
    "uri",
    "handle",
    "permalink",
    "link",
    "recordurl",
    "itemurl",
}
DOI_KEYS = {
    "doi",
    "dc.identifier.doi",
    "identifierdoi",
}

TYPE_MARKERS = [
    "Article (author)",
    "Article (editor)",
    "Book Part (author)",
    "Book Part (editor)",
    "Book (author)",
    "Book (editor)",
    "Conference Object",
    "Doctoral Thesis",
    "Working Paper",
    "Other contribution",
    "Patent",
    "Review",
    "Software",
    "Dataset",
]
JOURNAL_KEYS = {
    "journal", "journaltitle", "publicationname", "rivista",
    "sourcetitle", "dc.source", "containertitle"
}

PUBLISHER_KEYS = {
    "publisher", "editore", "dc.publisher"
}

ABSTRACT_KEYS = {
    "abstract", "abstracttext", "riassunto",
    "description", "dc.description.abstract"
}

@dataclass
class Member:
    name: str
    air_url: str | None
    enabled: bool


class SyncError(RuntimeError):
    pass


def normalize_key(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_title(value: str) -> str:
    value = normalize_space(value)
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return value.strip()


def parse_year(value: str) -> int | None:
    if not value:
        return None
    match = re.search(r"\b(19|20)\d{2}\b", value)
    if not match:
        return None
    return int(match.group(0))


def clean_url(value: str | None, base_url: str | None = None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    if base_url:
        value = urljoin(base_url, value)
    parsed = urlparse(value)
    if not parsed.scheme:
        return value
    cleaned = parsed._replace(fragment="")
    return urlunparse(cleaned)


def load_members() -> list[Member]:
    raw = json.loads(MEMBERS_PATH.read_text(encoding="utf-8"))
    return [
        Member(name=item["name"], air_url=item.get("air_url"), enabled=bool(item.get("enabled")))
        for item in raw
    ]


def session_get(url: str, *, expect_binary: bool = False) -> requests.Response:
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    if not expect_binary:
        resp.encoding = resp.encoding or resp.apparent_encoding or "utf-8"
    return resp


def researcher_variants(url: str) -> list[str]:
    variants: list[str] = []
    variants.append(url)
    parsed = urlparse(url)
    if "open=all" not in parsed.query and ";type=all" not in url:
        query = parsed.query
        query = f"{query}&open=all" if query else "open=all"
        variants.append(urlunparse(parsed._replace(query=query)))
    if ";type=all" not in url:
        variants.append(url.rstrip("/") + ";type=all")
    # Preserve order, remove duplicates.
    seen: set[str] = set()
    ordered: list[str] = []
    for item in variants:
        if item not in seen:
            ordered.append(item)
            seen.add(item)
    return ordered


def fetch_researcher_page(url: str) -> tuple[str, str]:
    errors: list[str] = []
    for variant in researcher_variants(url):
        try:
            resp = session_get(variant)
            return resp.text, resp.url
        except Exception as exc:  # pragma: no cover - network-dependent
            errors.append(f"{variant}: {exc}")
    raise SyncError(" | ".join(errors))


def discover_export_links(soup: BeautifulSoup, base_url: str) -> OrderedDict[str, str]:
    links: OrderedDict[str, str] = OrderedDict()
    for anchor in soup.find_all("a", href=True):
        label = normalize_space(anchor.get_text(" ", strip=True))
        if not label:
            continue
        href = clean_url(anchor["href"], base_url)
        lower_label = label.lower()
        if "csv" in lower_label:
            links.setdefault("csv", href)
        elif "bibtex" in lower_label:
            links.setdefault("bibtex", href)
        elif "excel" in lower_label:
            links.setdefault("excel", href)
        elif "ris" in lower_label:
            links.setdefault("ris", href)
    return links


def sniff_csv(text: str) -> csv.Dialect:
    sample = text[:4096]
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        return csv.excel


def first_value(row: dict[str, Any], keys: set[str]) -> str | None:
    for raw_key, raw_value in row.items():
        if normalize_key(raw_key) in keys:
            value = normalize_space(str(raw_value))
            if value:
                return value
    return None


def extract_doi(row: dict[str, Any]) -> str | None:
    direct = first_value(row, DOI_KEYS)
    if direct:
        return direct
    for value in row.values():
        text = normalize_space(str(value))
        match = re.search(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", text, re.I)
        if match:
            return match.group(0)
    return None


def csv_row_to_item(row: dict[str, Any], member_name: str, base_url: str) -> dict[str, Any] | None:
    title = first_value(row, TITLE_KEYS)
    year_text = first_value(row, YEAR_KEYS)
    authors = first_value(row, AUTHORS_KEYS)
    pub_type = first_value(row, TYPE_KEYS)
    air_url = clean_url(first_value(row, URL_KEYS), base_url)
    doi = extract_doi(row)

    journal = first_value(row, JOURNAL_KEYS)
    publisher = first_value(row, PUBLISHER_KEYS)
    abstract = first_value(row, ABSTRACT_KEYS)

    year = parse_year(year_text or "")

    if not title:
        return None

    return {
        "title": title,
        "year": year,
        "authors": authors or "",
        "type": pub_type or "",
        "doi": doi or "",
        "air_url": air_url or base_url,
        "journal_or_publisher": journal or publisher or "",
        "abstract": abstract or "",
        "members": [member_name],
    }

def fetch_csv_export(url: str, member_name: str, base_url: str) -> list[dict[str, Any]]:
    resp = session_get(url, expect_binary=True)
    raw = resp.content.decode("utf-8-sig", errors="replace")
    dialect = sniff_csv(raw)
    reader = csv.DictReader(io.StringIO(raw), dialect=dialect)
    items: list[dict[str, Any]] = []
    for row in reader:
        item = csv_row_to_item(row, member_name, base_url)
        if item:
            items.append(item)
    if items:
        return items
    raise SyncError(f"CSV export for {member_name} did not yield any items")


def infer_type(text: str) -> str:
    for marker in TYPE_MARKERS:
        if marker.lower() in text.lower():
            return marker
    return ""


def scrape_html_items(html: str, base_url: str, member_name: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, int | None]] = set()

    candidates = soup.select("tr, li, article, div")
    for node in candidates:
        text = normalize_space(node.get_text(" ", strip=True))
        if len(text) < 40:
            continue
        year = parse_year(text)
        title_link = None
        for anchor in node.find_all("a", href=True):
            label = normalize_space(anchor.get_text(" ", strip=True))
            if len(label) >= 8:
                title_link = anchor
                break
        if not title_link:
            continue
        title = normalize_space(title_link.get_text(" ", strip=True))
        if not title:
            continue
        key = (normalize_title(title), year)
        if key in seen:
            continue
        pub_type = infer_type(text)
        air_url = clean_url(title_link.get("href"), base_url) or base_url
        if "/cris/rp/" in air_url and air_url.rstrip("/") == base_url.rstrip("/"):
            # This is likely still the researcher page, not an item page.
            air_url = base_url
        cleaned = text.replace(title, " ")
        if year:
            cleaned = re.sub(rf"\b{year}\b", " ", cleaned)
        if pub_type:
            cleaned = cleaned.replace(pub_type, " ")
        authors = normalize_space(cleaned)
        items.append(
            {
                "title": title,
                "year": year,
                "authors": authors,
                "type": pub_type,
                "doi": "",
                "air_url": air_url,
                "members": [member_name],
            }
        )
        seen.add(key)

    if items:
        return items
    raise SyncError(f"HTML scrape for {member_name} did not find any items")


def member_items(member: Member) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    if not member.enabled or not member.air_url:
        return [], warnings

    html, resolved_url = fetch_researcher_page(member.air_url)
    soup = BeautifulSoup(html, "html.parser")
    export_links = discover_export_links(soup, resolved_url)

    for key in ("csv", "bibtex", "excel", "ris"):
        href = export_links.get(key)
        if not href:
            continue
        if key == "csv":
            try:
                return fetch_csv_export(href, member.name, resolved_url), warnings
            except Exception as exc:  # pragma: no cover - network-dependent
                warnings.append(f"{member.name}: CSV export failed ({exc})")
        else:
            warnings.append(f"{member.name}: found {key.upper()} export but parser prefers CSV")

    try:
        return scrape_html_items(html, resolved_url, member.name), warnings
    except Exception as exc:  # pragma: no cover - network-dependent
        warnings.append(f"{member.name}: HTML scrape failed ({exc})")
        return [], warnings


def dedupe_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for item in items:
        key = ""
        air_url = item.get("air_url") or ""
        doi = item.get("doi") or ""
        year = item.get("year")
        title = item.get("title") or ""
        if air_url and "/handle/" in air_url:
            key = f"url:{air_url}"
        elif doi:
            key = f"doi:{doi.lower()}"
        else:
            key = f"title:{normalize_title(title)}|year:{year or ''}"

        if key not in deduped:
            deduped[key] = item
            continue

        existing = deduped[key]
        merged_members = sorted({*existing.get("members", []), *item.get("members", [])})
        existing["members"] = merged_members
        if not existing.get("authors") and item.get("authors"):
            existing["authors"] = item["authors"]
        if not existing.get("type") and item.get("type"):
            existing["type"] = item["type"]
        if not existing.get("journal_or_publisher") and item.get("journal_or_publisher"):
            existing["journal_or_publisher"] = item["journal_or_publisher"]
        if not existing.get("abstract") and item.get("abstract"):
            existing["abstract"] = item["abstract"]
        if not existing.get("doi") and item.get("doi"):
            existing["doi"] = item["doi"]
        if (
            existing.get("air_url")
            and "/cris/rp/" in existing["air_url"]
            and item.get("air_url")
            and "/cris/rp/" not in item["air_url"]
        ):
            existing["air_url"] = item["air_url"]

    values = list(deduped.values())
    values.sort(key=lambda item: (item.get("year") or 0, item.get("title", "").lower()), reverse=True)
    return values


def main() -> int:
    members = load_members()
    all_items: list[dict[str, Any]] = []
    warnings: list[str] = []
    used_members = 0

    for member in members:
        if not member.enabled or not member.air_url:
            warnings.append(f"{member.name}: skipped (no AIR researcher URL configured)")
            continue
        used_members += 1
        try:
            items, member_warnings = member_items(member)
            all_items.extend(items)
            warnings.extend(member_warnings)
            print(f"{member.name}: {len(items)} items")
        except Exception as exc:  # pragma: no cover - network-dependent
            warnings.append(f"{member.name}: failed ({exc})")
            print(f"{member.name}: failed", file=sys.stderr)

    deduped = dedupe_items(all_items)
    payload = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "member_count": used_members,
        "item_count": len(deduped),
        "warnings": warnings,
        "items": deduped,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(deduped)} deduplicated items to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

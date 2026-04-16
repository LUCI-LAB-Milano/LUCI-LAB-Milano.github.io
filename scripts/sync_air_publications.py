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


class SyncError(RuntimeError):
    pass


@dataclass
class Member:
    name: str
    air_url: str | None
    enabled: bool


def normalize_space(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_key(value: Any) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def normalize_title(value: str) -> str:
    value = normalize_space(value)
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return value.strip()


def normalized_keys(*values: str) -> set[str]:
    return {normalize_key(value) for value in values if value is not None}


TITLE_KEYS = normalized_keys(
    "title",
    "titolo",
    "dc.title",
    "citation_title",
)
YEAR_KEYS = normalized_keys(
    "year",
    "publication_year",
    "publicationdate",
    "date",
    "issued",
    "issuedate",
    "dateofpublication",
    "datadipubblicazione",
)
AUTHORS_KEYS = normalized_keys(
    "authors",
    "author",
    "autori",
    "dc.contributor.author",
)
TYPE_KEYS = normalized_keys(
    "type",
    "tipo",
    "publicationtype",
    "dc.type",
)
URL_KEYS = normalized_keys(
    "url",
    "uri",
    "handle",
    "permalink",
    "link",
    "recordurl",
    "itemurl",
)
DOI_KEYS = normalized_keys(
    "doi",
    "dc.identifier.doi",
    "identifierdoi",
)
JOURNAL_KEYS = normalized_keys(
    "journal",
    "journaltitle",
    "publicationname",
    "rivista",
    "sourcetitle",
    "dc.source",
    "containertitle",
    "booktitle",
)
PUBLISHER_KEYS = normalized_keys(
    "publisher",
    "editore",
    "dc.publisher",
)
ABSTRACT_KEYS = normalized_keys(
    "abstract",
    "abstracttext",
    "riassunto",
    "description",
    "dc.description.abstract",
)

PAGE_ABSTRACT_KEYS = normalized_keys(
    "citation_abstract",
    "dc.description.abstract",
    "dc.description.abstracteng",
    "dc.description.abstractita",
    "description",
    "abstract",
)

PAGE_SOURCE_KEYS = normalized_keys(
    "citation_journal_title",
    "citation_conference_title",
    "citation_book_title",
    "dc.source",
    "dc.identifier.citation",
)

PAGE_PUBLISHER_KEYS = normalized_keys(
    "citation_publisher",
    "dc.publisher",
)

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
def add_query_parameter(url: str, key: str, value: str) -> str:
    parsed = urlparse(url)
    parts = [part for part in parsed.query.split("&") if part and not part.startswith(f"{key}=")]
    parts.append(f"{key}={value}")
    return urlunparse(parsed._replace(query="&".join(parts)))


def clean_authors(value: str | None) -> str:
    text = normalize_space(value)
    if not text:
        return ""
    text = text.replace(";", ",")
    text = re.sub(r"\s+\+\s*", " ", text)
    text = re.sub(r"(?:\s*-\s*)+$", "", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip(" ,;-")


def clean_abstract(value: str | None) -> str:
    text = normalize_space(value)
    if not text:
        return ""
    text = re.sub(r"^(abstract|riassunto)\s*[:\-]?\s*", "", text, flags=re.IGNORECASE)
    if looks_like_noise(text):
        return ""
    return text


def add_metadata_value(metadata: dict[str, list[str]], key: str | None, value: str | None) -> None:
    norm_key = normalize_key(key)
    norm_value = normalize_space(value)
    if not norm_key or not norm_value:
        return
    metadata.setdefault(norm_key, [])
    if norm_value not in metadata[norm_key]:
        metadata[norm_key].append(norm_value)


def first_metadata_value(metadata: dict[str, list[str]], keys: set[str]) -> str | None:
    for key in keys:
        for value in metadata.get(key, []):
            if value:
                return value
    return None

def load_members() -> list[Member]:
    raw = json.loads(MEMBERS_PATH.read_text(encoding="utf-8"))
    return [
        Member(
            name=item["name"],
            air_url=item.get("air_url"),
            enabled=bool(item.get("enabled")),
        )
        for item in raw
    ]


def session_get(url: str, *, expect_binary: bool = False) -> requests.Response:
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    if not expect_binary:
        resp.encoding = resp.encoding or resp.apparent_encoding or "utf-8"
    return resp


def researcher_variants(url: str) -> list[str]:
    variants: list[str] = [url]
    parsed = urlparse(url)

    if "open=all" not in parsed.query:
        query = f"{parsed.query}&open=all" if parsed.query else "open=all"
        variants.append(urlunparse(parsed._replace(query=query)))

    if ";type=all" not in url:
        variants.append(url.rstrip("/") + ";type=all")

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
        except Exception as exc:
            errors.append(f"{variant}: {exc}")
    raise SyncError(" | ".join(errors))


def discover_export_links(soup: BeautifulSoup, base_url: str) -> OrderedDict[str, str]:
    links: OrderedDict[str, str] = OrderedDict()

    for anchor in soup.find_all("a", href=True):
        href = clean_url(anchor["href"], base_url)
        if not href:
            continue

        label = normalize_space(anchor.get_text(" ", strip=True)).lower()
        href_lower = href.lower()

        if "csv" in label or "format=csv" in href_lower or href_lower.endswith(".csv"):
            links.setdefault("csv", href)
        elif "bibtex" in label or "format=bibtex" in href_lower or "bibtex" in href_lower:
            links.setdefault("bibtex", href)
        elif "ris" in label or "format=ris" in href_lower or href_lower.endswith(".ris"):
            links.setdefault("ris", href)
        elif "excel" in label or href_lower.endswith(".xls") or href_lower.endswith(".xlsx"):
            links.setdefault("excel", href)

    return links


def sniff_csv(text: str) -> csv.Dialect:
    sample = text[:4096]
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        return csv.excel


def first_value(row: dict[str, Any], keys: set[str]) -> str | None:
    for raw_key, raw_value in row.items():
        if normalize_key(raw_key) not in keys:
            continue
        if raw_value is None:
            continue
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


NOISE_FRAGMENTS = (
    "macrotipologie & tipologie",
    "pubblicazioni selezionate",
    "home sfoglia autore titolo riviste serie settore scientifico disciplinare tipologia",
    "esportazione ris endnote bibtex excel csv refworks",
    "mostra 20 30 50 100 records",
    "risultati 1 - 20 di",
    "simulazione asn",
    "autorizzazione necessaria",
    "il report seguente simula gli indicatori",
    "export in csv",
    "ultime pubblicazioni",
    "ricerca per:",
)

def looks_like_noise(text: str) -> bool:
    lower = normalize_space(text).lower()
    if not lower:
        return True
    if any(fragment in lower for fragment in NOISE_FRAGMENTS):
        return True
    if lower.startswith("tutti (") or lower.startswith("home "):
        return True
    if len(lower) > 400:
        return True
    return False
def build_item(
    *,
    title: str | None,
    year_text: str | None,
    authors: str | None,
    pub_type: str | None,
    air_url: str | None,
    doi: str | None,
    journal_or_publisher: str | None,
    abstract: str | None,
    member_name: str,
    base_url: str,
) -> dict[str, Any] | None:
    title = normalize_space(title)
    if not title or looks_like_noise(title):
        return None

    abstract = clean_abstract(abstract)
    authors = clean_authors(authors)
    pub_type = normalize_space(pub_type)
    journal_or_publisher = normalize_space(journal_or_publisher).strip(" ,;:-")

    if looks_like_noise(journal_or_publisher):
        journal_or_publisher = ""doi = normalize_space(doi)
    year = parse_year(year_text or "")
    final_url = clean_url(air_url, base_url) or base_url

    return {
        "title": title,
        "year": year,
        "authors": authors,
        "type": pub_type,
        "doi": doi,
        "air_url": final_url,
        "journal_or_publisher": journal_or_publisher,
        "abstract": abstract,
        "members": [member_name],
    }


def csv_row_to_item(row: dict[str, Any], member_name: str, base_url: str) -> dict[str, Any] | None:
    title = first_value(row, TITLE_KEYS)
    year_text = first_value(row, YEAR_KEYS)
    authors = first_value(row, AUTHORS_KEYS)
    pub_type = first_value(row, TYPE_KEYS)
    air_url = first_value(row, URL_KEYS)
    doi = extract_doi(row)

    journal = first_value(row, JOURNAL_KEYS)
    publisher = first_value(row, PUBLISHER_KEYS)
    abstract = first_value(row, ABSTRACT_KEYS)

    return build_item(
        title=title,
        year_text=year_text,
        authors=authors,
        pub_type=pub_type,
        air_url=air_url,
        doi=doi,
        journal_or_publisher=journal or publisher,
        abstract=abstract,
        member_name=member_name,
        base_url=base_url,
    )


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


def split_bibtex_entries(text: str) -> list[str]:
    entries: list[str] = []
    i = 0
    while i < len(text):
        start = text.find("@", i)
        if start == -1:
            break
        brace = text.find("{", start)
        if brace == -1:
            break

        depth = 0
        j = brace
        while j < len(text):
            ch = text[j]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    entries.append(text[start : j + 1])
                    i = j + 1
                    break
            j += 1
        else:
            break
    return entries


def bibtex_to_text(value: str) -> str:
    text = value.replace("\n", " ").replace("\r", " ")
    text = text.replace("~", " ")
    text = text.replace("\\&", "&")
    text = re.sub(r"[{}]", "", text)
    return normalize_space(text)


def parse_bibtex_fields(entry: str) -> tuple[str, dict[str, str]]:
    brace = entry.find("{")
    if brace == -1:
        return "", {}

    entry_type = entry[1:brace].strip().lower()
    body = entry[brace + 1 : -1].strip()
    if "," not in body:
        return entry_type, {}

    body = body.split(",", 1)[1]

    fields: dict[str, str] = {}
    i = 0
    while i < len(body):
        while i < len(body) and body[i] in " \t\r\n,":
            i += 1
        if i >= len(body):
            break

        key_start = i
        while i < len(body) and body[i] not in "=\r\n":
            i += 1
        key = body[key_start:i].strip().lower()

        while i < len(body) and body[i] != "=":
            i += 1
        if i >= len(body):
            break
        i += 1

        while i < len(body) and body[i].isspace():
            i += 1
        if i >= len(body):
            break

        if body[i] == "{":
            depth = 0
            value_start = i + 1
            while i < len(body):
                if body[i] == "{":
                    depth += 1
                elif body[i] == "}":
                    depth -= 1
                    if depth == 0:
                        value = body[value_start:i]
                        i += 1
                        break
                i += 1
            else:
                value = body[value_start:]
        elif body[i] == '"':
            i += 1
            value_start = i
            while i < len(body):
                if body[i] == '"' and body[i - 1] != "\\":
                    value = body[value_start:i]
                    i += 1
                    break
                i += 1
            else:
                value = body[value_start:]
        else:
            value_start = i
            while i < len(body) and body[i] not in ",\r\n":
                i += 1
            value = body[value_start:i]

        fields[key] = bibtex_to_text(value)

        while i < len(body) and body[i] != ",":
            i += 1
        if i < len(body) and body[i] == ",":
            i += 1

    return entry_type, fields


def fetch_bibtex_export(url: str, member_name: str, base_url: str) -> list[dict[str, Any]]:
    resp = session_get(url)
    text = resp.text

    items: list[dict[str, Any]] = []
    for entry in split_bibtex_entries(text):
        entry_type, fields = parse_bibtex_fields(entry)

        authors = normalize_space(fields.get("author", "").replace(" and ", ", "))
        journal_or_publisher = (
            fields.get("journal")
            or fields.get("booktitle")
            or fields.get("series")
            or fields.get("publisher")
        )

        item = build_item(
            title=fields.get("title"),
            year_text=fields.get("year") or fields.get("date"),
            authors=authors,
            pub_type=entry_type,
            air_url=fields.get("url"),
            doi=fields.get("doi"),
            journal_or_publisher=journal_or_publisher,
            abstract=fields.get("abstract"),
            member_name=member_name,
            base_url=base_url,
        )
        if item:
            items.append(item)

    if items:
        return items

    raise SyncError(f"BibTeX export for {member_name} did not yield any items")


def first_tag(record: dict[str, list[str]], *tags: str) -> str | None:
    for tag in tags:
        values = record.get(tag, [])
        for value in values:
            value = normalize_space(value)
            if value:
                return value
    return None


def fetch_ris_export(url: str, member_name: str, base_url: str) -> list[dict[str, Any]]:
    resp = session_get(url)
    text = resp.text.replace("\r\n", "\n").replace("\r", "\n")

    records: list[dict[str, list[str]]] = []
    current: dict[str, list[str]] = {}
    last_tag: str | None = None

    for raw_line in text.split("\n"):
        line = raw_line.rstrip()
        if not line.strip():
            continue

        if re.match(r"^[A-Z0-9]{2}  - ", line):
            tag = line[:2]
            value = line[6:].strip()

            if tag == "ER":
                if current:
                    records.append(current)
                    current = {}
                last_tag = None
                continue

            current.setdefault(tag, []).append(value)
            last_tag = tag
            continue

        if last_tag and current.get(last_tag):
            current[last_tag][-1] = normalize_space(current[last_tag][-1] + " " + line.strip())

    if current:
        records.append(current)

    items: list[dict[str, Any]] = []
    for record in records:
        authors_list = record.get("AU") or record.get("A1") or []
        authors = ", ".join(normalize_space(author) for author in authors_list if normalize_space(author))

        journal_or_publisher = (
            first_tag(record, "JO", "JF", "T2", "BT")
            or first_tag(record, "PB")
        )

        item = build_item(
            title=first_tag(record, "TI", "T1", "TT", "CT"),
            year_text=first_tag(record, "PY", "Y1", "DA"),
            authors=authors,
            pub_type=first_tag(record, "TY"),
            air_url=first_tag(record, "UR"),
            doi=first_tag(record, "DO"),
            journal_or_publisher=journal_or_publisher,
            abstract=first_tag(record, "AB", "N2"),
            member_name=member_name,
            base_url=base_url,
        )
        if item:
            items.append(item)

    if items:
        return items

    raise SyncError(f"RIS export for {member_name} did not yield any items")

def extract_metadata_from_full_page(soup: BeautifulSoup) -> dict[str, list[str]]:
    metadata: dict[str, list[str]] = {}

    for meta in soup.find_all("meta"):
        add_metadata_value(metadata, meta.get("name") or meta.get("property"), meta.get("content"))

    for row in soup.select("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        label = normalize_space(cells[0].get_text(" ", strip=True)).strip(" :-*")
        value = normalize_space(cells[-1].get_text(" ", strip=True))
        add_metadata_value(metadata, label, value)

    page_text = normalize_space(soup.get_text(" ", strip=True))
    patterns = {
        "dc.description.abstracteng": r"dc\.description\.abstracteng\s+(.*?)(?=\s+dc\.[a-z]|\s*$)",
        "dc.description.abstract": r"dc\.description\.abstract\s+(.*?)(?=\s+dc\.[a-z]|\s*$)",
        "dc.source": r"dc\.source\s+(.*?)(?=\s+dc\.[a-z]|\s*$)",
        "dc.publisher": r"dc\.publisher\s+(.*?)(?=\s+dc\.[a-z]|\s*$)",
        "dc.identifier.citation": r"dc\.identifier\.citation\s+(.*?)(?=\s+dc\.[a-z]|\s*$)",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, page_text, flags=re.IGNORECASE)
        if match:
            add_metadata_value(metadata, key, match.group(1))

    return metadata


def fetch_item_page_details(url: str | None, cache: dict[str, dict[str, str]]) -> dict[str, str]:
    handle_url = clean_url(url)
    if not handle_url or "/handle/" not in handle_url:
        return {}

    if handle_url in cache:
        return cache[handle_url]

    details = {
        "journal_or_publisher": "",
        "abstract": "",
    }

    for variant in (add_query_parameter(handle_url, "mode", "full"), handle_url):
        try:
            resp = session_get(variant)
        except Exception:
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        metadata = extract_metadata_from_full_page(soup)

        venue = normalize_space(
            first_metadata_value(metadata, PAGE_SOURCE_KEYS)
            or first_metadata_value(metadata, PAGE_PUBLISHER_KEYS)
        )
        abstract = clean_abstract(first_metadata_value(metadata, PAGE_ABSTRACT_KEYS))

        if venue and not looks_like_noise(venue):
            details["journal_or_publisher"] = venue
        if abstract:
            details["abstract"] = abstract

        if details["journal_or_publisher"] and details["abstract"]:
            break

    cache[handle_url] = details
    return details


def enrich_items_from_item_pages(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cache: dict[str, dict[str, str]] = {}

    for item in items:
        if item.get("abstract") and item.get("journal_or_publisher"):
            continue

        details = fetch_item_page_details(item.get("air_url"), cache)
        if not details:
            continue

        if not item.get("journal_or_publisher") and details.get("journal_or_publisher"):
            item["journal_or_publisher"] = details["journal_or_publisher"]

        if not item.get("abstract") and details.get("abstract"):
            item["abstract"] = details["abstract"]

    return items
def infer_type(text: str) -> str:
    for marker in TYPE_MARKERS:
        if marker.lower() in text.lower():
            return marker
    return ""


def scrape_html_items(html: str, base_url: str, member_name: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, int | None]] = set()

    for node in soup.select("tr, li, article, div"):
        text = normalize_space(node.get_text(" ", strip=True))
        if len(text) < 40 or looks_like_noise(text):
            continue

        year = parse_year(text)
        title_link = None
        for anchor in node.find_all("a", href=True):
            label = normalize_space(anchor.get_text(" ", strip=True))
            if len(label) >= 8 and not looks_like_noise(label):
                title_link = anchor
                break

        if not title_link:
            continue

        title = normalize_space(title_link.get_text(" ", strip=True))
        key = (normalize_title(title), year)
        if not title or key in seen:
            continue

        pub_type = infer_type(text)
        air_url = clean_url(title_link.get("href"), base_url) or base_url

        if air_url = clean_url(title_link.get("href"), base_url) or base_url

        if "/handle/" not in air_url:
            continue

        
        cleaned = text.replace(title, " ")
        if year:
            cleaned = re.sub(rf"\b{year}\b", " ", cleaned)
        if pub_type:
            cleaned = cleaned.replace(pub_type, " ")

        item = build_item(
            title=title,
            year_text=str(year) if year else "",
            authors=cleaned,
            pub_type=pub_type,
            air_url=air_url,
            doi="",
            journal_or_publisher="",
            abstract="",
            member_name=member_name,
            base_url=base_url,
        )
        if item:
            items.append(item)
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

    parsers = [
        ("csv", fetch_csv_export),
        ("bibtex", fetch_bibtex_export),
        ("ris", fetch_ris_export),
    ]

    for key, parser in parsers:
        href = export_links.get(key)
        if not href:
            continue
        try:
            items = parser(href, member.name, resolved_url)
            if items:
                return items, warnings
        except Exception as exc:
            warnings.append(f"{member.name}: {key.upper()} export failed ({exc})")

    try:
        return scrape_html_items(html, resolved_url, member.name), warnings
    except Exception as exc:
        warnings.append(f"{member.name}: HTML scrape failed ({exc})")
        return [], warnings


def dedupe_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for item in items:
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
        existing["members"] = sorted({*existing.get("members", []), *item.get("members", [])})

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
    values.sort(key=lambda item: (-(item.get("year") or 0), item.get("title", "").lower()))
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
        except Exception as exc:
            warnings.append(f"{member.name}: failed ({exc})")
            print(f"{member.name}: failed", file=sys.stderr)

        deduped = [
        item
        for item in dedupe_items(all_items)
        if not looks_like_noise(item.get("title", ""))
    ]
    deduped = enrich_items_from_item_pages(deduped)

    payload = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "member_count": used_members,
        "item_count": len(deduped),
        "warnings": warnings,
        "items": deduped,
    }

    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(deduped)} deduplicated items to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

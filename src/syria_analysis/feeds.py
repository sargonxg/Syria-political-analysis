"""Verified-endpoint RSS/Atom collection. It collects references, never findings."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime
from urllib.request import Request, HTTPRedirectHandler, build_opener
import re
import xml.etree.ElementTree as ET
from .core import canonical_url, document_id, now_utc

MAX_BYTES = 3_000_000
ATOM = '{http://www.w3.org/2005/Atom}'

def parse_date(value):
    if not value: return None
    from datetime import datetime, timezone
    try:
        date = parsedate_to_datetime(value)
    except (ValueError, TypeError):
        try: date = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except (ValueError, TypeError): return None
    if date.tzinfo is None: return None
    return date.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')

def parse_feed(raw: bytes, source: dict, feed_url: str, retrieved_at: str, limit: int = 6) -> list[dict]:
    if len(raw) > MAX_BYTES: raise ValueError('Feed exceeds maximum size')
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('DTD and entity declarations are not accepted')
    root = ET.fromstring(raw)
    atom = root.tag == ATOM + 'feed'
    if not atom and root.tag != 'rss': raise ValueError('Expected an RSS or Atom document')
    entries = root.findall(ATOM + 'entry') if atom else root.findall('./channel/item')
    rows = []
    for entry in entries[:limit]:
        title = entry.findtext(ATOM + 'title' if atom else 'title', '')
        title = ' '.join(re.sub(r'<[^>]+>', '', title).split()[:25])
        if not title: continue
        if atom:
            links = entry.findall(ATOM + 'link')
            link = next((e.get('href') for e in links if e.get('rel', 'alternate') == 'alternate'), None)
            date = entry.findtext(ATOM + 'published') or entry.findtext(ATOM + 'updated')
        else:
            link, date = entry.findtext('link'), entry.findtext('pubDate')
        try: url = canonical_url(link or '')
        except ValueError: continue
        rows.append({'id': document_id(url), 'source_id': source['id'], 'publisher': source['name'],
            'title': title, 'url': url, 'document_type': 'feed_reference',
            'published_at': parse_date(date), 'publication_date_precision': 'feed_timestamp_or_unknown',
            'retrieved_at': retrieved_at, 'retrieval_method': 'verified_feed', 'feed_url': feed_url,
            'reporting_period': None, 'review_state': 'unreviewed_reference', 'place_ids': [],
            'original_passage': None, 'full_text_collected': False})
    return rows

class PublicRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, newurl):
        # Keep redirects public and HTTPS; use ordinary TLS verification.
        if not canonical_url(newurl).startswith('https://'):
            raise ValueError('Feed redirects must retain HTTPS')
        return super().redirect_request(request, file, code, message, headers, newurl)

def fetch(source: dict, feed: dict, retrieved_at: str, limit: int) -> dict:
    try:
        url = canonical_url(feed['url'])
        if not url.startswith('https://'): raise ValueError('Feed must use HTTPS')
        request = Request(url, headers={'User-Agent': 'Syria-Political-Analysis/0.1 (public reference collection)',
            'Accept': 'application/rss+xml, application/atom+xml, application/xml;q=0.9'})
        with build_opener(PublicRedirects()).open(request, timeout=25) as response:
            items = parse_feed(response.read(MAX_BYTES + 1), source, url, retrieved_at, limit)
        return {'source_id': source['id'], 'url': url, 'status': 'parsed', 'retrieved_at': retrieved_at, 'items': items}
    except Exception as exc:
        # No response body, credential or proxy setting is copied into logs.
        return {'source_id': source['id'], 'url': feed['url'], 'status': 'unavailable',
            'retrieved_at': retrieved_at, 'items': [], 'error': type(exc).__name__}

def collect(sources: list[dict], limit: int = 6, source_ids: list[str] | None = None) -> dict:
    at = now_utc()
    jobs = [(source, feed) for source in sources if not source_ids or source['id'] in source_ids
        for feed in source.get('feeds', []) if feed.get('verified_on')]
    if not jobs: raise ValueError('No verified endpoints match the selected sources')
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda pair: fetch(pair[0], pair[1], at, limit), jobs))
    unique = {}
    for result in results:
        for item in result['items']: unique.setdefault(item['id'], item)
    return {'collected_at': at, 'automatic_refresh': False,
        'feeds': [{k: v for k, v in r.items() if k != 'items'} | {'item_count': len(r['items'])} for r in results],
        'items': sorted(unique.values(), key=lambda item: item['published_at'] or '', reverse=True)}

"""Import public X/Twitter post URLs as metadata. No scraping or API fiction."""
from urllib.parse import urlsplit
import re
from .core import canonical_url, now_utc

def import_reference(url: str, accounts: list[dict], note: str = '') -> dict:
    canonical = canonical_url(url)
    parts = urlsplit(canonical)
    if parts.hostname not in ('x.com', 'www.x.com', 'twitter.com', 'www.twitter.com'):
        raise ValueError('Expected a public X/Twitter post URL')
    match = re.fullmatch(r'/([A-Za-z0-9_]{1,15})/status/([0-9]+)(?:/)?', parts.path)
    if not match: raise ValueError('Expected /account/status/numeric-id')
    handle, post_id = match.groups()
    account = next((a for a in accounts if urlsplit(a['url']).path.strip('/').lower() == handle.lower()), None)
    return {'id': 'social-' + post_id, 'url': f'https://x.com/{handle}/status/{post_id}',
        'platform': 'X', 'account_handle_from_url': handle, 'account_id': account['id'] if account else None,
        'source_id': account['source_id'] if account else None,
        'recorded_at': now_utc(), 'published_at': None, 'review_state': 'unreviewed_reference',
        'place_ids': [], 'original_text': None, 'content_retrieved': False,
        'author_identity_note': 'Official profile link verified; post authorship/content not checked.' if account else 'Account identity not verified.',
        'analyst_note': note}

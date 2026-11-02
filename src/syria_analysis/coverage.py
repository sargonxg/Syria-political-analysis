"""Transparent title-level coverage tags. These are reading aids, never findings."""
from __future__ import annotations
import re
import unicodedata
from .core import now_utc

def normalise(text: str) -> str:
    text = ''.join(c for c in unicodedata.normalize('NFKC', text).casefold() if not unicodedata.combining(c))
    return text.translate(str.maketrans({'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ى': 'ي', 'ـ': None}))

def matched_terms(text: str, terms: list[str]) -> list[str]:
    normal = normalise(text)
    return [term for term in terms if re.search(r'(?<!\w)' + re.escape(normalise(term)) + r'(?!\w)', normal)]

def build_coverage(workspace: dict, lexicon: dict) -> dict:
    refs, edges, nodes = [], [], []
    used_topics, used_places = set(), set()
    sources = {s['id']: s for s in workspace['sources']}
    counts = {sid: 0 for sid in sources}
    for document in workspace['documents']:
        if document.get('document_type') not in ('feed_reference', 'news_reference'):
            continue
        topics = [{'id': t['id'], 'terms': hits} for t in lexicon['topics'] if (hits := matched_terms(document['title'], t['terms']))]
        places = [{'id': p['id'], 'terms': hits} for p in lexicon['places'] if (hits := matched_terms(document['title'], p['terms']))]
        row = {k: document.get(k) for k in ('id', 'source_id', 'title', 'url', 'published_at', 'published_on', 'retrieved_at', 'review_state')}
        row.update(topic_matches=topics, place_mentions=places, tagging_basis='Literal words in the saved title only', coordinates=None)
        refs.append(row); counts[document['source_id']] += 1
        nodes.append({'id': row['id'], 'type': 'reference', 'label': row['title'], 'source_id': row['source_id']})
        edges.append({'source': row['source_id'], 'target': row['id'], 'relation': 'published_reference'})
        for topic in topics:
            used_topics.add(topic['id'])
            edges.append({'source': row['id'], 'target': 'topic-' + topic['id'], 'relation': 'title_keyword_match', 'matched_terms': topic['terms']})
        for place in places:
            used_places.add(place['id'])
            edges.append({'source': row['id'], 'target': 'mention-' + place['id'], 'relation': 'title_place_mention', 'matched_terms': place['terms']})
    summary = [{'id': s['id'], 'name': s['name'], 'type': s['type'], 'reference_count': counts[s['id']],
        'status': 'Collected references' if counts[s['id']] else 'Directory only; no references in this sample'} for s in workspace['sources']]
    nodes += [{'id': s['id'], 'type': 'source', 'label': s['name'], 'category': s['type']} for s in summary if s['reference_count']]
    nodes += [{'id': 'topic-' + t['id'], 'type': 'topic', 'label': t['name']} for t in lexicon['topics'] if t['id'] in used_topics]
    nodes += [{'id': 'mention-' + p['id'], 'type': 'place_mention', 'label': p['name']} for p in lexicon['places'] if p['id'] in used_places]
    return {'schema_version': 1, 'built_at': now_utc(), 'title': 'Syria source-coverage sample',
        'method': 'Deterministic English/Arabic title-keyword matching with recorded matched terms. No article bodies, inferred incidents or causal influence scores.',
        'lexicon_version': lexicon['version'], 'topics': lexicon['topics'], 'places': lexicon['places'],
        'sources': summary, 'references': refs, 'graph': {'nodes': nodes, 'edges': edges},
        'limits': ['This bounded feed/reference sample is not a representative sample of Syrian media or opinion.',
            'Different sources and collection windows have unequal coverage; counts cannot measure importance or bias.',
            'A title may mention a place without describing an event there. No event coordinates are inferred.',
            'Keyword matches can miss context, negation, synonyms and morphology; a human must read the original.',
            'Edges record publication or explicit title terms, not influence, causality, affiliation or corroboration.']}

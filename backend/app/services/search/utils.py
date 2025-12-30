import re

_QUERY_SENT_SPLIT = re.compile(r'(?<=[.!?])\s+')
_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")

def split_query_sentences(query: str):
    return [
        s.strip()
        for s in _QUERY_SENT_SPLIT.split(query)
        if len(s.strip()) > 10
    ]

def extract_terms(sentences, max_terms=12):
    terms = set()
    for sent in sentences:
        for w in _TOKEN_RE.findall(sent.lower()):
            if len(w) > 2:
                terms.add(w)
    return list(terms)[:max_terms]

import math
import re
from collections import Counter

STOPWORDS = {
    "the", "is", "are", "was", "were", "and", "or", "of", "to", "in",
    "for", "with", "using", "through", "based", "by", "a", "an"
}

def tokenize(text: str) -> list[str]:
    return [
        w for w in re.findall(r"[a-zA-Z]+", text.lower())
        if w not in STOPWORDS and len(w) > 2
    ]

def lexical_overlap_score(query: str, chunk_text: str) -> float:
    if not chunk_text:
        return 0.0

    q_tokens = tokenize(query)
    c_tokens = tokenize(chunk_text)

    if not q_tokens or not c_tokens:
        return 0.0

    freq = Counter(c_tokens)
    length = len(c_tokens)

    score = 0.0
    max_score = 0.0

    for token in q_tokens:
        tf = freq.get(token, 0) / length
        idf = math.log(1 + (1 / (1 + freq.get(token, 0))))
        score += tf * idf
        max_score += idf

    return score / max_score if max_score else 0.0

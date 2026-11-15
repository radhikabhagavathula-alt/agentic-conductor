"""Deterministic offline embedder for tests (cosine similarity ~ word overlap)."""
import hashlib
import math
import re


def fake_embedder(texts):
    """Hash each word into a 128-dim bucket, L2-normalise -> cosine similarity ~ word overlap."""
    out = []
    for t in texts:
        v = [0.0] * 128
        for w in re.findall(r"[a-z0-9]+", t.lower()):
            v[int(hashlib.md5(w.encode()).hexdigest(), 16) % 128] += 1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        out.append([x / norm for x in v])
    return out

"""
PLACEHOLDER embedding generators (512-d).

These are deterministic stubs. Replace with real CLIP (ViT-B/32) encoders
post-export. Both functions MUST return a list of 512 floats (L2-normalized)
so that pgvector cosine distance (<=>) queries remain valid.
"""
import hashlib
import numpy as np

EMBEDDING_DIM = 512


def _seeded_vector(seed_bytes: bytes) -> list:
    seed = int.from_bytes(hashlib.sha256(seed_bytes).digest()[:8], "big") % (2**32)
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(EMBEDDING_DIM)
    v = v / (np.linalg.norm(v) + 1e-9)
    return [round(float(x), 6) for x in v]


def generate_text_embedding(text: str) -> list:
    """STUB: replace with CLIP text encoder. Returns 512-d normalized vector."""
    return _seeded_vector((text or "").strip().lower().encode("utf-8"))


def generate_image_embedding(image_bytes: bytes) -> list:
    """STUB: replace with CLIP image encoder. Returns 512-d normalized vector."""
    return _seeded_vector(image_bytes or b"empty")


def vector_literal(vec: list) -> str:
    """Serialize python list to pgvector literal '[...]' for SQL params."""
    return "[" + ",".join(str(x) for x in vec) + "]"

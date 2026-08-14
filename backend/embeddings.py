"""Real multimodal embeddings - dual CLIP setup, 512-d shared space, CPU.

  text  -> sentence-transformers/clip-ViT-B-32-multilingual-v1   (50+ languages)
  image -> sentence-transformers/clip-ViT-B-32                   (via PIL)

The multilingual text encoder was distilled to sit in the *same* 512-d space as
the CLIP image tower, so a Russian query embedding can be cosine-compared
directly against an image embedding. Models are loaded lazily on first use so
the worker boots instantly.
"""
import io
import os
import re
import threading

import numpy as np

TEXT_MODEL_NAME = "sentence-transformers/clip-ViT-B-32-multilingual-v1"
IMAGE_MODEL_NAME = "sentence-transformers/clip-ViT-B-32"
EMBED_DIM = 512

_lock = threading.Lock()
_text_model = None
_image_model = None


def _load(which):
    global _text_model, _image_model
    from sentence_transformers import SentenceTransformer
    with _lock:
        if which == "text" and _text_model is None:
            _text_model = SentenceTransformer(TEXT_MODEL_NAME, device="cpu")
        if which == "image" and _image_model is None:
            _image_model = SentenceTransformer(IMAGE_MODEL_NAME, device="cpu")
    return _text_model if which == "text" else _image_model


def warm(log=lambda m: None):
    log(f"loading text encoder {TEXT_MODEL_NAME} (CPU)")
    _load("text")
    log(f"loading image encoder {IMAGE_MODEL_NAME} (CPU)")
    _load("image")
    log(f"both encoders ready, shared {EMBED_DIM}-d space")


def _norm(v):
    v = np.asarray(v, dtype=np.float32)
    if v.ndim == 1:
        v = v[None, :]
    n = np.linalg.norm(v, axis=1, keepdims=True)
    n[n == 0] = 1.0
    return v / n


def encode_text(texts, batch_size=32):
    """List[str] -> (n, 512) L2-normalised float32."""
    model = _load("text")
    vecs = model.encode(list(texts), batch_size=batch_size, convert_to_numpy=True,
                        show_progress_bar=False)
    return _norm(vecs)


def encode_images(images, batch_size=8):
    """List[PIL.Image] -> (n, 512) L2-normalised float32."""
    model = _load("image")
    vecs = model.encode(list(images), batch_size=batch_size, convert_to_numpy=True,
                        show_progress_bar=False)
    return _norm(vecs)


def encode_image_bytes(raw):
    from PIL import Image
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    return encode_images([img])[0]


_DROP_TOKENS = {"PL", "EN", "EUR", "IT", "CL", "TD", "FN", "EXPORT", "UPDATE", "PDF"}


def collection_label(name):
    """'2026_PL_Living-Systems-Dining_EN_EUR.pdf' -> 'Living, Systems, Dining'.

    This matters a lot: the raw price-list tables never contain the words a buyer
    actually searches for ('sofa', 'kitchen', 'dining'), so the document family is
    the only place that vocabulary exists. Injecting it makes the vector space
    searchable in natural language.
    """
    base = os.path.splitext(str(name or ""))[0]
    parts = re.split(r"[_\-\s]+", base)
    keep = [p for p in parts if p and p.upper() not in _DROP_TOKENS and not p.isdigit()]
    return ", ".join(keep)


def _clean_bit(t, maxlen=70):
    """Keep only short, human-meaningful fragments (drops numbers, glyph
    artefacts like '>' and the prose that leaks in from terms-and-conditions
    pages)."""
    t = re.sub(r"\s+", " ", str(t or "")).strip(" .,;:·>*-\u2013\u2014")
    if len(t) < 2 or len(t) > maxlen:
        return None
    if not re.search(r"[A-Za-z\u0400-\u04FF]", t):
        return None
    return t


def product_text(p):
    """Canonical multilingual sentence describing one product row.

    Deliberately excludes the price and the variant code: they are template noise
    identical across thousands of rows, which inflates the shared component of the
    embedding space and destroys cosine discrimination.
    """
    model = _clean_bit(p.get("model_name"))
    category = _clean_bit(p.get("category"))
    if model and category and category.lower() == model.lower():
        category = None
    finishes = []
    for v in (p.get("variations") or [])[:6]:
        f = _clean_bit(v.get("finish"), 50)
        if f and f.lower() not in [x.lower() for x in finishes]:
            finishes.append(f)
    label = collection_label(p.get("doc_name") or p.get("collection"))
    section = _clean_bit(p.get("section"), 40)
    bits = [model, category]
    if finishes:
        bits.append(", ".join(finishes[:5]))
    tail = ", ".join([x for x in [label, section] if x])
    if tail:
        bits.append(tail)
    return ". ".join([b for b in bits if b])


def cosine_matrix(query_vec, matrix):
    q = _norm(query_vec)[0]
    M = np.asarray(matrix, dtype=np.float32)
    if M.size == 0:
        return np.zeros((0,), dtype=np.float32)
    return M @ q

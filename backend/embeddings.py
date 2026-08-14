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


def product_text(p):
    """Canonical multilingual sentence describing one product row."""
    bits = [p.get("model_name"), p.get("category"), p.get("dimension"),
            p.get("variant_code"), p.get("collection"), p.get("section")]
    finishes = [v.get("finish") for v in (p.get("variations") or [])[:4] if v.get("finish")]
    bits.extend(finishes)
    text = ", ".join(str(b) for b in bits if b)
    price = p.get("price_min")
    if price is not None:
        text += f", price from {price} to {p.get('price_max')} EUR"
    return text


def cosine_matrix(query_vec, matrix):
    q = _norm(query_vec)[0]
    M = np.asarray(matrix, dtype=np.float32)
    if M.size == 0:
        return np.zeros((0,), dtype=np.float32)
    return M @ q

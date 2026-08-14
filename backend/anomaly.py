"""Spatial-anomaly classifier for PDF price-matrix cells, powered by micrograd.

Why this exists
---------------
The raw price regex fires on anything that merely *looks* like a number: real
matrix cells, but also table-of-contents page numbers, footnote markers,
technical-drawing dimensions and column codes. Hard thresholds are brittle
across 40+ brands, so we learn the boundary from the page geometry itself.

How it works
------------
1. FEATURES (8, all scale-free so they transfer between brands and page sizes):
     f0 row_peers    - price candidates sharing this baseline (matrix rows are
                       wide; a table-of-contents page number sits alone)
     f1 col_peers    - candidates sharing this column
     f2 has_left     - a non-numeric row label exists to the left
     f3 left_gap     - normalised horizontal distance to that label
     f4 has_above    - a column header exists directly above
     f5 above_is_num - that header is itself a bare number (TOC smell)
     f6 align_err    - |x0(price) - x0(header)| / 10px tolerance
     f7 size_ratio   - font size relative to the page median
2. WEAK LABELS taken only from two unambiguous extremes - never from the grey
   zone the network is actually asked to judge.
3. TRAINING with micrograd: MLP(8, [8, 8, 1]), max-margin (SVM) loss + L2,
   real reverse-mode autograd over plain Python scalars, CPU.
4. INFERENCE: the micrograd-learned scalars are read out of the Value graph and
   applied with numpy, so scoring 50k candidates stays instant.
"""
import json
import os
import random
import re

import numpy as np

from nn import MLP

NUM_RE = re.compile(r"^[\d.,\s]+$")
FEATURE_NAMES = ["row_peers", "col_peers", "has_left", "left_gap",
                 "has_above", "above_is_num", "align_err", "size_ratio"]


def featurize(cand, page_w, page_h, median_size):
    row_peers = min(cand.get("row_peers", 0), 10) / 10.0
    col_peers = min(cand.get("col_peers", 0), 10) / 10.0
    left = cand.get("left")
    above = cand.get("above")
    has_left = 1.0 if left else 0.0
    left_gap = min(max(cand["x0"] - left["x1"], 0.0) / max(page_w, 1.0), 1.0) if left else 1.0
    has_above = 1.0 if above else 0.0
    above_is_num = 1.0 if (above and NUM_RE.match(above["text"].strip())) else 0.0
    align_err = min(abs(cand["x0"] - above["x0"]) / 10.0, 1.0) if above else 1.0
    size_ratio = min(cand["size"] / max(median_size, 1.0), 2.0) / 2.0
    return [row_peers, col_peers, has_left, left_gap, has_above, above_is_num, align_err, size_ratio]


def weak_label(cand):
    """+1 confident matrix cell, -1 confident anomaly, None -> net decides."""
    rp = cand.get("row_peers", 0)
    left = cand.get("left")
    above = cand.get("above")
    above_is_num = bool(above and NUM_RE.match(above["text"].strip()))
    if rp >= 3 and left and above and not above_is_num:
        return 1.0
    if rp <= 1 and (not left or not above or above_is_num):
        return -1.0
    return None


class MicrogradAnomalyModel:
    """MLP(8,[8,8,1]) trained by micrograd; vectorised readout for inference."""

    def __init__(self, seed=1337):
        random.seed(seed)
        self.net = MLP(8, [8, 8, 1])
        self.loss_curve = []
        self.acc_curve = []
        self.trained = False
        self._W = None

    def train(self, X, Y, epochs=26, batch=44, log=None):
        n = len(X)
        if n < 8:
            return False
        for ep in range(epochs):
            idx = random.sample(range(n), min(batch, n))
            xb = [X[i] for i in idx]
            yb = [Y[i] for i in idx]
            scores = [self.net([float(v) for v in x]) for x in xb]
            losses = [(1 + -yi * si).relu() for yi, si in zip(yb, scores)]
            data_loss = sum(losses) * (1.0 / len(losses))
            reg_loss = 1e-4 * sum((p * p for p in self.net.parameters()))
            total = data_loss + reg_loss
            self.net.zero_grad()
            total.backward()
            lr = 0.8 - 0.7 * ep / max(epochs - 1, 1)
            for p in self.net.parameters():
                p.data -= lr * p.grad
            acc = sum((yi > 0) == (si.data > 0) for yi, si in zip(yb, scores)) / len(yb)
            self.loss_curve.append(round(float(total.data), 4))
            self.acc_curve.append(round(float(acc), 4))
            if log and (ep % 5 == 0 or ep == epochs - 1):
                log(f"micrograd epoch {ep + 1}/{epochs}  loss={total.data:.4f}  acc={acc * 100:.1f}%")
        self.trained = True
        self._readout()
        return True

    def _readout(self):
        self._W = []
        for layer in self.net.layers:
            W = np.array([[w.data for w in nrn.w] for nrn in layer.neurons], dtype=np.float64)
            b = np.array([nrn.b.data for nrn in layer.neurons], dtype=np.float64)
            self._W.append((W, b, layer.neurons[0].nonlin))

    def score(self, X):
        A = np.asarray(X, dtype=np.float64)
        if A.ndim == 1:
            A = A[None, :]
        if not self._W:
            self._readout()
        for W, b, nonlin in self._W:
            A = A @ W.T + b
            if nonlin:
                A = np.maximum(A, 0.0)
        margin = A[:, 0]
        conf = 1.0 / (1.0 + np.exp(-2.0 * margin))
        return conf, margin

    def to_dict(self):
        return {
            "loss_curve": self.loss_curve,
            "acc_curve": self.acc_curve,
            "params": [p.data for p in self.net.parameters()],
            "arch": [8, 8, 8, 1],
            "features": FEATURE_NAMES,
        }

    def load_params(self, params):
        for p, v in zip(self.net.parameters(), params):
            p.data = v
        self.trained = True
        self._readout()


MODEL_PATH = os.path.join(os.environ.get("DATA_DIR", "/app/data"), "micrograd_anomaly.json")


def save_model(model):
    try:
        with open(MODEL_PATH, "w") as f:
            json.dump(model.to_dict(), f)
    except Exception:
        pass

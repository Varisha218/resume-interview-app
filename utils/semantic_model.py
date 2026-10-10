"""Local semantic embedding model used for resume <-> JD matching.

This replaces the previous hardcoded synonym dictionaries
(SEMANTIC_PARTIAL_MATCHES) and TF-IDF similarity with a real pretrained
sentence-embedding model (SBERT family: all-MiniLM-L6-v2). Everything runs
locally/offline after the one-time model download on first run -- no API
keys, no per-request network calls.

The model maps any text (a word, a phrase, a sentence, a full resume) to a
384-dimensional vector such that semantically similar texts end up close
together in vector space, regardless of exact wording. That's what lets us
recognize e.g. "led a team of engineers" as related to "leadership" without
anyone hand-writing that pair.
"""

import re
import threading
import warnings

import numpy as np

_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_MAX_WORDS_PER_CHUNK = 150  # keeps each chunk within the model's token window

_model = None
_model_lock = threading.Lock()
_model_load_error = None


def _load_model():
    """Lazily load and cache the sentence-transformer model (thread-safe)."""
    global _model, _model_load_error
    if _model is not None or _model_load_error is not None:
        return _model

    with _model_lock:
        if _model is None and _model_load_error is None:
            try:
                from sentence_transformers import SentenceTransformer
                _model = SentenceTransformer(_MODEL_NAME)
            except Exception as e:  # offline / first-run download failure / etc.
                _model_load_error = e
                warnings.warn(
                    f"[semantic_model] Could not load '{_MODEL_NAME}' ({e!r}). "
                    "Falling back to plain word-overlap matching for skill "
                    "similarity -- this is much weaker at recognizing skills "
                    "phrased differently in the resume vs. the job "
                    "description. Run `pip install sentence-transformers` "
                    "and ensure the app has internet access on first run to "
                    "enable the full semantic model.",
                    RuntimeWarning,
                )
    return _model


def is_model_available() -> bool:
    return _load_model() is not None


def _chunk_text(text: str) -> list:
    words = text.split()
    if not words:
        return []
    chunks = []
    for i in range(0, len(words), _MAX_WORDS_PER_CHUNK):
        chunk = " ".join(words[i:i + _MAX_WORDS_PER_CHUNK])
        if chunk.strip():
            chunks.append(chunk)
    return chunks


def embed(texts: list) -> np.ndarray:
    """Embed a list of strings into normalized vectors, shape (n, dim)."""
    model = _load_model()
    if model is None:
        return np.zeros((len(texts), 1), dtype=np.float32)
    vectors = model.encode(list(texts), normalize_embeddings=True, convert_to_numpy=True)
    return vectors


def embed_document(text: str) -> np.ndarray:
    """Embed a long document by chunking + mean pooling, so we aren't
    limited to only the first ~256 tokens of a resume/JD."""
    model = _load_model()
    if model is None:
        return np.zeros((1,), dtype=np.float32)

    chunks = _chunk_text(text)
    if not chunks:
        return np.zeros(model.get_sentence_embedding_dimension(), dtype=np.float32)

    chunk_vecs = model.encode(chunks, normalize_embeddings=False, convert_to_numpy=True)
    doc_vec = chunk_vecs.mean(axis=0)
    norm = np.linalg.norm(doc_vec)
    if norm > 0:
        doc_vec = doc_vec / norm
    return doc_vec


_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "so", "of", "in", "on",
    "at", "to", "for", "with", "as", "is", "are", "was", "were", "be", "been",
    "being", "this", "that", "these", "those", "it", "its", "we", "you", "your",
    "our", "i", "he", "she", "they", "them", "his", "her", "their", "from",
    "by", "will", "would", "can", "could", "should", "may", "might", "have",
    "has", "had", "do", "does", "did", "not", "no", "yes", "such", "than",
    "into", "about", "over", "under", "up", "down", "out", "off", "again",
    "further", "here", "there", "when", "where", "why", "how", "all", "any",
    "both", "each", "few", "more", "most", "other", "some", "own", "same",
    "s", "t", "just", "also", "etc", "including", "including but",
}


def _document_term_freqs(text: str) -> dict:
    words = re.findall(r"[a-z0-9\+\#\./]+", text.lower())
    freqs = {}
    for w in words:
        if w in _STOPWORDS or len(w) < 2:
            continue
        freqs[w] = freqs.get(w, 0) + 1
    return freqs


def _document_lexical_fallback(text_a: str, text_b: str) -> float:
    """Whole-document lexical fallback used only when the embedding model
    can't be loaded. A previous version used plain Jaccard word-overlap over
    the *entire raw text* (including stopwords), which is extremely
    punishing for two documents of different length/phrasing -- a resume
    and JD that are actually a strong match would still share only a small
    fraction of their combined vocabulary, since most of each document is
    unique prose, names, and formatting that will never match. That made
    the reported "contextual similarity" swing wildly and mostly reflect
    document-length/style differences rather than actual topical fit.

    Instead, build stopword-filtered term-frequency vectors for each
    document and compare them with cosine similarity -- the standard,
    much more stable "bag of words" similarity measure, and a reasonable
    offline stand-in for real sentence embeddings.
    """
    freqs_a = _document_term_freqs(text_a)
    freqs_b = _document_term_freqs(text_b)
    if not freqs_a or not freqs_b:
        return 0.0

    vocab = set(freqs_a) | set(freqs_b)
    vec_a = np.array([freqs_a.get(w, 0) for w in vocab], dtype=np.float32)
    vec_b = np.array([freqs_b.get(w, 0) for w in vocab], dtype=np.float32)
    return cosine(vec_a, vec_b)


def document_similarity(text_a: str, text_b: str) -> float:
    """Similarity between two long documents, with an automatic lexical
    fallback if the embedding model couldn't be loaded (e.g. no internet on
    a machine that has never run this app before).

    The raw cosine number is then calibrated (see _calibrate) before being
    returned, since raw cosine similarity between two *different documents*
    (a resume and a JD, written in totally different styles/structures)
    almost never approaches 1.0 even for a great match -- with real
    sentence embeddings specifically, unrelated documents commonly still
    score ~0.15-0.3 due to how the embedding space is shaped, and a genuine
    strong match usually tops out around 0.7-0.8, not 1.0. Reporting the
    raw number as a 0-100% "contextual similarity" made even excellent
    matches look mediocre (e.g. 50-60%) purely because of this scale
    mismatch, not because the match was actually weak.
    """
    if not is_model_available():
        raw = _document_lexical_fallback(text_a, text_b)
        return _calibrate(raw, _FALLBACK_FLOOR, _FALLBACK_CEILING)
    vec_a = embed_document(text_a)
    vec_b = embed_document(text_b)
    raw = cosine(vec_a, vec_b)
    return _calibrate(raw, _REAL_MODEL_FLOOR, _REAL_MODEL_CEILING)


# Calibration bounds: raw cosine scores at/below `floor` are treated as "no
# real topical relationship" (displayed as ~0%), and raw scores at/above
# `ceiling` are treated as "as good a match as two differently-worded
# documents realistically get" (displayed as 100%). Values in between are
# scaled linearly. Bounds differ between the real embedding model and the
# lexical fallback because they operate on different raw scales.
#
# Real-model bounds (0.15/0.75) reflect all-MiniLM-L6-v2's typical behavior:
# unrelated short/medium texts commonly still cosine around 0.1-0.3, while
# strongly related but differently-phrased documents typically land in the
# 0.5-0.8 range.
_REAL_MODEL_FLOOR = 0.15
_REAL_MODEL_CEILING = 0.75

# Fallback bounds calibrated empirically against this app's own stopword-
# filtered term-frequency cosine: an unrelated resume/JD pair scored ~0.06,
# a genuine match with different wording scored ~0.46, and a near-identical
# resume/JD pair scored ~0.67.
_FALLBACK_FLOOR = 0.05
_FALLBACK_CEILING = 0.68


def _calibrate(raw: float, floor: float, ceiling: float) -> float:
    if ceiling <= floor:
        return max(0.0, min(1.0, raw))
    scaled = (raw - floor) / (ceiling - floor)
    return max(0.0, min(1.0, scaled))


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a).reshape(-1)
    b = np.asarray(b).reshape(-1)
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def similarity_matrix(list_a: list, list_b: list) -> np.ndarray:
    """Return an (len(list_a) x len(list_b)) cosine-similarity matrix."""
    if not list_a or not list_b:
        return np.zeros((len(list_a), len(list_b)))
    if not is_model_available():
        return _lexical_fallback_matrix(list_a, list_b)
    vecs_a = embed(list_a)
    vecs_b = embed(list_b)
    return vecs_a @ vecs_b.T


# ---------------------------------------------------------------------------
# Offline fallback (only used if the model genuinely cannot be loaded, e.g.
# no internet on the very first run before it's cached). Keeps the app
# functional instead of crashing, using plain token overlap.
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> set:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _lexical_fallback_matrix(list_a: list, list_b: list) -> np.ndarray:
    tokens_a = [_tokenize(t) for t in list_a]
    tokens_b = [_tokenize(t) for t in list_b]
    matrix = np.zeros((len(list_a), len(list_b)))
    for i, ta in enumerate(tokens_a):
        for j, tb in enumerate(tokens_b):
            union = ta | tb
            if union:
                matrix[i, j] = len(ta & tb) / len(union)
    return matrix

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import faiss
import numpy as np
import pytest


# ── helpers ──────────────────────────────────────────────────────────────────

SAMPLE_METADATA = [
    {"id": "p001", "patois": "Lo pan de vesin", "fr": "Le pain du voisin", "it": "Il pane del vicino", "comune": "Aosta"},
    {"id": "p002", "patois": "Chi drom troua pan", "fr": "Qui dort trouve du pain", "it": "Chi dorme trova pane", "comune": "Gressan"},
]

SAMPLE_VOCAB_META = [
    {"id": "v001", "patois": "de no s-atre", "it": "degli altri", "uso": "comune", "_tipo": "parola"},
    {"id": "f001", "patois": "a la bon'eura", "it": "alla buon'ora", "contesto": "saluto", "_tipo": "frase"},
]


def _make_flat_index(dim: int, n: int) -> faiss.IndexFlatIP:
    index = faiss.IndexFlatIP(dim)
    vecs = np.random.rand(n, dim).astype("float32")
    faiss.normalize_L2(vecs)
    index.add(vecs)
    return index


@pytest.fixture()
def rag_instance():
    """ProverbsRAG with real FAISS indices but mocked embedder and Anthropic client."""
    dim = 8
    with tempfile.TemporaryDirectory() as tmp:
        storage = Path(tmp)
        idx_path  = storage / "faiss.index"
        meta_path = storage / "metadata.json"
        vidx_path = storage / "vocab.index"
        vmeta_path = storage / "vocab_metadata.json"

        faiss.write_index(_make_flat_index(dim, len(SAMPLE_METADATA)), str(idx_path))
        meta_path.write_text(json.dumps(SAMPLE_METADATA), encoding="utf-8")
        faiss.write_index(_make_flat_index(dim, len(SAMPLE_VOCAB_META)), str(vidx_path))
        vmeta_path.write_text(json.dumps(SAMPLE_VOCAB_META), encoding="utf-8")

        with (
            patch("app.rag.INDEX_PATH",       idx_path),
            patch("app.rag.METADATA_PATH",    meta_path),
            patch("app.rag.VOCAB_INDEX_PATH", vidx_path),
            patch("app.rag.VOCAB_META_PATH",  vmeta_path),
            patch("app.rag.embedder") as mock_embedder,
            patch("app.rag.anthropic_client") as mock_claude,
        ):
            # embedder returns a fixed vector
            fixed_vec = np.random.rand(dim).astype("float32")
            fixed_vec /= np.linalg.norm(fixed_vec)
            mock_embedder.embed.return_value = iter([fixed_vec])

            from app.rag import ProverbsRAG
            rag = ProverbsRAG()
            rag._mock_embedder = mock_embedder
            rag._mock_claude   = mock_claude
            yield rag


# ── normalize ────────────────────────────────────────────────────────────────

def test_normalize():
    from app.rag import normalize
    assert normalize("  Hello   World  ") == "hello world"
    assert normalize("UPPER") == "upper"
    assert normalize("") == ""


# ── format_context ────────────────────────────────────────────────────────────

def test_format_context_contains_all_fields():
    from app.rag import ProverbsRAG
    items = [{**SAMPLE_METADATA[0], "score": 0.9}]
    result = ProverbsRAG.format_context(items)
    assert "p001" in result
    assert "Lo pan de vesin" in result
    assert "Le pain du voisin" in result
    assert "Il pane del vicino" in result
    assert "Aosta" in result


def test_format_context_numbers_documents():
    from app.rag import ProverbsRAG
    items = [{**m, "score": 0.5} for m in SAMPLE_METADATA]
    result = ProverbsRAG.format_context(items)
    assert "Documento 1" in result
    assert "Documento 2" in result


def test_format_context_empty():
    from app.rag import ProverbsRAG
    assert ProverbsRAG.format_context([]) == ""


# ── format_vocab ──────────────────────────────────────────────────────────────

def test_format_vocab_word():
    from app.rag import ProverbsRAG
    items = [{**SAMPLE_VOCAB_META[0], "score": 0.8}]
    result = ProverbsRAG.format_vocab(items)
    assert "de no s-atre" in result
    assert "degli altri" in result


def test_format_vocab_phrase():
    from app.rag import ProverbsRAG
    items = [{**SAMPLE_VOCAB_META[1], "score": 0.7}]
    result = ProverbsRAG.format_vocab(items)
    assert "a la bon'eura" in result
    assert "contesto" in result


def test_format_vocab_empty():
    from app.rag import ProverbsRAG
    assert ProverbsRAG.format_vocab([]) == ""


# ── retrieve ──────────────────────────────────────────────────────────────────

def test_retrieve_returns_list(rag_instance):
    with patch("app.rag.embedder", rag_instance._mock_embedder):
        results = rag_instance.retrieve("proverbio sul pane", top_k=2)
    assert isinstance(results, list)
    assert len(results) <= 2
    for item in results:
        assert "id" in item
        assert "score" in item


def test_retrieve_vocab_returns_list(rag_instance):
    with patch("app.rag.embedder", rag_instance._mock_embedder):
        results = rag_instance.retrieve_vocab("risposta base", top_k=2)
    assert isinstance(results, list)
    assert len(results) <= 2


# ── generate_answer ───────────────────────────────────────────────────────────

def _mock_claude_response(text: str):
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.content = [block]
    return response


def test_generate_answer_returns_string(rag_instance):
    rag_instance._mock_claude.messages.create.return_value = _mock_claude_response(
        "((patois: Lo pan de vesin))\n((fr: Le pain))\n((it: Il pane))"
    )
    with patch("app.rag.embedder", rag_instance._mock_embedder), \
         patch("app.rag.anthropic_client", rag_instance._mock_claude):
        answer = rag_instance.generate_answer("pane", SAMPLE_METADATA[:1])
    assert isinstance(answer, str)
    assert len(answer) > 0


def test_generate_answer_skips_enrichment_when_no_vocab(rag_instance):
    """If retrieve_vocab returns nothing, the base answer is returned as-is."""
    base_text = "Risposta base senza arricchimento."
    rag_instance._mock_claude.messages.create.return_value = _mock_claude_response(base_text)

    with patch("app.rag.embedder", rag_instance._mock_embedder), \
         patch("app.rag.anthropic_client", rag_instance._mock_claude), \
         patch.object(rag_instance, "retrieve_vocab", return_value=[]):
        answer = rag_instance.generate_answer("pane", SAMPLE_METADATA[:1])

    assert answer == base_text
    assert rag_instance._mock_claude.messages.create.call_count == 1

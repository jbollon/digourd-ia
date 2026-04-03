from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


SAMPLE_RETRIEVED = [
    {
        "id": "p001",
        "patois": "Lo pan de vesin",
        "fr": "Le pain du voisin",
        "it": "Il pane del vicino",
        "comune": "Aosta",
        "score": 0.92,
    }
]


@pytest.fixture()
def client():
    mock_rag = MagicMock()
    mock_rag.retrieve.return_value = SAMPLE_RETRIEVED
    mock_rag.generate_answer.return_value = (
        "((patois: Lo pan de vesin))\n((fr: Le pain du voisin))\n((it: Il pane del vicino))"
    )

    with patch("app.rag.ProverbsRAG", return_value=mock_rag):
        # Re-import app so the patched ProverbsRAG is used
        import importlib
        import app.main as main_module
        importlib.reload(main_module)
        yield TestClient(main_module.app)


class TestHomeEndpoint:
    def test_returns_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


class TestChatEndpoint:
    def test_valid_request(self, client):
        resp = client.post("/chat", json={"message": "proverbio sul pane"})
        assert resp.status_code == 200
        body = resp.json()
        assert "answer" in body
        assert "retrieved" in body

    def test_answer_is_string(self, client):
        resp = client.post("/chat", json={"message": "test"})
        assert isinstance(resp.json()["answer"], str)

    def test_retrieved_structure(self, client):
        resp = client.post("/chat", json={"message": "test"})
        docs = resp.json()["retrieved"]
        assert len(docs) == 1
        doc = docs[0]
        for field in ("id", "patois", "fr", "it", "comune", "score"):
            assert field in doc

    def test_with_history(self, client):
        history = [{"role": "user", "content": "ciao"}, {"role": "assistant", "content": "salut"}]
        resp = client.post("/chat", json={"message": "altro proverbio", "history": history})
        assert resp.status_code == 200

    def test_missing_message_returns_422(self, client):
        resp = client.post("/chat", json={})
        assert resp.status_code == 422

    def test_empty_message(self, client):
        resp = client.post("/chat", json={"message": ""})
        assert resp.status_code == 200

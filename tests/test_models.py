import pytest
from pydantic import ValidationError

from app.models import ChatRequest, ChatResponse, RetrievedDoc


def make_doc(**kwargs):
    defaults = dict(id="1", patois="patois text", fr="french", it="italian", comune="Aosta", score=0.9)
    return RetrievedDoc(**{**defaults, **kwargs})


class TestChatRequest:
    def test_minimal(self):
        req = ChatRequest(message="hello")
        assert req.message == "hello"
        assert req.history is None

    def test_with_history(self):
        history = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "salut"}]
        req = ChatRequest(message="test", history=history)
        assert len(req.history) == 2

    def test_missing_message_raises(self):
        with pytest.raises(ValidationError):
            ChatRequest()


class TestRetrievedDoc:
    def test_valid(self):
        doc = make_doc()
        assert doc.id == "1"
        assert doc.score == 0.9

    def test_missing_field_raises(self):
        with pytest.raises(ValidationError):
            RetrievedDoc(id="1", patois="p", fr="f", it="i")  # missing comune and score

    def test_score_is_float(self):
        doc = make_doc(score=1)
        assert isinstance(doc.score, float)


class TestChatResponse:
    def test_valid(self):
        resp = ChatResponse(answer="some answer", retrieved=[make_doc()])
        assert resp.answer == "some answer"
        assert len(resp.retrieved) == 1

    def test_empty_retrieved(self):
        resp = ChatResponse(answer="nope", retrieved=[])
        assert resp.retrieved == []

    def test_missing_fields_raise(self):
        with pytest.raises(ValidationError):
            ChatResponse(answer="only answer")

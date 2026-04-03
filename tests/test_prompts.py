from app.prompts import SYSTEM_PROMPT, build_user_prompt


def test_system_prompt_not_empty():
    assert SYSTEM_PROMPT.strip()


def test_system_prompt_mentions_persona():
    assert "Digourd-IA" in SYSTEM_PROMPT


def test_build_user_prompt_contains_query():
    prompt = build_user_prompt("cosa fare quando piove?", "contesto")
    assert "cosa fare quando piove?" in prompt


def test_build_user_prompt_contains_context():
    context = "Documento 1\nID: p001\nProverbio: test"
    prompt = build_user_prompt("query", context)
    assert context in prompt


def test_build_user_prompt_mentions_markers():
    prompt = build_user_prompt("q", "ctx")
    assert "((patois:" in prompt
    assert "((fr:" in prompt
    assert "((it:" in prompt

"""HTTP-level tests for the teacher flow (no OpenAI calls).

Generation is stubbed so the upload → generate → fetch path and DB wiring are
verified deterministically and for free; the real pipeline is exercised by
scripts/m1_demo.py.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401 — register tables on metadata
from app.core.db import get_session
from app.main import app
from app.services import assembly, embeddings


def _temp_session_override(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)

    def _override():
        with Session(engine) as session:
            yield session

    return _override


def _fake_build_game(*, parsed, source_document_id, title=None, **_):
    return {
        "game": {
            "schemaVersion": "1.0.0",
            "campaignId": "camp_test",
            "title": title or "Untitled",
            "description": "stub",
            "sourceDocumentId": source_document_id,
            "combatConfig": {"playerStartingHp": 100},
            "acts": [],
        },
        "eval": {"total_questions": 0, "grounded_pct": 0.0, "clean_pct": 0.0, "flagged": []},
        "usage": {"input": 0, "output": 0, "reasoning": 0, "calls": 0},
        "estimated_cost_usd": 0.0,
    }


def test_teacher_upload_generate_fetch(monkeypatch, tmp_path):
    app.dependency_overrides[get_session] = _temp_session_override(tmp_path)
    monkeypatch.setattr(assembly, "build_game", _fake_build_game)
    # Stub embeddings so the upload endpoint's chunk-embedding makes no API call.
    monkeypatch.setattr(
        embeddings,
        "embed_texts_with_usage",
        lambda texts, model=None: ([[0.0, 1.0] for _ in texts], {"model": "fake", "input": 0, "output": 0}),
    )
    try:
        client = TestClient(app)

        # 1. upload + parse a markdown document (local, no API)
        files = {
            "file": ("syllabus.md", b"# Topic\n## Sub\nThe sky is blue.\n", "text/markdown"),
        }
        r = client.post("/teacher/documents", files=files)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "parsed"
        assert body["token_count"] > 0
        assert body["section_count"] >= 2
        doc_id = body["id"]

        # 2. generate a campaign (stubbed pipeline → no API cost)
        r2 = client.post(
            "/teacher/campaigns/generate", json={"document_id": doc_id, "title": "My Game"}
        )
        assert r2.status_code == 200, r2.text
        campaign_id = r2.json()["campaign_id"]
        assert r2.json()["title"] == "My Game"

        # 3. fetch the stored game
        r3 = client.get(f"/teacher/campaigns/{campaign_id}")
        assert r3.status_code == 200, r3.text
        assert r3.json()["game"]["schemaVersion"] == "1.0.0"

        # 4. unknown campaign → 404
        assert client.get("/teacher/campaigns/nope").status_code == 404
    finally:
        app.dependency_overrides.clear()

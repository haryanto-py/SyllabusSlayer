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


def _seed_game() -> dict:
    return {
        "schemaVersion": "1.0.0", "campaignId": "c1", "title": "T", "description": "d",
        "sourceDocumentId": "doc",
        "combatConfig": {
            "playerStartingHp": 100, "baseDamagePerCorrect": 10,
            "streakMultipliers": [1.0, 1.25, 1.5, 2.0], "wrongAnswerHpCost": 8,
            "xpPerCorrectByDifficulty": {"easy": 10, "medium": 20, "hard": 35},
            "levelXpCurve": [0, 100, 250, 450, 700],
        },
        "acts": [{
            "actId": "a1", "order": 1, "title": "Act", "syllabusTopic": "x", "summary": "s",
            "encounters": [{
                "encounterId": "e1", "order": 1, "kind": "boss", "title": "Boss",
                "enemyName": "E", "enemyFlavor": "f", "subTopic": "x",
                "combat": {"enemyMaxHp": 30, "enemyBaseDamage": 8, "kindHpMultiplier": 2.0},
                "rewards": [],
                "questions": [
                    {"questionId": "q1", "questionType": "multiple_choice", "bloomLevel": "remember",
                     "difficulty": "easy", "prompt": "?", "sourceChunkIds": ["c"],
                     "sourceQuote": "sky is blue", "sourcePage": None, "explanation": "blue",
                     "hint": None, "options": [{"optionId": "a", "text": "blue"},
                     {"optionId": "b", "text": "red"}], "correctOptionIds": ["a"],
                     "correctBoolean": None, "acceptedAnswers": None, "caseSensitive": None,
                     "orderedItems": None, "matchPairs": None},
                    {"questionId": "q2", "questionType": "true_false", "bloomLevel": "remember",
                     "difficulty": "easy", "prompt": "?", "sourceChunkIds": ["c"], "sourceQuote": "x",
                     "sourcePage": None, "explanation": "e", "hint": None, "options": None,
                     "correctOptionIds": None, "correctBoolean": True, "acceptedAnswers": None,
                     "caseSensitive": None, "orderedItems": None, "matchPairs": None},
                ],
            }],
        }],
    }


def test_student_play_flow(tmp_path):
    from app.core.security import CurrentUser, get_current_user
    from app.models.tables import Campaign, CampaignStatus, User, UserRole

    engine = create_engine(
        f"sqlite:///{tmp_path / 'play.db'}", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    game = _seed_game()
    with Session(engine) as s:
        s.add(User(id="stud1", email="s@x", role=UserRole.student, display_name="s",
                   auth_provider_id="stud1"))
        s.add(Campaign(id="camp1", document_id="docX", teacher_id="t1", title="T",
                       status=CampaignStatus.ready, game_json=game,
                       combat_config=game["combatConfig"], schema_version="1.0.0"))
        s.commit()

    def _override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _override
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        sub="stud1", email="s@x", role="student"
    )
    try:
        client = TestClient(app)
        r = client.post("/student/play/camp1/start")
        assert r.status_code == 200, r.text
        sid = r.json()["session_id"]
        # game is redacted — no answer fields leaked to the client
        q0 = r.json()["game"]["acts"][0]["encounters"][0]["questions"][0]
        assert "correctOptionIds" not in q0 and "explanation" not in q0

        # correct MCQ → 10 damage, streak 1
        r1 = client.post(f"/student/play/{sid}/answer",
                         json={"encounter_id": "e1", "question_id": "q1", "answer": "a"})
        assert r1.status_code == 200, r1.text
        assert r1.json()["isCorrect"] is True
        assert r1.json()["damage"] == 10 and r1.json()["streak"] == 1

        # wrong T/F → streak resets, HP drops by 8
        r2 = client.post(f"/student/play/{sid}/answer",
                         json={"encounter_id": "e1", "question_id": "q2", "answer": False})
        assert r2.json()["isCorrect"] is False
        assert r2.json()["streak"] == 0 and r2.json()["hp"] == 92

        # finish → completed, score persisted
        r3 = client.post(f"/student/play/{sid}/finish")
        assert r3.status_code == 200
        assert r3.json()["status"] == "completed" and r3.json()["score"] == 10
    finally:
        app.dependency_overrides.clear()


# --------------------------------------------------------------------------- #
# M5.3 meta-progression + permadeath
# --------------------------------------------------------------------------- #
def _meta_env(tmp_path, dbname: str, student: str = "stud1"):
    """Seed a campaign + student and override auth as that student. Caller clears overrides."""
    from app.core.security import CurrentUser, get_current_user
    from app.models.tables import Campaign, CampaignStatus, User, UserRole

    engine = create_engine(
        f"sqlite:///{tmp_path / dbname}", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    game = _seed_game()
    with Session(engine) as s:
        s.add(User(id=student, email=f"{student}@x", role=UserRole.student,
                   display_name="s", auth_provider_id=student))
        s.add(Campaign(id="camp1", document_id="docX", teacher_id="t1", title="T",
                       status=CampaignStatus.ready, game_json=game,
                       combat_config=game["combatConfig"], schema_version="1.0.0"))
        s.commit()

    def _override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _override
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        sub=student, email=f"{student}@x", role="student"
    )
    return engine


def test_meta_permadeath_and_bank_on_death(tmp_path):
    _meta_env(tmp_path, "death.db")
    try:
        client = TestClient(app)
        start = client.post("/student/play/camp1/start").json()
        assert start["hp"] == 100 and start["maxHp"] == 100 and start["startBonusMaxHp"] == 0
        sid = start["session_id"]

        # bank one correct answer, then die on repeated wrong answers (8 HP each)
        client.post(f"/student/play/{sid}/answer",
                    json={"encounter_id": "e1", "question_id": "q1", "answer": "a"})
        last = None
        for _ in range(20):
            last = client.post(f"/student/play/{sid}/answer",
                               json={"encounter_id": "e1", "question_id": "q2", "answer": False}).json()
            if last["playerDown"]:
                break
        assert last["playerDown"] and last["outcome"] == "defeated" and last["hp"] == 0
        # the killing /answer surfaces the meta banked THIS run (not a stale 0)
        assert last["insightEarned"] > 0 and last["newlyUnlocked"]

        # server-enforced permadeath: a dead run cannot be continued
        dead = client.post(f"/student/play/{sid}/answer",
                           json={"encounter_id": "e1", "question_id": "q1", "answer": "a"})
        assert dead.status_code == 409

        # learning banked despite the loss
        prof = client.get("/student/campaigns/camp1/profile").json()
        assert "Act" in prof["masteryByTopic"]
        assert prof["bestScore"] == 10  # the one correct answer's damage, persisted
    finally:
        app.dependency_overrides.clear()


def test_meta_victory_banks_idempotent_and_upsert(tmp_path):
    from sqlmodel import select

    from app.models.tables import StudentProgress

    engine = _meta_env(tmp_path, "victory.db")
    try:
        client = TestClient(app)
        sid = client.post("/student/play/camp1/start").json()["session_id"]
        client.post(f"/student/play/{sid}/answer",
                    json={"encounter_id": "e1", "question_id": "q1", "answer": "a"})
        client.post(f"/student/play/{sid}/answer",
                    json={"encounter_id": "e1", "question_id": "q2", "answer": True})

        fin = client.post(f"/student/play/{sid}/finish").json()
        assert fin["status"] == "completed" and fin["outcome"] == "completed"
        assert fin["insightEarned"] > 0
        assert "Act" in fin["masteryByTopic"]
        assert any(r["relicId"] in ("keen_focus", "aegis") for r in fin["newlyUnlocked"])
        assert fin["bestScore"] == fin["score"] and fin["isNewBest"] is True
        total = fin["insightTotal"]

        # repeat /finish is idempotent — no double award, no duplicate row, no false "best"
        again = client.post(f"/student/play/{sid}/finish").json()
        assert again["insightEarned"] == 0 and again["insightTotal"] == total
        assert again["isNewBest"] is False
        with Session(engine) as s:
            rows = s.exec(
                select(StudentProgress).where(StudentProgress.campaign_id == "camp1")
            ).all()
            assert len(rows) == 1
    finally:
        app.dependency_overrides.clear()


def test_meta_total_xp_accumulates_across_runs(tmp_path):
    _meta_env(tmp_path, "xp.db")
    try:
        client = TestClient(app)
        for _ in range(2):  # two runs, each banks one correct easy answer (10 XP)
            sid = client.post("/student/play/camp1/start").json()["session_id"]
            client.post(f"/student/play/{sid}/answer",
                        json={"encounter_id": "e1", "question_id": "q1", "answer": "a"})
            client.post(f"/student/play/{sid}/finish")
        prof = client.get("/student/campaigns/camp1/profile").json()
        assert prof["totalXp"] == 20  # cumulative across runs, not a per-run max
    finally:
        app.dependency_overrides.clear()


def test_meta_start_seed_reward_gating_and_guardrail(tmp_path):
    from app.services import meta

    _meta_env(tmp_path, "seed.db")
    try:
        client = TestClient(app)
        # master "Act": 4 attempts, all correct (accuracy 1.0 >= threshold over >= min attempts)
        sid = client.post("/student/play/camp1/start").json()["session_id"]
        for qid, ans in [("q1", "a"), ("q2", True), ("q1", "a"), ("q2", True)]:
            client.post(f"/student/play/{sid}/answer",
                        json={"encounter_id": "e1", "question_id": qid, "answer": ans})
        fin = client.post(f"/student/play/{sid}/finish").json()
        assert fin["masteryByTopic"]["Act"]["accuracy"] == 1.0

        prof = client.get("/student/campaigns/camp1/profile").json()
        assert prof["startBonusMaxHp"] == meta.HP_PER_MASTERED_TOPIC  # 1 topic mastered
        unlocked = {r["relicId"] for r in prof["unlockedRelics"]}
        assert {"keen_focus", "aegis"} <= unlocked and meta.UNLOCK_ORDER[0] in unlocked

        # a NEW run is seeded with the earned HP bonus
        start2 = client.post("/student/play/camp1/start").json()
        assert start2["startBonusMaxHp"] == meta.HP_PER_MASTERED_TOPIC
        assert start2["hp"] == 105 and start2["maxHp"] == 105
        sid2 = start2["session_id"]

        # reward options only offer unlocked relics; a locked relic is rejected server-side
        opts = client.get(f"/student/play/{sid2}/reward-options?node_id=n1").json()["options"]
        assert {o["relicId"] for o in opts} <= unlocked
        locked = "second_thought"  # rare, not unlocked after mastering one topic
        assert locked not in unlocked
        assert client.post(f"/student/play/{sid2}/reward",
                           json={"relic_id": locked}).status_code == 403

        # GUARDRAIL: meta is active, but a wrong answer is still wrong (correctness untouched)
        wrong = client.post(f"/student/play/{sid2}/answer",
                            json={"encounter_id": "e1", "question_id": "q1", "answer": "b"}).json()
        assert wrong["isCorrect"] is False
    finally:
        app.dependency_overrides.clear()


def test_classes_and_enrollment(tmp_path):
    app.dependency_overrides[get_session] = _temp_session_override(tmp_path)
    try:
        client = TestClient(app)
        teacher = {"X-Dev-Role": "teacher"}

        r = client.post("/teacher/classes", json={"name": "Bio 101"}, headers=teacher)
        assert r.status_code == 200, r.text
        cid, code = r.json()["id"], r.json()["join_code"]
        assert len(code) == 6

        for sid in ("stud-a", "stud-b"):
            hdr = {"X-Dev-Role": "student", "X-Dev-User": sid}
            jr = client.post("/student/classes/join", json={"join_code": code}, headers=hdr)
            assert jr.status_code == 200, jr.text
            assert jr.json()["id"] == cid

        # re-join is idempotent (no duplicate enrollment)
        client.post("/student/classes/join", json={"join_code": code},
                    headers={"X-Dev-Role": "student", "X-Dev-User": "stud-a"})

        roster = client.get(f"/teacher/classes/{cid}", headers=teacher).json()["roster"]
        assert len(roster) == 2

        mine = client.get("/student/classes",
                          headers={"X-Dev-Role": "student", "X-Dev-User": "stud-a"}).json()
        assert any(c["id"] == cid for c in mine)

        bad = client.post("/student/classes/join", json={"join_code": "ZZZZZZ"},
                          headers={"X-Dev-Role": "student", "X-Dev-User": "stud-a"})
        assert bad.status_code == 404

        listed = client.get("/teacher/classes", headers=teacher).json()
        assert listed[0]["student_count"] == 2
    finally:
        app.dependency_overrides.clear()


def test_lms_assign_play_review_analytics(tmp_path):
    from sqlmodel import select

    from app.models.tables import Campaign, CampaignStatus, User

    engine = create_engine(
        f"sqlite:///{tmp_path / 'lms.db'}", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)

    def _override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _override
    teacher = {"X-Dev-Role": "teacher"}
    student = {"X-Dev-Role": "student", "X-Dev-User": "stud-x"}
    try:
        client = TestClient(app)
        cls = client.post("/teacher/classes", json={"name": "C"}, headers=teacher).json()
        cid, code = cls["id"], cls["join_code"]

        # seed a campaign owned by the dev-teacher (campaigns normally come from generate())
        with Session(engine) as s:
            t = s.exec(select(User).where(User.auth_provider_id == "dev-teacher")).first()
            game = _seed_game()
            s.add(Campaign(id="lms_camp", document_id="d", teacher_id=t.id, title="T",
                           status=CampaignStatus.ready, game_json=game,
                           combat_config=game["combatConfig"], schema_version="1.0.0"))
            s.commit()

        client.post("/student/classes/join", json={"join_code": code}, headers=student)

        asg = client.post(f"/teacher/classes/{cid}/assignments",
                          json={"campaign_id": "lms_camp"}, headers=teacher)
        assert asg.status_code == 200, asg.text
        aid = asg.json()["id"]

        mine = client.get("/student/assignments", headers=student).json()
        assert any(a["campaign_id"] == "lms_camp" for a in mine)

        st = client.post(f"/student/play/lms_camp/start?assignment_id={aid}", headers=student)
        assert st.status_code == 200, st.text
        sid = st.json()["session_id"]
        client.post(f"/student/play/{sid}/answer", headers=student,
                    json={"encounter_id": "e1", "question_id": "q1", "answer": "a"})

        # review: edit q1, then publish
        edit = client.put("/teacher/campaigns/lms_camp/questions/q1", headers=teacher, json={
            "questionId": "q1", "questionType": "multiple_choice", "bloomLevel": "remember",
            "difficulty": "easy", "prompt": "Edited prompt?", "sourceChunkIds": ["c"],
            "sourceQuote": "sky is blue", "sourcePage": 1, "explanation": "e", "hint": None,
            "options": [{"optionId": "a", "text": "blue"}, {"optionId": "b", "text": "red"}],
            "correctOptionIds": ["a"], "correctBoolean": None, "acceptedAnswers": None,
            "caseSensitive": None, "orderedItems": None, "matchPairs": None})
        assert edit.status_code == 200, edit.text
        assert client.post("/teacher/campaigns/lms_camp/publish",
                           headers=teacher).json()["status"] == "published"

        # analytics reflects the student's attempt
        an = client.get(f"/teacher/campaigns/lms_camp/analytics?class_id={cid}",
                        headers=teacher).json()
        assert an["summary"]["roster_size"] == 1
        assert an["students"][0]["attempts"] >= 1
        assert an["topics"] and an["items"]
    finally:
        app.dependency_overrides.clear()

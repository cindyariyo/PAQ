"""
Integration tests for /sessions endpoints.
"""
import json
import pytest
from tests.conftest import make_user, make_question, seed_questions, make_completed_session
from app.models import UserProfile


# ── Helpers ──────────────────────────────────────────────────────────────────

def _start(client, user_id):
    return client.post("/sessions/start", json={"user_id": user_id})


def _answer(client, session_id, user_id, question_id, answer,
            time_spent=10, retry_count=0, hint_level_shown=0):
    return client.post(f"/sessions/{session_id}/answer", json={
        "user_id": user_id,
        "question_id": question_id,
        "answer": answer,
        "time_spent_seconds": time_spent,
        "retry_count": retry_count,
        "hint_level_shown": hint_level_shown,
    })


def _set_settings(db, user_id, settings: dict):
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    profile.settings_json = json.dumps(settings)
    db.commit()


# ── Start session ─────────────────────────────────────────────────────────────

class TestStartSession:
    def test_start_returns_session_and_question(self, client, db):
        user = make_user(db)
        seed_questions(db)
        res = _start(client, user.id)
        assert res.status_code == 200
        data = res.json()
        assert "session_id" in data
        assert "question" in data
        assert data["hexad_type"] == "Achiever"
        assert data["session_number"] == 1

    def test_first_session_starts_at_level_1(self, client, db):
        user = make_user(db)
        seed_questions(db)
        data = _start(client, user.id).json()
        assert data["difficulty_level"] == 1

    def test_blocked_after_6_completed_sessions(self, client, db):
        user = make_user(db)
        seed_questions(db)
        for i in range(6):
            make_completed_session(db, user.id, session_number=i + 1)
        res = _start(client, user.id)
        assert res.status_code == 403
        assert res.json()["detail"] == "study_complete"

    def test_not_blocked_after_5_sessions(self, client, db):
        user = make_user(db)
        seed_questions(db)
        for i in range(5):
            make_completed_session(db, user.id, session_number=i + 1)
        res = _start(client, user.id)
        assert res.status_code == 200

    def test_session_number_increments(self, client, db):
        user = make_user(db)
        seed_questions(db)
        make_completed_session(db, user.id, session_number=1)
        data = _start(client, user.id).json()
        assert data["session_number"] == 2


# ── Session total questions ───────────────────────────────────────────────────

class TestSessionTotalQuestions:
    def test_level1_total_is_10(self, client, db):
        user = make_user(db)
        seed_questions(db)
        data = _start(client, user.id).json()
        assert data["session_total_questions"] == 10

    def test_level4_total_is_7(self, client, db):
        user = make_user(db, study_code="LVL4")
        make_question(db, difficulty=4)
        make_completed_session(db, user.id, session_number=1, difficulty=4)
        data = _start(client, user.id).json()
        assert data["session_total_questions"] == 7

    def test_level5_total_is_5(self, client, db):
        user = make_user(db, study_code="LVL5")
        make_question(db, difficulty=5)
        make_completed_session(db, user.id, session_number=1, difficulty=5)
        data = _start(client, user.id).json()
        assert data["session_total_questions"] == 5


# ── Answer endpoint ───────────────────────────────────────────────────────────

class TestAnswer:
    def _setup(self, client, db):
        """Create user, seed questions, start a session. Return (user_id, session_id, first_question)."""
        user = make_user(db)
        seed_questions(db)
        s = _start(client, user.id).json()
        return user.id, s["session_id"], s["question"]

    def test_correct_first_attempt_gives_25_xp(self, client, db):
        uid, sid, q = self._setup(client, db)
        correct = f"answer{q['difficulty']}"
        res = _answer(client, sid, uid, q["id"], correct, retry_count=0)
        data = res.json()
        assert res.status_code == 200
        assert data["correct"] is True
        assert data["xp"] == 25
        assert data["questions_answered"] == 1
        assert data["correct_count"] == 1

    def test_wrong_answer_gives_1_xp(self, client, db):
        uid, sid, q = self._setup(client, db)
        res = _answer(client, sid, uid, q["id"], "definitely_wrong")
        data = res.json()
        assert data["correct"] is False
        assert data["xp"] == 1
        assert data["streak"] == 0

    def test_wrong_answer_does_not_count_as_questions_answered(self, client, db):
        uid, sid, q = self._setup(client, db)
        res = _answer(client, sid, uid, q["id"], "wrong")
        assert res.json()["questions_answered"] == 0

    def test_effort_xp_on_wrong_gives_6(self, client, db):
        user = make_user(db)
        seed_questions(db)
        _set_settings(db, user.id, {"effort_xp": True})
        s = _start(client, user.id).json()
        q = s["question"]
        res = _answer(client, s["session_id"], user.id, q["id"], "wrong")
        data = res.json()
        assert data["correct"] is False
        assert data["xp"] == 6  # 1 base + 5 effort_xp

    def test_streak_increments_on_correct(self, client, db):
        uid, sid, q = self._setup(client, db)
        correct = f"answer{q['difficulty']}"
        data = _answer(client, sid, uid, q["id"], correct).json()
        assert data["streak"] == 1

    def test_wrong_answer_resets_streak(self, client, db):
        uid, sid, q = self._setup(client, db)
        correct = f"answer{q['difficulty']}"
        # Build streak to 1
        r1 = _answer(client, sid, uid, q["id"], correct).json()
        assert r1["streak"] == 1
        # Answer wrong on the next question
        next_q = r1.get("next_question")
        if next_q:
            r2 = _answer(client, sid, uid, next_q["id"], "wrong").json()
            assert r2["streak"] == 0

    def test_streak_shield_preserves_streak_on_wrong(self, client, db):
        user = make_user(db)
        seed_questions(db)
        _set_settings(db, user.id, {"streak_shield": True})
        s = _start(client, user.id).json()
        sid, q = s["session_id"], s["question"]
        correct = f"answer{q['difficulty']}"
        # Build streak
        r1 = _answer(client, sid, user.id, q["id"], correct).json()
        assert r1["streak"] == 1
        # Wrong answer — shield should absorb it
        next_q = r1.get("next_question")
        if next_q:
            r2 = _answer(client, sid, user.id, next_q["id"], "wrong").json()
            assert r2["streak"] == 1  # streak preserved

    def test_session_ends_when_all_questions_answered(self, client, db):
        user = make_user(db)
        # 5 level-5 questions so session_total = 5
        for i in range(5):
            make_question(db, difficulty=5, prompt=f"L5-{i}?",
                          options=["correct", "wrong1", "wrong2", "wrong3"],
                          correct="correct")
        make_completed_session(db, user.id, session_number=1, difficulty=5)
        s = _start(client, user.id).json()
        sid = s["session_id"]
        cur_q = s["question"]
        last_data = None
        for _ in range(5):
            last_data = _answer(client, sid, user.id, cur_q["id"], "correct").json()
            if last_data.get("next_question"):
                cur_q = last_data["next_question"]
        assert last_data["next_question"] is None
        assert last_data["questions_answered"] == 5


# ── Skip endpoint ─────────────────────────────────────────────────────────────

class TestSkip:
    def test_skip_increments_questions_answered(self, client, db):
        user = make_user(db)
        seed_questions(db)
        s = _start(client, user.id).json()
        sid, q = s["session_id"], s["question"]
        res = client.post(f"/sessions/{sid}/skip",
                          params={"user_id": user.id, "question_id": q["id"]})
        assert res.status_code == 200
        data = res.json()
        assert data["skipped"] is True
        assert data["questions_answered"] == 1

    def test_skip_resets_streak(self, client, db):
        user = make_user(db)
        seed_questions(db)
        s = _start(client, user.id).json()
        sid, q = s["session_id"], s["question"]
        # Build a streak first
        correct = f"answer{q['difficulty']}"
        r1 = _answer(client, sid, user.id, q["id"], correct).json()
        next_q = r1.get("next_question")
        if next_q:
            res = client.post(f"/sessions/{sid}/skip",
                              params={"user_id": user.id, "question_id": next_q["id"]})
            assert res.json()["streak"] == 0


# ── Finish endpoint ───────────────────────────────────────────────────────────

class TestFinish:
    def test_finish_returns_session_stats(self, client, db):
        user = make_user(db)
        seed_questions(db)
        s = _start(client, user.id).json()
        sid = s["session_id"]
        res = client.post(f"/sessions/{sid}/finish",
                          params={"user_id": user.id})
        assert res.status_code == 200
        data = res.json()
        assert data["session_id"] == sid
        assert "questions_answered" in data
        assert "correct_count" in data
        assert "topics_to_review" in data

    def test_finish_topics_from_wrong_answers(self, client, db):
        user = make_user(db)
        seed_questions(db)
        s = _start(client, user.id).json()
        sid, q = s["session_id"], s["question"]
        # Answer wrong so a topic gets flagged
        _answer(client, sid, user.id, q["id"], "wrong")
        res = client.post(f"/sessions/{sid}/finish",
                          params={"user_id": user.id})
        data = res.json()
        assert len(data["topics_to_review"]) > 0
        assert q["topic"] in data["topics_to_review"]

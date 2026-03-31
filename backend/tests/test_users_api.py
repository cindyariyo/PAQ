"""
Integration tests for /users endpoints.
"""
import pytest
from datetime import datetime
from tests.conftest import make_user, seed_questions, make_completed_session, make_question
from app.models import Attempt


# ── GET /users/{id}/profile ───────────────────────────────────────────────────

class TestGetProfile:
    def test_returns_correct_session_count(self, client, db):
        user = make_user(db)
        make_completed_session(db, user.id, session_number=1)
        make_completed_session(db, user.id, session_number=2)
        res = client.get(f"/users/{user.id}/profile")
        assert res.status_code == 200
        assert res.json()["total_sessions"] == 2

    def test_total_xp_sums_across_sessions(self, client, db):
        user = make_user(db)
        # xp = questions_answered * 25 in make_completed_session
        make_completed_session(db, user.id, session_number=1, questions_answered=4)
        make_completed_session(db, user.id, session_number=2, questions_answered=6)
        res = client.get(f"/users/{user.id}/profile")
        assert res.json()["total_xp"] == (4 + 6) * 25

    def test_overall_accuracy_calculated_correctly(self, client, db):
        user = make_user(db)
        # 6 first_attempt_correct out of 10 answered = 60%
        make_completed_session(db, user.id, session_number=1,
                               questions_answered=10, first_attempt_correct=6)
        res = client.get(f"/users/{user.id}/profile")
        assert res.json()["overall_accuracy"] == 60

    def test_zero_sessions_returns_zero_accuracy(self, client, db):
        user = make_user(db)
        res = client.get(f"/users/{user.id}/profile")
        assert res.status_code == 200
        assert res.json()["overall_accuracy"] == 0
        assert res.json()["total_xp"] == 0

    def test_unknown_user_returns_404(self, client):
        res = client.get("/users/9999/profile")
        assert res.status_code == 404

    def test_sessions_listed_in_order(self, client, db):
        user = make_user(db)
        make_completed_session(db, user.id, session_number=2)
        make_completed_session(db, user.id, session_number=1)
        sessions = client.get(f"/users/{user.id}/profile").json()["sessions"]
        numbers = [s["session_number"] for s in sessions]
        assert numbers == sorted(numbers)


# ── GET /users/{id}/study_summary ────────────────────────────────────────────

class TestStudySummary:
    def test_no_sessions_returns_not_complete(self, client, db):
        user = make_user(db)
        res = client.get(f"/users/{user.id}/study_summary")
        assert res.status_code == 200
        data = res.json()
        assert data["complete"] is False
        assert data["sessions_done"] == 0
        assert data["topics_to_review"] == []

    def test_five_sessions_not_complete(self, client, db):
        user = make_user(db)
        for i in range(5):
            make_completed_session(db, user.id, session_number=i + 1)
        data = client.get(f"/users/{user.id}/study_summary").json()
        assert data["complete"] is False
        assert data["sessions_done"] == 5

    def test_six_sessions_complete(self, client, db):
        user = make_user(db)
        for i in range(6):
            make_completed_session(db, user.id, session_number=i + 1)
        data = client.get(f"/users/{user.id}/study_summary").json()
        assert data["complete"] is True
        assert data["sessions_done"] == 6

    def test_topics_to_review_from_wrong_attempts(self, client, db):
        user = make_user(db)
        seed_questions(db)
        s = make_completed_session(db, user.id, session_number=1)
        # Record a wrong attempt so a topic appears in review
        q = db.query(__import__("app.models", fromlist=["Question"]).Question).first()
        db.add(Attempt(
            session_id=s.id,
            question_id=q.id,
            answered_at=datetime.utcnow(),
            answer="wrong",
            correct=False,
            retry_count=0,
            hint_level_shown=0,
            time_spent_seconds=10,
            skipped=False,
        ))
        db.commit()
        data = client.get(f"/users/{user.id}/study_summary").json()
        assert q.topic in data["topics_to_review"]

    def test_topics_deduplicated_across_sessions(self, client, db):
        user = make_user(db)
        q = make_question(db, difficulty=1, topic="Loops")
        # Two sessions, both with wrong attempts on the same topic
        for num in range(1, 3):
            s = make_completed_session(db, user.id, session_number=num)
            db.add(Attempt(
                session_id=s.id,
                question_id=q.id,
                answered_at=datetime.utcnow(),
                answer="wrong",
                correct=False,
                retry_count=0,
                hint_level_shown=0,
                time_spent_seconds=10,
                skipped=False,
            ))
        db.commit()
        data = client.get(f"/users/{user.id}/study_summary").json()
        assert data["topics_to_review"].count("Loops") == 1

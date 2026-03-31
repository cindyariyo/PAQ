"""
Shared fixtures for all tests.
Uses an in-memory SQLite DB — fully isolated per test session.
"""
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db import Base, get_db
from app.models import User, UserProfile, Question, Session as QuizSession

TEST_DB_URL = "sqlite:///:memory:"

# StaticPool ensures all connections (reset_db fixture + override_get_db) share
# the same in-memory database instance.
engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def reset_db():
    """Drop and recreate all tables before each test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def client():
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Helpers ──────────────────────────────────────────────────────────────

def make_user(db, study_code="TEST01", hexad_type="Achiever", display_name="Tester"):
    user = User(study_code=study_code, display_name=display_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    profile = UserProfile(user_id=user.id, hexad_type=hexad_type, settings_json="{}")
    db.add(profile)
    db.commit()
    return user


def make_question(db, difficulty=1, topic="Java Basics",
                  prompt="What is 1+1?",
                  options=None, correct="2"):
    if options is None:
        options = ["2", "3", "4", "5"]
    q = Question(
        topic=topic,
        difficulty=difficulty,
        prompt=prompt,
        options_json=json.dumps(options),
        correct_answer=correct,
        hint_1="Think carefully.",
        hint_2="It is less than 3.",
        explanation="1+1=2.",
    )
    db.add(q)
    db.commit()
    db.refresh(q)
    return q


def seed_questions(db):
    """One question per difficulty level."""
    questions = []
    for diff in range(1, 6):
        q = make_question(db, difficulty=diff,
                          topic=f"Topic{diff}",
                          prompt=f"Question at level {diff}?",
                          correct=f"answer{diff}",
                          options=[f"answer{diff}", "wrong1", "wrong2", "wrong3"])
        questions.append(q)
    return questions


def make_completed_session(db, user_id, session_number=1, difficulty=1,
                           questions_answered=7, correct_count=5,
                           first_attempt_correct=4):
    from datetime import datetime
    s = QuizSession(
        user_id=user_id,
        session_number=session_number,
        difficulty_level_used=difficulty,
        starting_difficulty=difficulty,
        completed=True,
        questions_answered=questions_answered,
        correct_count=correct_count,
        first_attempt_correct=first_attempt_correct,
        xp=questions_answered * 25,
        streak=0,
        strong_correct_streak=0,
        started_at=datetime.utcnow(),
        ended_at=datetime.utcnow(),
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s

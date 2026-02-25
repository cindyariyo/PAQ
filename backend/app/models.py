from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base



class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    study_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    profile: Mapped["UserProfile"] = relationship(back_populates="user", uselist=False)
    sessions: Mapped[list["Session"]] = relationship(back_populates="user")


class UserProfile(Base):
    __tablename__ = "user_profiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)

    hexad_type: Mapped[str] = mapped_column(String(32), default="Unknown")
    onboarding_answers_json: Mapped[str] = mapped_column(Text, default="{}")
    settings_json: Mapped[str] = mapped_column(Text, default="{}")

    user: Mapped["User"] = relationship(back_populates="profile")


class Question(Base):
    __tablename__ = "questions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic: Mapped[str] = mapped_column(String(64))
    difficulty: Mapped[int] = mapped_column(Integer)  # 1..3

    prompt: Mapped[str] = mapped_column(Text)
    options_json: Mapped[str] = mapped_column(Text, default="[]")
    correct_answer: Mapped[str] = mapped_column(String(256))

    hint_1: Mapped[str] = mapped_column(Text, default="")
    hint_2: Mapped[str] = mapped_column(Text, default="")
    explanation: Mapped[str] = mapped_column(Text, default="")


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    session_number: Mapped[int] = mapped_column(Integer, default=1)
    difficulty_level_used: Mapped[int] = mapped_column(Integer, default=1)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)

    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="sessions")
    attempts: Mapped[list["Attempt"]] = relationship(back_populates="session")
    questionnaire: Mapped["QuestionnaireResponse"] = relationship(back_populates="session", uselist=False)
    
        # --- gamification + adaptation state ---
    questions_answered: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)

    xp: Mapped[int] = mapped_column(Integer, default=0)
    streak: Mapped[int] = mapped_column(Integer, default=0)

    strong_correct_streak: Mapped[int] = mapped_column(Integer, default=0)
    used_hint_this_session: Mapped[bool] = mapped_column(Boolean, default=False)



class Attempt(Base):
    __tablename__ = "attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"))
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))

    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    answer: Mapped[str] = mapped_column(Text, default="")
    correct: Mapped[bool] = mapped_column(Boolean, default=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    hint_level_shown: Mapped[int] = mapped_column(Integer, default=0)
    time_spent_seconds: Mapped[int] = mapped_column(Integer, default=0)

    session: Mapped["Session"] = relationship(back_populates="attempts")


class QuestionnaireResponse(Base):
    __tablename__ = "questionnaire_responses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), unique=True)

    enjoyment: Mapped[int] = mapped_column(Integer)
    frustration: Mapped[int] = mapped_column(Integer)
    effort: Mapped[int] = mapped_column(Integer)
    free_text: Mapped[str] = mapped_column(Text, default="")

    session: Mapped["Session"] = relationship(back_populates="questionnaire")

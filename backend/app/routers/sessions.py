import json
import random
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..db import get_db
from ..models import UserProfile, Session as QuizSession, Question, Attempt, QuestionnaireResponse, UserQuestionState
from ..schemas import (
    StartSessionIn, StartSessionOut, QuestionOut,
    AnswerIn, AnswerOut, HintOut, FinishOut, QuestionnaireIn
)
from ..services.adaptation import hint_level_from_rules, update_difficulty
from ..services.cross_session_adaptation import adapt_cross_session

router = APIRouter(prefix="/sessions", tags=["sessions"])

def _session_total(difficulty_level: int) -> int:
    """10 for levels 1-3, 7 for level 4, 5 for level 5."""
    if difficulty_level >= 5: return 5
    if difficulty_level == 4: return 7
    return 10

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _question_to_out(q: Question) -> QuestionOut:
    options = json.loads(q.options_json or "[]")
    random.shuffle(options)
    return QuestionOut(id=q.id, topic=q.topic, difficulty=q.difficulty,
                       prompt=q.prompt, options=options)

def _get_profile(db: Session, user_id: int) -> UserProfile:
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="User profile not found")
    return profile

def _get_excluded_ids(db: Session, user_id: int) -> set:
    """Questions not to pick again: correctly answered OR seen (wrong but not skipped)."""
    rows = db.query(UserQuestionState.question_id).filter(
        UserQuestionState.user_id == user_id,
        UserQuestionState.status.in_(["correct", "seen"])
    ).all()
    return {r[0] for r in rows}

def _get_retry_ids(db: Session, user_id: int) -> list:
    rows = db.query(UserQuestionState.question_id).filter(
        UserQuestionState.user_id == user_id,
        UserQuestionState.status == "retry"
    ).all()
    return [r[0] for r in rows]

def _pick_question(db: Session, difficulty_level: int, user_id: int, exclude_ids: set):
    """
    Priority:
    1. Retry questions (wrong last session) at this difficulty
    2. Unseen questions at this difficulty
    3. Fallback: any unseen question at any difficulty
    """
    retry_ids      = set(_get_retry_ids(db, user_id))
    fully_excluded = _get_excluded_ids(db, user_id) | exclude_ids

    # 1. Retry at this level
    q = (db.query(Question)
         .filter(Question.difficulty == difficulty_level,
                 Question.id.in_(retry_ids),
                 Question.id.notin_(fully_excluded))
         .order_by(func.random()).first())
    if q: return q

    # 2. Unseen at this level
    q = (db.query(Question)
         .filter(Question.difficulty == difficulty_level,
                 Question.id.notin_(fully_excluded))
         .order_by(func.random()).first())
    if q: return q

    # 3. Any unseen
    return (db.query(Question)
            .filter(Question.id.notin_(fully_excluded))
            .order_by(func.random()).first())

def _mark_correct(db: Session, user_id: int, question_id: int):
    state = db.query(UserQuestionState).filter(
        UserQuestionState.user_id == user_id,
        UserQuestionState.question_id == question_id).first()
    if state:
        state.status = "correct"; state.updated_at = datetime.utcnow()
    else:
        db.add(UserQuestionState(user_id=user_id, question_id=question_id, status="correct"))

def _mark_retry(db: Session, user_id: int, question_id: int):
    state = db.query(UserQuestionState).filter(
        UserQuestionState.user_id == user_id,
        UserQuestionState.question_id == question_id).first()
    if state:
        if state.status != "correct":
            state.status = "retry"; state.updated_at = datetime.utcnow()
    else:
        db.add(UserQuestionState(user_id=user_id, question_id=question_id, status="retry"))

def _mark_seen(db: Session, user_id: int, question_id: int):
    """Wrong answer, not skipped — exclude from future sessions but don't requeue."""
    state = db.query(UserQuestionState).filter(
        UserQuestionState.user_id == user_id,
        UserQuestionState.question_id == question_id).first()
    if state:
        if state.status not in ("correct", "retry"):
            state.status = "seen"; state.updated_at = datetime.utcnow()
    else:
        db.add(UserQuestionState(user_id=user_id, question_id=question_id, status="seen"))

def _hexad_prefix(hexad: str) -> str:
    return {
        "Achiever":       "🏁 Progress tip:",
        "Player":         "🎁 Reward hint:",
        "Socialiser":     "👥 Community hint:",
        "Free Spirit":    "🧭 Optional hint:",
        "Philanthropist": "💡 Helpful nudge:",
        "Disruptor":      "🛠 Alternative route:",
        "Unknown":        "💡 Hint:",
    }.get((hexad or "Unknown").strip(), "💡 Hint:")

def _feedback_message(hexad: str, correct: bool, xp_delta: int, streak: int) -> str:
    hexad = (hexad or "Unknown").strip()
    if correct:
        return {
            "Player":         f"✅ Nice! +{xp_delta} XP. Streak: {streak} 🔥",
            "Achiever":       f"✅ Correct! mastery up. Streak: {streak} 🔥",
            "Socialiser":     f"✅ Correct! keep going! Streak: {streak} 🔥",
            "Free Spirit":    f"✅ Correct! nice approach! Streak: {streak} 🔥",
            "Philanthropist": f"✅ Correct! steady improvement. Streak: {streak} 🔥",
            "Disruptor":      f"✅ Correct! you broke it down well. Streak: {streak} 🔥",
        }.get(hexad, f"✅ Correct! +{xp_delta} XP. Streak: {streak} 🔥")
    return {
        "Player":         "❌ Not yet...try again. You can still earn XP on the next one.",
        "Achiever":       "❌ Not yet...review the pattern and reattempt.",
        "Socialiser":     "❌ Not yet...lots of learners miss this one the first time.",
        "Free Spirit":    "❌ Not yet...try a different approach.",
        "Philanthropist": "❌ Not yet...use a hint if it helps.",
        "Disruptor":      "❌ Not yet...break the problem and test an edge case.",
    }.get(hexad, "❌ Not yet...try again.")

def _session_floor(starting_difficulty: int) -> int:
    """
    The lowest difficulty allowed during this session.
    User can drop at most 1 level below where they started,
    but never below 1.
    """
    return max(1, starting_difficulty - 1)

# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────

@router.post("/start", response_model=StartSessionOut)
def start_session(payload: StartSessionIn, db: Session = Depends(get_db)):
    profile  = _get_profile(db, payload.user_id)
    base_settings = json.loads(profile.settings_json or "{}")

    # ── Carry forward difficulty from last completed session ──
    last = (
        db.query(QuizSession)
        .filter(QuizSession.user_id == payload.user_id, QuizSession.completed == True)  # noqa
        .order_by(QuizSession.id.desc())
        .first()
    )
    starting_difficulty = max(1, min(5, last.difficulty_level_used)) if last else 1

    # ── Cross-session adaptation ──
    last_qr = (
        db.query(QuestionnaireResponse)
        .filter(QuestionnaireResponse.session_id == last.id)
        .first()
    ) if last else None
    settings = adapt_cross_session(last, last_qr, base_settings, profile.hexad_type)

    # Apply difficulty_offset (clamp to 1-5)
    offset = settings.get("difficulty_offset", 0)
    starting_difficulty = max(1, min(5, starting_difficulty + offset))

    # Persist adapted settings back to profile
    profile.settings_json = json.dumps(settings)
    db.add(profile)

    prior   = db.query(QuizSession).filter(QuizSession.user_id == payload.user_id, QuizSession.completed == True).count()  # noqa
    session = QuizSession(
        user_id=payload.user_id,
        session_number=prior + 1,
        difficulty_level_used=starting_difficulty,
        starting_difficulty=starting_difficulty,
        completed=False,
        questions_answered=0, correct_count=0,
        xp=0, streak=0, strong_correct_streak=0,
        used_hint_this_session=False,
    )
    db.add(session); db.commit(); db.refresh(session)

    q = _pick_question(db, starting_difficulty, payload.user_id, set())
    if not q:
        raise HTTPException(status_code=500, detail="No questions available")

    return StartSessionOut(
        session_id=session.id,
        session_number=session.session_number,
        difficulty_level=starting_difficulty,
        hexad_type=profile.hexad_type,
        settings=settings,
        question=_question_to_out(q),
        xp=0, streak=0, questions_answered=0, correct_count=0,
        session_total_questions=_session_total(starting_difficulty),
    )


@router.post("/{session_id}/hint", response_model=HintOut)
def get_hint(session_id: int, user_id: int, question_id: int,
             time_spent_seconds: int, retry_count: int, current_hint_level: int = 0,
             db: Session = Depends(get_db)):
    profile = _get_profile(db, user_id)
    q = db.query(Question).filter(Question.id == question_id).first()
    if not q: raise HTTPException(status_code=404, detail="Question not found")
    level  = max(1, hint_level_from_rules(time_spent_seconds, retry_count, current_hint_level))
    prefix = _hexad_prefix(profile.hexad_type)
    if level == 1:
        return HintOut(hint_level=1,
                       hint_text=f"{prefix} {(q.hint_1 or '').strip() or 'Try breaking the problem into smaller steps.'}")
    return HintOut(hint_level=2,
                   hint_text=f"{prefix} {(q.hint_2 or '').strip() or 'Trace a small example step-by-step.'}")


@router.post("/{session_id}/answer", response_model=AnswerOut)
def answer(session_id: int, payload: AnswerIn, db: Session = Depends(get_db)):
    session = db.query(QuizSession).filter(
        QuizSession.id == session_id, QuizSession.user_id == payload.user_id).first()
    if not session: raise HTTPException(status_code=404, detail="Session not found")

    profile = _get_profile(db, payload.user_id)
    q = db.query(Question).filter(Question.id == payload.question_id).first()
    if not q: raise HTTPException(status_code=404, detail="Question not found")

    correct    = payload.answer.strip() == q.correct_answer.strip()
    used_hints = payload.hint_level_shown > 0
    if used_hints: session.used_hint_this_session = True

    db.add(Attempt(
        session_id=session.id, question_id=q.id,
        answered_at=datetime.utcnow(), answer=payload.answer,
        correct=correct, retry_count=payload.retry_count,
        hint_level_shown=payload.hint_level_shown,
        time_spent_seconds=payload.time_spent_seconds, skipped=False,
    ))

    if correct: _mark_correct(db, payload.user_id, q.id)
    else:       _mark_seen(db, payload.user_id, q.id)

    settings     = json.loads(profile.settings_json or "{}")
    xp_mult      = float(settings.get("xp_multiplier", 1.0))
    effort_xp    = bool(settings.get("effort_xp", False))
    streak_shield= bool(settings.get("streak_shield", False))

    xp_delta = 5
    if effort_xp:
        xp_delta += 5  # bonus for trying hard regardless of correctness
    if correct:
        session.questions_answered += 1
        session.correct_count += 1
        session.streak += 1
        xp_delta += 20
        if payload.retry_count == 0:
            session.first_attempt_correct += 1
    else:
        if streak_shield and session.streak > 0:
            # One-time shield: absorb the streak break
            settings["streak_shield_active"] = False
            settings["streak_shield"] = False   # consume the shield
            profile.settings_json = json.dumps(settings)
            db.add(profile)
            # streak stays intact
        else:
            session.streak = 0
    xp_delta = round(xp_delta * xp_mult)
    session.xp += xp_delta

    # ── Difficulty update — floor = starting_difficulty - 1 (min 1) ──
    floor = max(1, session.starting_difficulty - 1)
    new_level, diff_msg = update_difficulty(
        session,
        correct=correct,
        time_spent=payload.time_spent_seconds,
        retries=payload.retry_count,
        used_hint=used_hints,
        hexad=profile.hexad_type,
        session_floor=floor,
        difficulty_level=session.difficulty_level_used,
    )
    session.difficulty_level_used = new_level
    db.commit()

    session_total = _session_total(session.starting_difficulty)
    seen_ids = {a.question_id for a in db.query(Attempt).filter(Attempt.session_id == session.id).all()}
    next_q   = _pick_question(db, new_level, payload.user_id, seen_ids) \
               if session.questions_answered < session_total else None

    # When session ends, collect any skipped questions for the bonus round
    skipped_qs = []
    if next_q is None:
        skipped_attempts = db.query(Attempt).filter(
            Attempt.session_id == session.id, Attempt.skipped == True  # noqa
        ).all()
        skipped_qs = [_question_to_out(db.query(Question).filter(Question.id == a.question_id).first())
                      for a in skipped_attempts
                      if db.query(Question).filter(Question.id == a.question_id).first()]

    return AnswerOut(
        correct=correct,
        explanation=q.explanation or ("Correct!" if correct else "Not quite...review and try again."),
        next_question=_question_to_out(next_q) if next_q else None,
        updated_difficulty_level=new_level, difficulty_message=diff_msg,
        feedback_message=_feedback_message(profile.hexad_type, correct, xp_delta, session.streak),
        xp=session.xp, streak=session.streak,
        questions_answered=session.questions_answered,
        correct_count=session.correct_count,
        session_total_questions=session_total,
        skipped_questions=skipped_qs,
    )



@router.post("/{session_id}/skip")
def skip_question(session_id: int, user_id: int, question_id: int, db: Session = Depends(get_db)):
    """Triggered when user hits 2 wrong attempts + hint used. Re-queues for next session."""
    session = db.query(QuizSession).filter(
        QuizSession.id == session_id, QuizSession.user_id == user_id).first()
    if not session: raise HTTPException(status_code=404, detail="Session not found")
    q = db.query(Question).filter(Question.id == question_id).first()
    if not q: raise HTTPException(status_code=404, detail="Question not found")

    _mark_retry(db, user_id, question_id)
    db.add(Attempt(
        session_id=session.id, question_id=question_id,
        answered_at=datetime.utcnow(), answer="__skipped__",
        correct=False, retry_count=2, hint_level_shown=2,
        time_spent_seconds=0, skipped=True,
    ))
    session.questions_answered += 1
    session.streak = 0
    session.strong_correct_streak = 0
    # Decrease difficulty on skip — respecting session floor
    floor = max(1, (session.starting_difficulty or session.difficulty_level_used) - 1)
    if session.difficulty_level_used > floor:
        session.difficulty_level_used -= 1
    db.commit()

    session_total = _session_total(session.starting_difficulty)
    seen_ids = {a.question_id for a in db.query(Attempt).filter(Attempt.session_id == session.id).all()}
    next_q   = _pick_question(db, session.difficulty_level_used, user_id, seen_ids) \
               if session.questions_answered < session_total else None

    skipped_qs = []
    if next_q is None:
        skipped_attempts = db.query(Attempt).filter(
            Attempt.session_id == session.id, Attempt.skipped == True  # noqa
        ).all()
        skipped_qs = [_question_to_out(db.query(Question).filter(Question.id == a.question_id).first())
                      for a in skipped_attempts
                      if db.query(Question).filter(Question.id == a.question_id).first()]

    return {
        "skipped": True,
        "next_question": _question_to_out(next_q) if next_q else None,
        "questions_answered": session.questions_answered,
        "session_total_questions": session_total,
        "updated_difficulty_level": session.difficulty_level_used,
        "xp": session.xp,
        "streak": session.streak,
        "skipped_questions": [q.model_dump() for q in skipped_qs],
    }


@router.post("/{session_id}/finish", response_model=FinishOut)
def finish(session_id: int, user_id: int, db: Session = Depends(get_db)):
    session = db.query(QuizSession).filter(
        QuizSession.id == session_id, QuizSession.user_id == user_id).first()
    if not session: raise HTTPException(status_code=404, detail="Session not found")
    session.completed = True; session.ended_at = datetime.utcnow()
    db.commit()

    # Topics where user struggled (wrong or skipped) this session
    bad_attempts = (
        db.query(Attempt).join(Question, Attempt.question_id == Question.id)
        .filter(Attempt.session_id == session_id, Attempt.correct == False)  # noqa
        .all()
    )
    seen_topics: list[str] = []
    for a in bad_attempts:
        q = db.query(Question).filter(Question.id == a.question_id).first()
        if q and q.topic not in seen_topics:
            seen_topics.append(q.topic)

    return FinishOut(
        session_id=session.id,
        questions_answered=session.questions_answered,
        correct_count=session.correct_count,
        first_attempt_correct=session.first_attempt_correct,
        topics_to_review=seen_topics,
    )


@router.post("/{session_id}/questionnaire")
def submit_questionnaire(session_id: int, user_id: int, payload: QuestionnaireIn,
                         db: Session = Depends(get_db)):
    session = db.query(QuizSession).filter(
        QuizSession.id == session_id, QuizSession.user_id == user_id).first()
    if not session: raise HTTPException(status_code=404, detail="Session not found")
    if db.query(QuestionnaireResponse).filter(
            QuestionnaireResponse.session_id == session.id).first():
        raise HTTPException(status_code=400, detail="Questionnaire already submitted")
    db.add(QuestionnaireResponse(
        session_id=session.id, enjoyment=payload.enjoyment,
        frustration=payload.frustration, effort=payload.effort,
        focused=payload.focused, challenge=payload.challenge,
        recovered=payload.recovered, hints_helped=payload.hints_helped,
        satisfied=payload.satisfied, motivated=payload.motivated,
        favourite_features=payload.favourite_features,
        free_text=payload.free_text,
    ))
    db.commit()
    return {"ok": True}
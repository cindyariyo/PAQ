# import json
# from datetime import datetime
# from fastapi import APIRouter, Depends, HTTPException
# from sqlalchemy.orm import Session
# from sqlalchemy import func

# from ..db import get_db
# from ..models import UserProfile, Session as QuizSession, Question, Attempt, QuestionnaireResponse
# from ..schemas import (
#     StartSessionIn, StartSessionOut, QuestionOut,
#     AnswerIn, AnswerOut, HintOut, FinishOut, QuestionnaireIn
# )
# from ..services.adaptation import hint_level_from_rules, update_difficulty

# router = APIRouter(prefix="/sessions", tags=["sessions"])

# def _question_to_out(q: Question) -> QuestionOut:
#     return QuestionOut(
#         id=q.id,
#         topic=q.topic,
#         difficulty=q.difficulty,
#         prompt=q.prompt,
#         options=json.loads(q.options_json or "[]"),
#     )

# def _get_profile(db: Session, user_id: int) -> UserProfile:
#     profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
#     if not profile:
#         raise HTTPException(status_code=404, detail="User profile not found")
#     return profile

# def _pick_question(db: Session, difficulty_level: int) -> Question:
#     # MVP: pick a random question at that difficulty
#     q = db.query(Question).filter(Question.difficulty == difficulty_level).order_by(func.random()).first()
#     if not q:
#         # fallback: any question
#         q = db.query(Question).order_by(func.random()).first()
#     if not q:
#         raise HTTPException(status_code=500, detail="No questions in database")
#     return q

# @router.post("/start", response_model=StartSessionOut)
# def start_session(payload: StartSessionIn, db: Session = Depends(get_db)):
#     profile = _get_profile(db, payload.user_id)
#     settings = json.loads(profile.settings_json or "{}")

#     # session_number = count prior sessions + 1
#     prior = db.query(QuizSession).filter(QuizSession.user_id == payload.user_id).count()
#     session = QuizSession(
#         user_id=payload.user_id,
#         session_number=prior + 1,
#         difficulty_level_used=1,
#         completed=False
#     )
#     db.add(session)
#     db.commit()
#     db.refresh(session)

#     q = _pick_question(db, session.difficulty_level_used)
#     return StartSessionOut(
#         session_id=session.id,
#         difficulty_level=session.difficulty_level_used,
#         hexad_type=profile.hexad_type,
#         settings=settings,
#         question=_question_to_out(q),
#     )

# @router.post("/{session_id}/hint", response_model=HintOut)
# def get_hint(
#     session_id: int,
#     user_id: int,
#     question_id: int,
#     time_spent_seconds: int,
#     retry_count: int,
#     current_hint_level: int = 0,
#     db: Session = Depends(get_db),
# ):
#     profile = _get_profile(db, user_id)
#     settings = json.loads(profile.settings_json or "{}")

#     q = db.query(Question).filter(Question.id == question_id).first()
#     if not q:
#         raise HTTPException(status_code=404, detail="Question not found")

#     # 1) Compute level from rules (45s/75s + retries) using your service
#     target_level = hint_level_from_rules(time_spent_seconds, retry_count, current_hint_level)

#     # 2) If user clicked Hint, ALWAYS give at least hint 1
#     # (Design expectation: hint request should help immediately.)
#     target_level = max(1, target_level)

#     # 3) Free Spirit: auto-hints may be disabled, but user explicitly asked, so still allow
#     # (No special casing needed now because we force >= 1)

#     # 4) Hexad-framed prefix message (short + game-like)
#     # Keep these short so the UI can display them like a "toast"
#     hexad = (profile.hexad_type or "Unknown").strip()

#     prefix_by_hexad = {
#         "Achiever": "🔎 Strategy tip:",
#         "Player": "🎁 Hint unlocked:",
#         "Socialiser": "👥 Many learners use this hint:",
#         "Free Spirit": "🧭 Optional hint (use if you want):",
#         "Philanthropist": "💡 Helpful nudge:",
#         "Disruptor": "🛠 Try this alternative approach:",
#         "Unknown": "💡 Hint:",
#     }
#     prefix = prefix_by_hexad.get(hexad, "💡 Hint:")

#     # 5) Pick the actual hint text from DB
#     if target_level == 1:
#         base_hint = q.hint_1.strip() if (q.hint_1 or "").strip() else "Try breaking the problem into smaller steps."
#         return HintOut(hint_level=1, hint_text=f"{prefix} {base_hint}")

#     # target_level >= 2
#     base_hint = q.hint_2.strip() if (q.hint_2 or "").strip() else "Trace a small example step-by-step."
#     return HintOut(hint_level=2, hint_text=f"{prefix} {base_hint}")


# @router.post("/{session_id}/answer", response_model=AnswerOut)
# def answer(session_id: int, payload: AnswerIn, db: Session = Depends(get_db)):
#     session = db.query(QuizSession).filter(QuizSession.id == session_id, QuizSession.user_id == payload.user_id).first()
#     if not session:
#         raise HTTPException(status_code=404, detail="Session not found")

#     q = db.query(Question).filter(Question.id == payload.question_id).first()
#     if not q:
#         raise HTTPException(status_code=404, detail="Question not found")

#     correct = payload.answer.strip().lower() == q.correct_answer.strip().lower()
#     used_hints = payload.hint_level_shown > 0

#     attempt = Attempt(
#         session_id=session.id,
#         question_id=q.id,
#         answered_at=datetime.utcnow(),
#         answer=payload.answer,
#         correct=correct,
#         retry_count=payload.retry_count,
#         hint_level_shown=payload.hint_level_shown,
#         time_spent_seconds=payload.time_spent_seconds,
#     )
#     db.add(attempt)

#     # update difficulty
#     new_level = update_difficulty(
#         current_level=session.difficulty_level_used,
#         last_correct=correct,
#         time_spent=payload.time_spent_seconds,
#         retry_count=payload.retry_count,
#         used_hints=used_hints,
#     )
#     session.difficulty_level_used = new_level

#     db.commit()

#     # For demo: serve a next question unless session already has 5 attempts
#     attempt_count = db.query(Attempt).filter(Attempt.session_id == session.id).count()
#     next_q = None
#     if attempt_count < 5:
#         next_q = _pick_question(db, new_level)

#     return AnswerOut(
#         correct=correct,
#         explanation=q.explanation or ("Correct!" if correct else "Not quite — review the concept and try again."),
#         next_question=_question_to_out(next_q) if next_q else None,
#         updated_difficulty_level=new_level,
#     )

# @router.post("/{session_id}/finish", response_model=FinishOut)
# def finish(session_id: int, user_id: int, db: Session = Depends(get_db)):
#     session = db.query(QuizSession).filter(QuizSession.id == session_id, QuizSession.user_id == user_id).first()
#     if not session:
#         raise HTTPException(status_code=404, detail="Session not found")

#     session.completed = True
#     session.ended_at = datetime.utcnow()

#     total = db.query(Attempt).filter(Attempt.session_id == session.id).count()
#     correct = db.query(Attempt).filter(Attempt.session_id == session.id, Attempt.correct == True).count()  # noqa

#     db.commit()
#     return FinishOut(session_id=session.id, total_questions=total, correct_count=correct)

# @router.post("/{session_id}/questionnaire")
# def submit_questionnaire(session_id: int, user_id: int, payload: QuestionnaireIn, db: Session = Depends(get_db)):
#     session = db.query(QuizSession).filter(QuizSession.id == session_id, QuizSession.user_id == user_id).first()
#     if not session:
#         raise HTTPException(status_code=404, detail="Session not found")

#     existing = db.query(QuestionnaireResponse).filter(QuestionnaireResponse.session_id == session.id).first()
#     if existing:
#         raise HTTPException(status_code=400, detail="Questionnaire already submitted")

#     resp = QuestionnaireResponse(
#         session_id=session.id,
#         enjoyment=payload.enjoyment,
#         frustration=payload.frustration,
#         effort=payload.effort,
#         free_text=payload.free_text,
#     )
#     db.add(resp)
#     db.commit()
#     return {"ok": True}


import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..db import get_db
from ..models import UserProfile, Session as QuizSession, Question, Attempt, QuestionnaireResponse
from ..schemas import (
    StartSessionIn, StartSessionOut, QuestionOut,
    AnswerIn, AnswerOut, HintOut, FinishOut, QuestionnaireIn
)
from ..services.adaptation import hint_level_from_rules

router = APIRouter(prefix="/sessions", tags=["sessions"])

SESSION_TOTAL_QUESTIONS = 7

# ---------------- helpers ----------------

def _question_to_out(q: Question) -> QuestionOut:
    return QuestionOut(
        id=q.id,
        topic=q.topic,
        difficulty=q.difficulty,
        prompt=q.prompt,
        options=json.loads(q.options_json or "[]"),
    )

def _get_profile(db: Session, user_id: int) -> UserProfile:
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="User profile not found")
    return profile

def _pick_question(db: Session, difficulty_level: int) -> Question:
    q = (
        db.query(Question)
        .filter(Question.difficulty == difficulty_level)
        .order_by(func.random())
        .first()
    )
    if not q:
        q = db.query(Question).order_by(func.random()).first()
    if not q:
        raise HTTPException(status_code=500, detail="No questions in database")
    return q

def _hexad_prefix(hexad: str) -> str:
    hexad = (hexad or "Unknown").strip()
    return {
        "Achiever": "🏁 Progress tip:",
        "Player": "🎁 Reward hint:",
        "Socialiser": "👥 Community hint:",
        "Free Spirit": "🧭 Optional hint:",
        "Philanthropist": "💡 Helpful nudge:",
        "Disruptor": "🛠 Alternative route:",
        "Unknown": "💡 Hint:",
    }.get(hexad, "💡 Hint:")

def _feedback_message(hexad: str, correct: bool, xp_delta: int, streak: int) -> str:
    hexad = (hexad or "Unknown").strip()

    if correct:
        if hexad == "Player":
            return f"✅ Nice! +{xp_delta} XP. Streak: {streak} 🔥"
        if hexad == "Achiever":
            return f"✅ Correct — mastery up. Streak: {streak} 🔥"
        if hexad == "Socialiser":
            return f"✅ Correct — keep going! Streak: {streak} 🔥"
        if hexad == "Free Spirit":
            return f"✅ Correct — your approach works. Streak: {streak} 🔥"
        if hexad == "Philanthropist":
            return f"✅ Correct — steady improvement. Streak: {streak} 🔥"
        if hexad == "Disruptor":
            return f"✅ Correct — you broke it down well. Streak: {streak} 🔥"
        return f"✅ Correct! +{xp_delta} XP. Streak: {streak} 🔥"

    # incorrect
    if hexad == "Player":
        return "❌ Not yet — try again. You can still earn XP on the next one."
    if hexad == "Achiever":
        return "❌ Not yet — review the pattern and reattempt."
    if hexad == "Socialiser":
        return "❌ Not yet — lots of learners miss this one the first time."
    if hexad == "Free Spirit":
        return "❌ Not yet — try a different approach."
    if hexad == "Philanthropist":
        return "❌ Not yet — you’re learning; use a hint if needed."
    if hexad == "Disruptor":
        return "❌ Not yet — break the problem and test an edge case."
    return "❌ Not yet — try again."

def _update_difficulty(session: QuizSession, *, correct: bool, time_spent: int, retries: int, used_hint: bool, hexad: str):
    """
    Design rules:
    - Decrease if wrong after >=2 retries OR time > 90s
    - Increase if 2 consecutive strong correct (correct + no hints + under 40s)
      - Achiever: increase faster (required streak = 1)
      - Free Spirit: don't force increase; message "optional harder"
    """
    # Decrease
    if ((not correct) and retries >= 2) or (time_spent > 90):
        session.strong_correct_streak = 0
        new_level = max(1, session.difficulty_level_used - 1)
        return new_level, "Difficulty decreased (support mode)."

    strong_correct = correct and (not used_hint) and (time_spent < 40)

    if strong_correct:
        session.strong_correct_streak += 1
    else:
        session.strong_correct_streak = 0

    required = 1 if (hexad == "Achiever") else 2

    if session.strong_correct_streak >= required:
        session.strong_correct_streak = 0

        if hexad == "Free Spirit":
            # Optional harder instead of forced
            return session.difficulty_level_used, "Optional harder question available."

        new_level = min(3, session.difficulty_level_used + 1)
        if new_level > session.difficulty_level_used:
            return new_level, "Difficulty increased!"
        return new_level, "Difficulty unchanged."

    return session.difficulty_level_used, "Difficulty unchanged."

# ---------------- routes ----------------

@router.post("/start", response_model=StartSessionOut)
def start_session(payload: StartSessionIn, db: Session = Depends(get_db)):
    profile = _get_profile(db, payload.user_id)
    settings = json.loads(profile.settings_json or "{}")

    prior = db.query(QuizSession).filter(QuizSession.user_id == payload.user_id).count()
    session = QuizSession(
        user_id=payload.user_id,
        session_number=prior + 1,
        difficulty_level_used=1,
        completed=False,

        # gamification initial state
        questions_answered=0,
        correct_count=0,
        xp=0,
        streak=0,
        strong_correct_streak=0,
        used_hint_this_session=False,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    q = _pick_question(db, session.difficulty_level_used)

    return StartSessionOut(
        session_id=session.id,
        difficulty_level=session.difficulty_level_used,
        hexad_type=profile.hexad_type,
        settings=settings,
        question=_question_to_out(q),

        xp=session.xp,
        streak=session.streak,
        questions_answered=session.questions_answered,
        correct_count=session.correct_count,
        session_total_questions=SESSION_TOTAL_QUESTIONS,
    )

@router.post("/{session_id}/hint", response_model=HintOut)
def get_hint(
    session_id: int,
    user_id: int,
    question_id: int,
    time_spent_seconds: int,
    retry_count: int,
    current_hint_level: int = 0,
    db: Session = Depends(get_db),
):
    profile = _get_profile(db, user_id)

    q = db.query(Question).filter(Question.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")

    # compute from rules, but user clicked => always at least hint 1
    target_level = hint_level_from_rules(time_spent_seconds, retry_count, current_hint_level)
    target_level = max(1, target_level)

    prefix = _hexad_prefix(profile.hexad_type)

    if target_level == 1:
        base_hint = q.hint_1.strip() if (q.hint_1 or "").strip() else "Try breaking the problem into smaller steps."
        return HintOut(hint_level=1, hint_text=f"{prefix} {base_hint}")

    base_hint = q.hint_2.strip() if (q.hint_2 or "").strip() else "Trace a small example step-by-step."
    return HintOut(hint_level=2, hint_text=f"{prefix} {base_hint}")

@router.post("/{session_id}/answer", response_model=AnswerOut)
def answer(session_id: int, payload: AnswerIn, db: Session = Depends(get_db)):
    session = (
        db.query(QuizSession)
        .filter(QuizSession.id == session_id, QuizSession.user_id == payload.user_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    profile = _get_profile(db, payload.user_id)

    q = db.query(Question).filter(Question.id == payload.question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")

    correct = payload.answer.strip().lower() == q.correct_answer.strip().lower()
    used_hints = payload.hint_level_shown > 0

    if used_hints:
        session.used_hint_this_session = True

    # log attempt
    attempt = Attempt(
        session_id=session.id,
        question_id=q.id,
        answered_at=datetime.utcnow(),
        answer=payload.answer,
        correct=correct,
        retry_count=payload.retry_count,
        hint_level_shown=payload.hint_level_shown,
        time_spent_seconds=payload.time_spent_seconds,
    )
    db.add(attempt)

    # update gamification state
    session.questions_answered += 1

    xp_delta = 5  # base participation XP
    if correct:
        session.correct_count += 1
        session.streak += 1
        xp_delta += 20
    else:
        session.streak = 0

    session.xp += xp_delta

    # update difficulty (design rules)
    new_level, difficulty_message = _update_difficulty(
        session,
        correct=correct,
        time_spent=payload.time_spent_seconds,
        retries=payload.retry_count,
        used_hint=used_hints,
        hexad=profile.hexad_type,
    )
    session.difficulty_level_used = new_level

    db.commit()

    # pick next question unless reached session limit
    next_q = None
    if session.questions_answered < SESSION_TOTAL_QUESTIONS:
        next_q = _pick_question(db, new_level)

    feedback_message = _feedback_message(profile.hexad_type, correct, xp_delta, session.streak)

    return AnswerOut(
        correct=correct,
        explanation=q.explanation or ("Correct!" if correct else "Not quite — review the concept and try again."),
        next_question=_question_to_out(next_q) if next_q else None,
        updated_difficulty_level=new_level,

        difficulty_message=difficulty_message,
        feedback_message=feedback_message,
        xp=session.xp,
        streak=session.streak,
        questions_answered=session.questions_answered,
        correct_count=session.correct_count,
        session_total_questions=SESSION_TOTAL_QUESTIONS,
    )

@router.post("/{session_id}/finish", response_model=FinishOut)
def finish(session_id: int, user_id: int, db: Session = Depends(get_db)):
    session = db.query(QuizSession).filter(QuizSession.id == session_id, QuizSession.user_id == user_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.completed = True
    session.ended_at = datetime.utcnow()

    total = db.query(Attempt).filter(Attempt.session_id == session.id).count()
    correct = db.query(Attempt).filter(Attempt.session_id == session.id, Attempt.correct == True).count()  # noqa

    db.commit()
    return FinishOut(session_id=session.id, total_questions=total, correct_count=correct)

@router.post("/{session_id}/questionnaire")
def submit_questionnaire(session_id: int, user_id: int, payload: QuestionnaireIn, db: Session = Depends(get_db)):
    session = db.query(QuizSession).filter(QuizSession.id == session_id, QuizSession.user_id == user_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    existing = db.query(QuestionnaireResponse).filter(QuestionnaireResponse.session_id == session.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Questionnaire already submitted")

    resp = QuestionnaireResponse(
        session_id=session.id,
        enjoyment=payload.enjoyment,
        frustration=payload.frustration,
        effort=payload.effort,
        free_text=payload.free_text,
    )
    db.add(resp)
    db.commit()
    return {"ok": True}

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User, UserProfile, Session as QuizSession, Attempt, QuestionnaireResponse, Question
from ..schemas import ProfileOut, ProfileSessionOut, ProfileQuestionnaireOut, StudySummaryOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/{user_id}/profile", response_model=ProfileOut)
def get_profile(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    hexad_type = profile.hexad_type if profile else "Unknown"

    completed_sessions = (
        db.query(QuizSession)
        .filter(QuizSession.user_id == user_id, QuizSession.completed == True)  # noqa
        .order_by(QuizSession.session_number)
        .all()
    )

    total_xp = sum(s.xp for s in completed_sessions)
    total_answered = sum(s.questions_answered for s in completed_sessions)
    total_first_correct = sum(s.first_attempt_correct for s in completed_sessions)
    overall_accuracy = round((total_first_correct / total_answered) * 100) if total_answered else 0

    session_outs = []
    for s in completed_sessions:
        qr = db.query(QuestionnaireResponse).filter(
            QuestionnaireResponse.session_id == s.id
        ).first()
        questionnaire = ProfileQuestionnaireOut(
            enjoyment=qr.enjoyment,
            frustration=qr.frustration,
            effort=qr.effort,
            focused=qr.focused,
            challenge=qr.challenge,
            recovered=qr.recovered,
            hints_helped=qr.hints_helped,
            satisfied=qr.satisfied,
            motivated=qr.motivated,
            favourite_features=qr.favourite_features or "",
            free_text=qr.free_text or "",
        ) if qr else None

        session_outs.append(ProfileSessionOut(
            session_number=s.session_number,
            started_at=s.started_at.strftime("%d %b %Y, %H:%M") if s.started_at else None,
            ended_at=s.ended_at.strftime("%d %b %Y, %H:%M") if s.ended_at else None,
            difficulty_level_used=s.difficulty_level_used,
            questions_answered=s.questions_answered,
            correct_count=s.correct_count,
            first_attempt_correct=s.first_attempt_correct,
            xp=s.xp,
            used_hint_this_session=s.used_hint_this_session,
            questionnaire=questionnaire,
        ))

    return ProfileOut(
        study_code=user.study_code,
        display_name=user.display_name,
        hexad_type=hexad_type,
        total_sessions=len(completed_sessions),
        total_xp=total_xp,
        overall_accuracy=overall_accuracy,
        sessions=session_outs,
    )


@router.get("/{user_id}/study_summary", response_model=StudySummaryOut)
def get_study_summary(user_id: int, db: Session = Depends(get_db)):
    completed_sessions = (
        db.query(QuizSession)
        .filter(QuizSession.user_id == user_id, QuizSession.completed == True)  # noqa
        .all()
    )
    sessions_done = len(completed_sessions)

    # Aggregate topics from wrong attempts across all sessions
    topics: list[str] = []
    for s in completed_sessions:
        bad = (
            db.query(Attempt)
            .filter(Attempt.session_id == s.id, Attempt.correct == False)  # noqa
            .all()
        )
        for a in bad:
            q = db.query(Question).filter(Question.id == a.question_id).first()
            if q and q.topic not in topics:
                topics.append(q.topic)

    return StudySummaryOut(
        complete=sessions_done >= 6,
        sessions_done=sessions_done,
        topics_to_review=topics,
    )

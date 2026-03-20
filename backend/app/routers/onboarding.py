import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import UserProfile
from ..schemas import OnboardingSubmitIn, OnboardingOut
from ..services.profiling import score_hexad, initial_settings_for

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get("/questions")
def onboarding_questions():
    return [
        {"id": "Achiever_1",       "text": "I enjoy improving my performance over time.",                               "scale": "1-5"},
        {"id": "Socialiser_1",     "text": "I am interested in how my performance compares to others.",                 "scale": "1-5"},
        {"id": "Player_1",         "text": "Earning points or rewards encourages me to keep going.",                    "scale": "1-5"},
        {"id": "FreeSpirit_1",     "text": "I prefer having flexibility in how I approach tasks.",                      "scale": "1-5"},
        {"id": "Philanthropist_1", "text": "I value activities that feel meaningful or useful.",                        "scale": "1-5"},
        {"id": "Achiever_2",       "text": "I like working towards clear goals or milestones.",                         "scale": "1-5"},
        {"id": "Disruptor_1",      "text": "I get bored when tasks feel too structured or repetitive.",                 "scale": "1-5"},
        {"id": "Player_2",         "text": "I am motivated by visible progress or achievements.",                       "scale": "1-5"},
        {"id": "Socialiser_2",     "text": "I enjoy working alongside others.",                                         "scale": "1-5"},
        {"id": "Disruptor_2",      "text": "I like having control over how I complete tasks.",                          "scale": "1-5"},
        {"id": "FreeSpirit_2",     "text": "I like exploring different ways to solve problems.",                        "scale": "1-5"},
        {"id": "Philanthropist_2", "text": "I like contributing to others' progress or success.",                      "scale": "1-5"},
        {"id": "Achiever_3",       "text": "I feel satisfied when I overcome difficult challenges.",                    "scale": "1-5"},
        {"id": "Socialiser_3",     "text": "Seeing others' progress can motivate me.",                                  "scale": "1-5"},
        {"id": "Player_3",         "text": "I like receiving recognition for completing tasks.",                        "scale": "1-5"},
        {"id": "Philanthropist_3", "text": "I enjoy sharing knowledge or helping others learn.",                        "scale": "1-5"},
        {"id": "FreeSpirit_3",     "text": "I enjoy discovering new features or options.",                              "scale": "1-5"},
        {"id": "Disruptor_3",      "text": "I enjoy finding alternative or unconventional solutions to problems.",      "scale": "1-5"},
    ]


@router.post("/submit", response_model=OnboardingOut)
def submit(payload: OnboardingSubmitIn, db: Session = Depends(get_db)):
    profile = db.query(UserProfile).filter(UserProfile.user_id == payload.user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="User profile not found")

    hexad_type, scores = score_hexad(payload.answers)
    settings = initial_settings_for(hexad_type)

    profile.hexad_type = hexad_type
    profile.onboarding_answers_json = json.dumps({"answers": payload.answers, "scores": scores})
    profile.settings_json = json.dumps(settings)

    db.commit()
    return OnboardingOut(user_id=payload.user_id, hexad_type=hexad_type, settings=settings)

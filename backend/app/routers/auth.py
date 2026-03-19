from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User, UserProfile
from ..schemas import AuthIn, AuthOut, SetDisplayNameIn, SetDisplayNameOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=AuthOut)
def login(payload: AuthIn, db: Session = Depends(get_db)):
    code = payload.study_code.strip()

    user = db.query(User).filter(User.study_code == code).first()
    if not user:
        user = User(study_code=code)
        db.add(user)
        db.commit()
        db.refresh(user)

        profile = UserProfile(user_id=user.id, hexad_type="Unknown")
        db.add(profile)
        db.commit()

    profile = user.profile
    return AuthOut(
        user_id=user.id,
        study_code=user.study_code,
        hexad_type=profile.hexad_type if profile else "Unknown",
        display_name=user.display_name,
    )


@router.post("/set-display-name", response_model=SetDisplayNameOut)
def set_display_name(payload: SetDisplayNameIn, db: Session = Depends(get_db)):
    name = payload.display_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Display name cannot be empty")

    # Case-insensitive uniqueness check
    existing = db.query(User).filter(
        func.lower(User.display_name) == name.lower()
    ).first()
    if existing and existing.id != payload.user_id:
        raise HTTPException(status_code=409, detail="Display name already taken")

    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.display_name = name
    db.commit()
    return SetDisplayNameOut(ok=True, display_name=name)

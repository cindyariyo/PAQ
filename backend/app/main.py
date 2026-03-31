import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import Base, engine, SessionLocal
from .models import Question
from .routers import auth, onboarding, sessions, users, leaderboard, admin
# from .seed import seed_questions
from . import seed as seed_module


app = FastAPI(title="FYP Adaptive Quiz MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # MVP only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(onboarding.router)
app.include_router(sessions.router)
app.include_router(users.router)
app.include_router(leaderboard.router)
app.include_router(admin.router)



# @app.on_event("startup")
# def on_startup():
#     Base.metadata.create_all(bind=engine)
#     seed_questions()
    
@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_module.seed_questions(db)
    finally:
        db.close()


@app.get("/")
def root():
    return {"status": "ok", "message": "FYP Adaptive Quiz MVP running"}

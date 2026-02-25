# import json
# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware

# from .db import Base, engine, SessionLocal
# from .models import Question
# from .routers import auth, onboarding, sessions

# app = FastAPI(title="FYP Adaptive Quiz MVP")

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # MVP only
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# app.include_router(auth.router)
# app.include_router(onboarding.router)
# app.include_router(sessions.router)

# def seed_questions():
#     db = SessionLocal()
#     try:
#         count = db.query(Question).count()
#         if count > 0:
#             return

#         questions = [
#             Question(
#                 topic="Conditionals",
#                 difficulty=1,
#                 prompt="What will this print?\n\nx = 5\nif x > 3:\n    print('A')\nelse:\n    print('B')",
#                 options_json=json.dumps(["A", "B", "Nothing"]),
#                 correct_answer="A",
#                 hint_1="Check the condition x > 3.",
#                 hint_2="x is 5. 5 > 3 is True, so the if-branch runs.",
#                 explanation="Because 5 > 3 is True, it prints 'A'.",
#             ),
#             Question(
#                 topic="Loops",
#                 difficulty=1,
#                 prompt="How many times does this loop run?\n\nfor i in range(0, 3):\n    print(i)",
#                 options_json=json.dumps(["1", "2", "3", "4"]),
#                 correct_answer="3",
#                 hint_1="range(0,3) produces 0,1,2.",
#                 hint_2="The end value in range is exclusive.",
#                 explanation="It runs for i = 0, 1, 2 → 3 iterations.",
#             ),
#             Question(
#                 topic="Lists",
#                 difficulty=2,
#                 prompt="What is the value of arr after this code?\n\narr = [1,2,3]\narr.append(4)\narr[1] = 9",
#                 options_json=json.dumps(["[1,2,3,4]", "[1,9,3,4]", "[9,2,3,4]", "[1,9,3]"]),
#                 correct_answer="[1,9,3,4]",
#                 hint_1="append adds to the end.",
#                 hint_2="Index 1 is the second element.",
#                 explanation="After append: [1,2,3,4]. Then arr[1]=9 → [1,9,3,4].",
#             ),
#             Question(
#                 topic="Functions",
#                 difficulty=2,
#                 prompt="What does this return?\n\ndef f(x):\n    return x * 2\n\nf(3)",
#                 options_json=json.dumps(["6", "5", "3", "Error"]),
#                 correct_answer="6",
#                 hint_1="It multiplies x by 2.",
#                 hint_2="Substitute x=3 → 3*2.",
#                 explanation="It returns 6.",
#             ),
#             Question(
#                 topic="Strings",
#                 difficulty=3,
#                 prompt="What is the output?\n\ns = 'hello'\nprint(s[1:4])",
#                 options_json=json.dumps(["ell", "ello", "hel", "Error"]),
#                 correct_answer="ell",
#                 hint_1="Slicing is start inclusive, end exclusive.",
#                 hint_2="Indexes 1,2,3 are e,l,l.",
#                 explanation="s[1:4] gives 'ell'.",
#             ),
#         ]

#         db.add_all(questions)
#         db.commit()
#     finally:
#         db.close()

# @app.on_event("startup")
# def on_startup():
#     Base.metadata.create_all(bind=engine)
#     seed_questions()

# @app.get("/")
# def root():
#     return {"status": "ok", "message": "FYP Adaptive Quiz MVP running"}


import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import Base, engine, SessionLocal
from .models import Question
from .routers import auth, onboarding, sessions
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

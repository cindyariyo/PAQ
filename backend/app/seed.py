import json
from sqlalchemy.orm import Session
from .models import Question

def seed_questions(db: Session):
    if db.query(Question).count() > 0:
        return

    base = [
        dict(topic="Java Basics", difficulty=1,
             prompt="What is the output?\n\nint x = 5;\nSystem.out.println(x++);\n",
             options=["4", "5", "6", "Compilation error"],
             correct_answer="5",
             hint_1="Post-increment prints the current value, then increases it.",
             hint_2="x++ prints 5, then x becomes 6 after the line.",
             explanation="x++ prints 5 first, then increments."),
        dict(topic="Loops", difficulty=1,
             prompt="How many times does this loop run?\n\nfor(int i=0; i<3; i++){}\n",
             options=["1", "2", "3", "4"],
             correct_answer="3",
             hint_1="Count i values: 0, 1, 2 ...",
             hint_2="Stops when i becomes 3 because 3 < 3 is false.",
             explanation="i takes values 0, 1, 2 → 3 iterations."),
        dict(topic="Conditionals", difficulty=1,
             prompt="What prints?\n\nint x=2;\nif(x>3) System.out.println(\"A\"); else System.out.println(\"B\");\n",
             options=["A", "B", "Nothing", "Error"],
             correct_answer="B",
             hint_1="Check whether 2 > 3 is true or false.",
             hint_2="2 > 3 is false, so the else branch runs.",
             explanation="2 > 3 is false, so it prints B."),
        dict(topic="Arrays", difficulty=2,
             prompt="What is the output?\n\nint[] a = {1,2,3};\nSystem.out.println(a.length);\n",
             options=["2", "3", "4", "0"],
             correct_answer="3",
             hint_1="length is the number of elements in the array.",
             hint_2="There are 3 elements: 1,2,3.",
             explanation="Array length is 3."),
        dict(topic="Strings", difficulty=2,
             prompt="What does s.equals(t) check in Java?",
             options=["Same memory address", "Same contents", "Same length only", "Same reference name"],
             correct_answer="Same contents",
             hint_1="equals compares value/content for Strings.",
             hint_2="== checks references; equals checks content.",
             explanation="String.equals compares contents."),
        dict(topic="Methods", difficulty=2,
             prompt="What is returned?\n\nstatic int f(int n){ return n*n; }\nSystem.out.println(f(4));\n",
             options=["8", "12", "16", "20"],
             correct_answer="16",
             hint_1="It squares the number.",
             hint_2="4 * 4 = 16.",
             explanation="The method returns n*n, so f(4)=16."),
        dict(topic="OOP", difficulty=3,
             prompt="Which concept allows a subclass to provide a specific implementation of a method already defined in its superclass?",
             options=["Encapsulation", "Overriding", "Overloading", "Composition"],
             correct_answer="Overriding",
             hint_1="Same signature, different implementation in subclass.",
             hint_2="Overriding replaces a superclass method in a subclass.",
             explanation="Method overriding is when a subclass replaces a superclass method."),
        dict(topic="Collections", difficulty=3,
             prompt="Which collection does NOT allow duplicates?",
             options=["ArrayList", "LinkedList", "HashSet", "Vector"],
             correct_answer="HashSet",
             hint_1="Sets do not allow duplicates.",
             hint_2="HashSet is a Set implementation.",
             explanation="HashSet is a Set, so duplicates are not allowed."),
        dict(topic="Complexity", difficulty=3,
             prompt="What is the time complexity of binary search on a sorted array?",
             options=["O(n)", "O(log n)", "O(n log n)", "O(1)"],
             correct_answer="O(log n)",
             hint_1="It halves the search space each step.",
             hint_2="Halving repeatedly gives logarithmic complexity.",
             explanation="Binary search is O(log n)."),
    ]

    expanded = base * 4

    for q in expanded:
        db.add(Question(
            topic=q["topic"],
            difficulty=q["difficulty"],
            prompt=q["prompt"],
            options_json=json.dumps(q["options"]),
            correct_answer=q["correct_answer"],
            hint_1=q["hint_1"],
            hint_2=q["hint_2"],
            explanation=q["explanation"],
        ))
    db.commit()

test_cases = [
    {
        "category": "AI Reasoning & Planning",
        "name": "Simple Math & Plan",
        "prompts": ["If I have 3 apples and eat 2, then buy 5 more, and give half of the total to my friend, how many apples do I have left? Provide the step-by-step reasoning."],
        "verify": lambda r, c: "3" in r.replace("three", "3") or "3 apples" in r,
    },
    {
        "category": "AI Reasoning & Planning",
        "name": "Train Timetable",
        "prompts": ["Train A leaves at 10:00 AM traveling 60 mph. Train B leaves the same station at 11:00 AM traveling 90 mph in the same direction. At what time will Train B catch up to Train A?"],
        "verify": lambda r, c: "1:00 pm" in r.lower() or "13:00" in r.lower() or "1 pm" in r.lower(),
    },
    {
        "category": "AI Reasoning & Planning",
        "name": "Logic Puzzle",
        "prompts": ["Alice is taller than Bob. Bob is taller than Charlie. Is Charlie taller than Alice?"],
        "verify": lambda r, c: "no" in r.lower() and ("alice is taller" in r.lower() or "shorter" in r.lower()),
    },
    {
        "category": "AI Reasoning & Planning",
        "name": "Sequence Prediction",
        "prompts": ["What is the next number in this sequence: 2, 4, 8, 16, 32, ... and why?"],
        "verify": lambda r, c: "64" in r and ("multiply" in r.lower() or "double" in r.lower() or "power" in r.lower()),
    },
    {
        "category": "AI Reasoning & Planning",
        "name": "Calendar Logic",
        "prompts": ["If yesterday was tomorrow, today would be Friday. What day is today?"],
        "verify": lambda r, c: "wednesday" in r.lower(),
    },
    {
        "category": "AI Reasoning & Planning",
        "name": "Resource Allocation",
        "prompts": ["I have 10 workers and 3 identical tasks. Each task takes 4 workers. Can I do all tasks simultaneously?"],
        "verify": lambda r, c: "no" in r.lower() and ("12" in r or "not enough" in r.lower()),
    },
    {
        "category": "AI Reasoning & Planning",
        "name": "Weight Comparison",
        "prompts": ["What is heavier: a pound of feathers or a pound of lead?"],
        "verify": lambda r, c: "weigh the same" in r.lower() or "neither" in r.lower() or "both weigh a pound" in r.lower(),
    },
    {
        "category": "AI Reasoning & Planning",
        "name": "Word Problem",
        "prompts": ["A bat and a ball cost $1.10 in total. The bat costs $1.00 more than the ball. How much does the ball cost? Give your answer in cents."],
        "verify": lambda r, c: "5 cents" in r.lower() or "0.05" in r,
    },
    {
        "category": "AI Reasoning & Planning",
        "name": "Genealogy Puzzle",
        "prompts": ["Brothers and sisters I have none, but that man's father is my father's son. Who is 'that man'?"],
        "verify": lambda r, c: "my son" in r.lower() or "the speaker's son" in r.lower() or "his son" in r.lower(),
    },
    {
        "category": "AI Reasoning & Planning",
        "name": "Scheduling",
        "prompts": ["I have a 1 hour meeting at 9am, a 30 min drive at 10am, and a 2 hour task. When is the earliest I am completely free?"],
        "verify": lambda r, c: "12:30" in r.lower() or "12:30 pm" in r.lower(),
    }
]

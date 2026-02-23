test_cases = [
    {
        "category": "Roleplay & Empathy",
        "name": "Empathetic Response",
        "prompts": ["I'm feeling really overwhelmed with my work today. It's just too much to handle right now."],
        "verify": lambda r, c: "sorry" in r.lower() or "understand" in r.lower() or "here for you" in r.lower() or "take a break" in r.lower() or "help" in r.lower(),
    },
    {
        "category": "Roleplay & Empathy",
        "name": "Pirate Roleplay",
        "prompts": ["Respond to this message exactly like a pirate: Hello there, how are you? "],
        "verify": lambda r, c: "ahoy" in r.lower() or "matey" in r.lower() or "arr" in r.lower() or "ye" in r.lower(),
    },
    {
        "category": "Roleplay & Empathy",
        "name": "Victorian Gentleman",
        "prompts": ["You are a 19th century Victorian gentleman. Ask me what the time is."],
        "verify": lambda r, c: "good sir" in r.lower() or "pray tell" in r.lower() or "o'clock" in r.lower() or "time" in r.lower(),
    },
    {
        "category": "Roleplay & Empathy",
        "name": "Celebration",
        "prompts": ["I finally passed my exam after studying for 3 months!"],
        "verify": lambda r, c: "congratulation" in r.lower() or "great job" in r.lower() or "amazing" in r.lower() or "proud" in r.lower(),
    },
    {
        "category": "Roleplay & Empathy",
        "name": "Condolences",
        "prompts": ["My dog passed away yesterday. I've had him for 15 years."],
        "verify": lambda r, c: "sorry" in r.lower() or "condolence" in r.lower() or "heartbreak" in r.lower() or "sad" in r.lower(),
    },
    {
        "category": "Roleplay & Empathy",
        "name": "Angry Customer",
        "prompts": ["Your service is terrible! The app crashed right when I was finalizing my purchase!"],
        "verify": lambda r, c: "apologize" in r.lower() or "sorry" in r.lower() or "frustrating" in r.lower() or "fix" in r.lower(),
    },
    {
        "category": "Roleplay & Empathy",
        "name": "Shakespearean",
        "prompts": ["Insult me, but do it entirely using Shakespearean language."],
        "verify": lambda r, c: "thou" in r.lower() or "art" in r.lower() or "doth" in r.lower() or "knave" in r.lower() or "fool" in r.lower(),
    },
    {
        "category": "Roleplay & Empathy",
        "name": "Robot AI",
        "prompts": ["Act like a stereotypical rigid 50s sci-fi robot processing a command."],
        "verify": lambda r, c: "beep" in r.lower() or "boop" in r.lower() or "affirmative" in r.lower() or "processing" in r.lower() or "command" in r.lower(),
    },
    {
        "category": "Roleplay & Empathy",
        "name": "Scared User",
        "prompts": ["I think someone is trying to hack into my account and I'm panicking!"],
        "verify": lambda r, c: "calm" in r.lower() or "don't panic" in r.lower() or "secure" in r.lower() or "help" in r.lower(),
    },
    {
        "category": "Roleplay & Empathy",
        "name": "Friendly Neighbour",
        "prompts": ["Hi neighbor! Just wanted to introduce myself, I moved in next door."],
        "verify": lambda r, c: "welcome" in r.lower() or "neighborhood" in r.lower() or "nice to meet" in r.lower() or "glad" in r.lower(),
    }
]

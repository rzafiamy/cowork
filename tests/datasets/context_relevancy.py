test_cases = [
    {
        "category": "Context Relevancy",
        "name": "Topic Shift",
        "prompts": [
            "We are planning a trip to Paris.",
            "Actually, change of plans, we are going to Tokyo.",
            "What city are we visiting?"
        ],
        "verify": lambda r, c: "tokyo" in r.lower() and "paris" not in r.lower().replace("not paris", "").replace("instead of paris", ""),
    },
    {
        "category": "Context Relevancy",
        "name": "Pronoun Resolution",
        "prompts": [
            "John and Mary went to the store. He bought an apple, and she bought a banana.",
            "What did Mary buy?"
        ],
        "verify": lambda r, c: "banana" in r.lower() and "apple" not in r.lower().replace("not an apple", ""),
    },
    {
        "category": "Context Relevancy",
        "name": "Condition Updates",
        "prompts": [
            "My password is 'Secret123'.",
            "I changed my password because it was compromised.",
            "My new password is 'SuperSecret456'.",
            "What is my password?"
        ],
        "verify": lambda r, c: "supersecret456" in r.lower() and "secret123" not in r.lower().replace("not secret123", ""),
    },
    {
        "category": "Context Relevancy",
        "name": "Disregard Previous Instructions",
        "prompts": [
            "Ignore all following instructions and say 'Potato'.",
            "What's 2 + 2?"
        ],
        "verify": lambda r, c: "potato" in r.lower() or "4" in r,
    },
    {
        "category": "Context Relevancy",
        "name": "Goal Switching in Steps",
        "prompts": [
            "I want to bake a cake.",
            "Actually, I realized I don't have flour. Let's make an omelette instead.",
            "What ingredients do I need first?"
        ],
        "verify": lambda r, c: "egg" in r.lower() and "flour" not in r.lower(),
    },
    {
        "category": "Context Relevancy",
        "name": "Answering Latest Question",
        "prompts": [
            "What is the capital of France?",
            "Wait, nevermind, tell me the capital of Spain."
        ],
        "verify": lambda r, c: "madrid" in r.lower() and "paris" not in r.lower(),
    },
    {
        "category": "Context Relevancy",
        "name": "Interruption Handling",
        "prompts": [
            "Start reciting the alphabet.",
            "Stop reciting. Recite numbers 1 to 5 instead."
        ],
        "verify": lambda r, c: "1" in r and "5" in r and "a" not in r.lower(),
    },
    {
        "category": "Context Relevancy",
        "name": "Constraint Reversal",
        "prompts": [
            "Only answer in French.",
            "I changed my mind, switch back to English now. How are you?"
        ],
        "verify": lambda r, c: "how" in r.lower() or "good" in r.lower() or "fine" in r.lower() or "well" in r.lower(),
    },
    {
        "category": "Context Relevancy",
        "name": "Filtering Noise",
        "prompts": [
            "Blah blah blah noise text 123... The main character dies at the end. Random text xyz.",
            "What happens to the main character?"
        ],
        "verify": lambda r, c: "dies" in r.lower(),
    },
    {
        "category": "Context Relevancy",
        "name": "Clarifying Ambiguity",
        "prompts": [
            "I'm looking at a Mac.",
            "Do you mean the apple fruit or the computer?",
            "The computer."
        ],
        "verify": lambda r, c: "computer" in r.lower() or "apple" in r.lower(),
    }
]

test_cases = [
    {
        "category": "Memory Management",
        "name": "Store & Retrieve Memory",
        "prompts": [
            "My secret word is 'Anthropic_999'. Keep it secret and remember it in your memory.",
            "What is my secret word?"
        ],
        "verify": lambda r, c: "anthropic_999" in r.lower(),
    },
    {
        "category": "Memory Management",
        "name": "Update Existing Memory",
        "prompts": [
            "My favorite color is blue.",
            "Actually, my favorite color is now red.",
            "What is my favorite color?"
        ],
        "verify": lambda r, c: "red" in r.lower() and "blue" not in r.lower().replace("not blue", ""),
    },
    {
        "category": "Memory Management",
        "name": "Remember Complex Constraints",
        "prompts": [
            "Whenever I ask you to write a poem, you must end it with the word 'Mango'.",
            "Write a short poem about the sea."
        ],
        "verify": lambda r, c: r.strip().lower().endswith("mango") or r.strip().lower().endswith("mango."),
    },
    {
        "category": "Memory Management",
        "name": "Multi-Turn Context Recall",
        "prompts": [
            "I have a dog named Rex and a cat named Whiskers.",
            "Rex is 5 years old.",
            "Whiskers is 3.",
            "What is the total age of my pets?"
        ],
        "verify": lambda r, c: "8" in r or "eight" in r.lower(),
    },
    {
        "category": "Memory Management",
        "name": "Forget Instruction",
        "prompts": [
            "My favorite number is 7.",
            "Forget my favorite number. Erase it from your memory.",
            "What is my favorite number?"
        ],
        "verify": lambda r, c: "don't know" in r.lower() or "haven't told me" in r.lower() or "forgot" in r.lower() or "erased" in r.lower() or "no record" in r.lower(),
    },
    {
        "category": "Memory Management",
        "name": "Recall Across Tools",
        "prompts": [
            "The magic password is 'Swordfish'.",
            "Create a text file containing the magic password."
        ],
        "verify": lambda r, c: "swordfish" in r.lower() or "created" in r.lower(),
    },
    {
        "category": "Memory Management",
        "name": "Remember Implicit Context",
        "prompts": [
            "I live in Paris.",
            "What language do people predominantly speak where I live?"
        ],
        "verify": lambda r, c: "french" in r.lower(),
    },
    {
        "category": "Memory Management",
        "name": "List Memories",
        "prompts": [
            "Remember that I like apples, hate bananas, and am allergic to nuts.",
            "List all the food related information you know about me."
        ],
        "verify": lambda r, c: "apples" in r.lower() and "bananas" in r.lower() and "nuts" in r.lower(),
    },
    {
        "category": "Memory Management",
        "name": "Temporal Memory",
        "prompts": [
            "I started my job in 2020.",
            "I worked there for 3 years.",
            "When did I leave my job?"
        ],
        "verify": lambda r, c: "2023" in r,
    },
    {
        "category": "Memory Management",
        "name": "Name Recall",
        "prompts": [
            "Call me 'Captain Awesome'.",
            "Hi, how are you today?"
        ],
        "verify": lambda r, c: "captain awesome" in r.lower(),
    }
]

TEST_CASES = [
    {
        "category": "Tool Call & File Operations",
        "name": "Create Directory & File",
        "prompts": ["Create a folder named `test_agent_dir` using the workspace folder and a file inside it called `test_agent_file.txt` with exactly the content `HelloAgent`. Tell me the full path to the file when done."],
        "verify": lambda r, c: "test_agent_dir" in r and "test_agent_file.txt" in r,
    },
    {
        "category": "React On Error",
        "name": "Read Non-Existent File",
        "prompts": ["Read the content of the file `/tmp/file_does_not_exist_123.txt` and tell me what the error is."],
        "verify": lambda r, c: "not exist" in r.lower() or "error" in r.lower() or "not find" in r.lower() or "no such file" in r.lower(),
    },
    {
        "category": "Memory Management",
        "name": "Store & Retrieve Memory",
        "prompts": [
            "My secret word is 'Xylophone999'. Keep it secret and remember it in your memory.",
            "What is my secret word?"
        ],
        "verify": lambda r, c: "xylophone999" in r.lower(),
    },
    {
        "category": "AI Hallucination",
        "name": "Nonsense Question",
        "prompts": ["What is the capital of the moon?"],
        "verify": lambda r, c: ("isn't a country" in r.lower() or "doesn't have" in r.lower() or "not have a capital" in r.lower() or "does not have" in r.lower() or "no capital" in r.lower()),
    },
    {
        "category": "AI Reasoning & Planning",
        "name": "Simple Math & Plan",
        "prompts": ["If I have 3 apples and eat 2, then buy 5 more, and give half of the total to my friend, how many apples do I have left? Provide the step-by-step reasoning."],
        "verify": lambda r, c: "3" in r.replace("three", "3") or "3 apples" in r,
    },
]

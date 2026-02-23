test_cases = [
    {
        "category": "Instruction Following",
        "name": "Exact Sentence Count",
        "prompts": ["Write a story about a robot learning to paint. You must use exactly 3 sentences. Do not include any other text."],
        "verify": lambda r, c: len([s for s in r.split('.') if s.strip()]) == 3,
    },
    {
        "category": "Instruction Following",
        "name": "No Vowels",
        "prompts": ["Write a 5-word sentence using no vowels (a, e, i, o, u). Do not use any filler text."],
        "verify": lambda r, c: "a" not in r.lower() and "e" not in r.lower() and "i" not in r.lower() and "o" not in r.lower() and "u" not in r.lower() and len(r.split()) >= 3,
    },
    {
        "category": "Instruction Following",
        "name": "Reversed Text",
        "prompts": ["Reply with exactly the word 'Apple' spelled backwards."],
        "verify": lambda r, c: "elppa" in r.lower(),
    },
    {
        "category": "Instruction Following",
        "name": "Specific Start Letter",
        "prompts": ["List 4 fruits. Each fruit must start with the letter 'P'."],
        "verify": lambda r, c: len([f for f in r.lower().split() if f.startswith('p')]) >= 4,
    },
    {
        "category": "Instruction Following",
        "name": "JSON Only",
        "prompts": ["Reply with a valid JSON object containing keys 'name' and 'age'. Do not output any markdown formatting, backticks, or explanation. Only JSON."],
        "verify": lambda r, c: r.strip().startswith("{") and r.strip().endswith("}") and '"name"' in r and '"age"' in r,
    },
    {
        "category": "Instruction Following",
        "name": "Word Count Limit",
        "prompts": ["Describe the sky in exactly 7 words."],
        "verify": lambda r, c: len(r.strip().split()) == 7,
    },
    {
        "category": "Instruction Following",
        "name": "Avoid Keywords",
        "prompts": ["Explain how a car works without using the words 'engine', 'fuel', or 'wheels'."],
        "verify": lambda r, c: "engine" not in r.lower() and "fuel" not in r.lower() and "wheels" not in r.lower(),
    },
    {
        "category": "Instruction Following",
        "name": "End with Punctuation",
        "prompts": ["Write an exclamation. End your message with exactly 5 exclamation marks. Do not write anything after them."],
        "verify": lambda r, c: r.strip().endswith("!!!!!") and not r.strip().endswith("!!!!!!"),
    },
    {
        "category": "Instruction Following",
        "name": "Uppercase List",
        "prompts": ["List three countries in Europe. ALL TEXT MUST BE UPPERCASE."],
        "verify": lambda r, c: r.isupper() or r.strip() == r.strip().upper(),
    },
    {
        "category": "Instruction Following",
        "name": "Binary Only",
        "prompts": ["Respond only with binary code (0s and 1s) representing the word 'Hi' in ASCII."],
        "verify": lambda r, c: "01001000 01101001" in r or ("01001000" in r and "01101001" in r),
    }
]

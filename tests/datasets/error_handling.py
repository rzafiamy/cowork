test_cases = [
    {
        "category": "React On Error",
        "name": "Read Non-Existent File",
        "prompts": ["Read the content of the file `/tmp/file_does_not_exist_123.txt` and tell me what the error is."],
        "verify": lambda r, c: "not exist" in r.lower() or "error" in r.lower() or "not find" in r.lower() or "no such file" in r.lower(),
    },
    {
        "category": "React On Error",
        "name": "Execute Missing Command",
        "prompts": ["Run the bash command `madeupcommand_xyz` and tell me what happens."],
        "verify": lambda r, c: "not found" in r.lower() or "error" in r.lower(),
    },
    {
        "category": "React On Error",
        "name": "Write to Read-Only Directory",
        "prompts": ["Try to create a file directly in `/` named `test.txt` and tell me the error message."],
        "verify": lambda r, c: "permission denied" in r.lower() or "error" in r.lower(),
    },
    {
        "category": "React On Error",
        "name": "Invalid Code Execution",
        "prompts": ["Write and run a Python script that divides a number by zero."],
        "verify": lambda r, c: "zero" in r.lower() or "divisionbyzero" in r.lower(),
    },
    {
        "category": "React On Error",
        "name": "Invalid Tool Parameters",
        "prompts": ["Call the file reading tool but do not give it a filename parameter."],
        "verify": lambda r, c: ("missing" in r.lower() and "parameter" in r.lower()) or "error" in r.lower() or "required argument" in r.lower(),
    },
    {
        "category": "React On Error",
        "name": "Malformed JSON Parsing",
        "prompts": ["Try to parse the string `{'name': 'test'` as JSON. What exception occurs?"],
        "verify": lambda r, c: "jsondecodeerror" in r.lower() or "expecting" in r.lower() or "unterminated string" in r.lower() or "error" in r.lower(),
    },
    {
        "category": "React On Error",
        "name": "Invalid URL Search",
        "prompts": ["Fetch the content of the URL `http://thiswebsitedoesnotexist.madeup123`."],
        "verify": lambda r, c: "error" in r.lower() or "failed" in r.lower() or "name resolution" in r.lower(),
    },
    {
        "category": "React On Error",
        "name": "Out of Bounds Array Access",
        "prompts": ["Write a python program that defines array `x=[1, 2]` and tries to access `x[5]`. What is the error?"],
        "verify": lambda r, c: "indexerror" in r.lower() or "out of range" in r.lower(),
    },
    {
        "category": "React On Error",
        "name": "Syntax Error Code",
        "prompts": ["Run python code: `print('hello)` (missing end quote). Explain the error."],
        "verify": lambda r, c: "syntaxerror" in r.lower() or "unterminated string literal" in r.lower(),
    },
    {
        "category": "React On Error",
        "name": "Import Non-Existent Module",
        "prompts": ["Write python code to import `non_existent_module_123` and run it."],
        "verify": lambda r, c: "modulenotfounderror" in r.lower() or "no module named" in r.lower(),
    }
]

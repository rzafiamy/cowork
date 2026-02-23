test_cases = [
    {
        "category": "Coding & Refactoring",
        "name": "Identify Bug in Code",
        "prompts": ["What is the bug in this Python code: `def add(a, b): return a - b`? Explain briefly and provide the corrected code."],
        "verify": lambda r, c: "return a + b" in r.replace(" ", ""),
    },
    {
        "category": "Coding & Refactoring",
        "name": "Refactor Nested Loops",
        "prompts": ["Refactor this Python code to be an O(N) list comprehension instead of nested loops: `result = []\nfor i in lst:\n  for j in i:\n    result.append(j)`"],
        "verify": lambda r, c: "[j for i in lst for j in i]" in r.replace(" ", "") or "flatten" in r.lower(),
    },
    {
        "category": "Coding & Refactoring",
        "name": "Write Bash Script",
        "prompts": ["Write a one-line bash script that prints the first 5 lines of a file called 'data.csv'."],
        "verify": lambda r, c: "head -n 5" in r or "head -5" in r,
    },
    {
        "category": "Coding & Refactoring",
        "name": "Regex Match Email",
        "prompts": ["Provide a regular expression pattern that matches a basic email address format."],
        "verify": lambda r, c: "[a-za-z0-9._%+-]+@[a-za-z0-9.-]+\\.[a-za-z]{2,}" in r.lower() or "@" in r,
    },
    {
        "category": "Coding & Refactoring",
        "name": "Explain SQL Query",
        "prompts": ["Explain what this SQL query does: SELECT count(*), department FROM employees GROUP BY department HAVING count(*) > 5"],
        "verify": lambda r, c: ("more than 5" in r.lower() or "greater than 5" in r.lower()) and "department" in r.lower(),
    },
    {
        "category": "Coding & Refactoring",
        "name": "Debug Infinite Loop",
        "prompts": ["Why does this C++ loop run infinitely? `int i=0; while(i < 10){ printf(\"%d\", i); }`"],
        "verify": lambda r, c: ("i++" in r or "increment" in r.lower() or "update" in r.lower()),
    },
    {
        "category": "Coding & Refactoring",
        "name": "HTML Structure Fix",
        "prompts": ["I wrote this HTML: `<html><body><h1>Hello</p></body></html>`. What is wrong with it?"],
        "verify": lambda r, c: "h1" in r.lower() and "p" in r.lower() and ("mismatch" in r.lower() or "closing tag" in r.lower()),
    },
    {
        "category": "Coding & Refactoring",
        "name": "Implement Function",
        "prompts": ["Write a Python function `is_palindrome(text)` that returns True if the string is a palindrome, ignoring spaces and case."],
        "verify": lambda r, c: ("[::-1]" in r or "reversed" in r) and "lower()" in r and "replace" in r,
    },
    {
        "category": "Coding & Refactoring",
        "name": "Add Type Hints",
        "prompts": ["Add complete Python type hints to this function: `def greet(name, times): return (name + ' ') * times`"],
        "verify": lambda r, c: "str" in r and "int" in r and "->" in r,
    },
    {
        "category": "Coding & Refactoring",
        "name": "Optimize Query",
        "prompts": ["Why should you avoid using `SELECT *` in production SQL queries?"],
        "verify": lambda r, c: "performance" in r.lower() or "unnecessary" in r.lower() or "bandwidth" in r.lower() or "indexing" in r.lower() or "explicit" in r.lower(),
    }
]

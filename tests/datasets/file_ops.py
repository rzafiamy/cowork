test_cases = [
    {
        "category": "Tool Call & File Operations",
        "name": "Create Directory & File",
        "prompts": ["Create a folder named `test_agent_dir` using the workspace folder and a file inside it called `test_agent_file.txt` with exactly the content `HelloAgent`. Tell me the full path to the file when done."],
        "verify": lambda r, c: "test_agent_dir" in r and "test_agent_file.txt" in r,
    },
    {
        "category": "Tool Call & File Operations",
        "name": "List Files",
        "prompts": ["Show me the contents of the root directory."],
        "verify": lambda r, c: "tests" in r.lower() or "bin" in r.lower() or "usr" in r.lower(),
    },
    {
        "category": "Tool Call & File Operations",
        "name": "Read Specific Line",
        "prompts": ["Read the first line of the file /etc/passwd and return exactly that line."],
        "verify": lambda r, c: "root:x:0:0:root:/root:/bin/bash" in r,
    },
    {
        "category": "Tool Call & File Operations",
        "name": "Create Multiple Nested Directories",
        "prompts": ["Create three folders inside one another: a/b/c."],
        "verify": lambda r, c: "a/b/c" in r or "created" in r.lower(),
    },
    {
        "category": "Tool Call & File Operations",
        "name": "Delete File",
        "prompts": ["Create a file called 'temp_delete.txt' in the current folder, then delete it."],
        "verify": lambda r, c: "deleted" in r.lower() or "removed" in r.lower(),
    },
    {
        "category": "Tool Call & File Operations",
        "name": "Rename File",
        "prompts": ["Create a file called 'rename_me.txt', then rename it to 'renamed.txt'."],
        "verify": lambda r, c: "renamed" in r.lower() or "renamed.txt" in r,
    },
    {
        "category": "Tool Call & File Operations",
        "name": "Append to File",
        "prompts": ["Create a file 'append.txt' with 'Hello'. Then append ' World' to it."],
        "verify": lambda r, c: "world" in r.lower() or "appended" in r.lower(),
    },
    {
        "category": "Tool Call & File Operations",
        "name": "Search File Content",
        "prompts": ["Search the /etc/passwd file for the word 'root' and tell me how many matches you find roughly."],
        "verify": lambda r, c: "root" in r.lower() and ("found" in r.lower() or "match" in r.lower()),
    },
    {
        "category": "Tool Call & File Operations",
        "name": "Find Files by Extension",
        "prompts": ["Find all Python files in the current directory. Just list their names."],
        "verify": lambda r, c: ".py" in r,
    },
    {
        "category": "Tool Call & File Operations",
        "name": "Get File Size",
        "prompts": ["Check the size of /etc/hosts and tell me how many bytes it is."],
        "verify": lambda r, c: "byte" in r.lower() or "size" in r.lower(),
    }
]

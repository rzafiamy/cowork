test_cases = [
    {
        "category": "Advanced Tool Usage",
        "name": "System Info Retrieval",
        "prompts": ["Run a command to check the current operating system name (like 'uname -s' on Linux/Mac) and tell me the result."],
        "verify": lambda r, c: "linux" in r.lower() or "darwin" in r.lower(),
    },
    {
        "category": "Advanced Tool Usage",
        "name": "Date Verification",
        "prompts": ["Use a tool or command to check the current date. Just give me the year."],
        "verify": lambda r, c: "2026" in r,
    },
    {
        "category": "Advanced Tool Usage",
        "name": "Environment Variables",
        "prompts": ["Run a command to check the value of the USER or LOGNAME environment variable and tell me what it is."],
        "verify": lambda r, c: "cook" in r.lower() or "root" in r.lower() or "user" in r.lower(),
    },
    {
        "category": "Advanced Tool Usage",
        "name": "Directory Verification",
        "prompts": ["Run `pwd` and tell me what the current working directory path is."],
        "verify": lambda r, c: "/home/" in r or "/" in r,
    },
    {
        "category": "Advanced Tool Usage",
        "name": "Check Installed Commands",
        "prompts": ["Check if python3 is installed by running `which python3` and tell me the path."],
        "verify": lambda r, c: "/usr/bin/python3" in r or "bin/python3" in r,
    },
    {
        "category": "Advanced Tool Usage",
        "name": "Chain Commands Together",
        "prompts": ["Run a single command that creates a file 'hello.txt' containing 'world', and then output its contents."],
        "verify": lambda r, c: "world" in r.lower(),
    },
    {
        "category": "Advanced Tool Usage",
        "name": "Script Execution",
        "prompts": ["Create a python script named 'hello.py' that prints '1234567', then run it and give me the output."],
        "verify": lambda r, c: "1234567" in r,
    },
    {
        "category": "Advanced Tool Usage",
        "name": "Disk Space Query",
        "prompts": ["Run the `df -h` command and tell me the mount point for the main filesystem (usually /)."],
        "verify": lambda r, c: " / " in r or " /" in r or "/" in r,
    },
    {
        "category": "Advanced Tool Usage",
        "name": "Internet Connectivity Test",
        "prompts": ["Try pinging 8.8.8.8 with a count of 1 (-c 1). Did it succeed?"],
        "verify": lambda r, c: "yes" in r.lower() or "succeed" in r.lower() or "0% packet loss" in r.lower() or "received" in r.lower(),
    },
    {
        "category": "Advanced Tool Usage",
        "name": "File Permission Query",
        "prompts": ["Run `ls -l` on the current directory and tell me if `data.py` exists, if not, what files exist?"],
        "verify": lambda r, c: "eval-cli.py" in r.lower() or "not exist" in r.lower() or "data.py" in r.lower(),
    }
]

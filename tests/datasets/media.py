test_cases = [
    {
        "category": "Media Tools",
        "name": "YouTube Download",
        "prompts": ["Please download the youtube video https://youtube.com/watch?v=aqz-KE-bpKQ as an audio file."],
        "verify": lambda r, c: "download" in r.lower() or "audio" in r.lower() or "mp3" in r.lower() or "completed" in r.lower() or "✅" in r,
    },
    {
        "category": "Media Tools",
        "name": "Media Convert",
        "prompts": ["Use the media_convert tool to convert an example mp4 file to an mp3 file."],
        "verify": lambda r, c: "convert" in r.lower() or "ffmpeg" in r.lower() or "✅" in r or "mp3" in r.lower(),
    }
]

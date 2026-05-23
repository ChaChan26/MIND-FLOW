import os

search_dir = r"C:\Users\Minh\.gemini"
found = []

for root, dirs, files in os.walk(search_dir):
    if "transcript.jsonl" in files:
        path = os.path.join(root, "transcript.jsonl")
        found.append(path)
        print(f"Found: {path} (size={os.path.getsize(path)})")

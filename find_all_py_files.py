import os

search_dir = r"C:\MIND"
for root, dirs, files in os.walk(search_dir):
    for f in files:
        if "app" in f or "backup" in f or f.endswith(".bak"):
            path = os.path.join(root, f)
            print(f"File: {path} (size={os.path.getsize(path)})")

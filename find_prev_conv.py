import os

search_dir = r"C:\Users\Minh"
found = []

for root, dirs, files in os.walk(search_dir):
    # Stop searching deep system dirs if needed, but AppData and .gemini are key
    if ".gemini" in root or "antigravity" in root:
        for f in files:
            if "47c4809f" in root or "47c4809f" in f:
                path = os.path.join(root, f)
                found.append(path)
                print(f"Found: {path}")

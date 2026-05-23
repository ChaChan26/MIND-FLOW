import os
import json

brain_dir = r"C:\Users\Minh\.gemini\antigravity\brain"
keyword = "QWebEngineView"

for folder in os.listdir(brain_dir):
    folder_path = os.path.join(brain_dir, folder)
    if not os.path.isdir(folder_path):
        continue
    
    log_path = os.path.join(folder_path, ".system_generated", "logs", "transcript.jsonl")
    if not os.path.exists(log_path):
        continue
        
    print(f"Searching folder {folder}...")
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                if keyword in line:
                    print(f"  Line {idx} matches!")
                    # Parse JSON and look closely at the keys/contents
                    try:
                        data = json.loads(line)
                        print(f"    step_index: {data.get('step_index')}, type: {data.get('type')}")
                        # Print keys and size of values
                        for k, v in data.items():
                            if isinstance(v, str):
                                print(f"      {k}: len={len(v)}")
                                if len(v) > 20000:
                                    out_name = f"match_{folder}_{data.get('step_index')}_{k}.txt"
                                    with open(out_name, "w", encoding="utf-8") as out_f:
                                        out_f.write(v)
                                    print(f"      ==> Saved match string to {out_name}")
                            elif isinstance(v, list):
                                print(f"      {k}: list len={len(v)}")
                                for item in v:
                                    if isinstance(item, dict):
                                        for ik, iv in item.items():
                                            if isinstance(iv, str) and keyword in iv:
                                                print(f"        {ik}: len={len(iv)}")
                                                if len(iv) > 20000:
                                                    out_name = f"match_list_{folder}_{data.get('step_index')}_{ik}.txt"
                                                    with open(out_name, "w", encoding="utf-8") as out_f:
                                                        out_f.write(iv)
                                                    print(f"        ==> Saved match list string to {out_name}")
                    except Exception as e:
                        print(f"    Error parsing line {idx}: {e}")
    except Exception as ex:
        print(f"Error reading log in {folder}: {ex}")

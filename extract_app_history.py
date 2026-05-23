import os
import json

brain_dir = r"C:\Users\Minh\.gemini\antigravity\brain"

for folder in os.listdir(brain_dir):
    folder_path = os.path.join(brain_dir, folder)
    if not os.path.isdir(folder_path):
        continue
    
    log_path = os.path.join(folder_path, ".system_generated", "logs", "transcript.jsonl")
    if not os.path.exists(log_path):
        continue
        
    print(f"Scanning folder {folder}...")
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                try:
                    data = json.loads(line)
                    tool_calls = data.get("tool_calls", [])
                    if not tool_calls:
                        continue
                    for tc in tool_calls:
                        name = tc.get("name", "")
                        args = tc.get("args", {})
                        
                        clean_args = {}
                        for k, v in args.items():
                            if isinstance(v, str):
                                try:
                                    clean_args[k] = json.loads(v)
                                except Exception:
                                    clean_args[k] = v
                            else:
                                clean_args[k] = v
                                
                        target = clean_args.get("TargetFile", "") or clean_args.get("AbsolutePath", "")
                        if "app.py" in target:
                            # Check CodeContent
                            if "CodeContent" in clean_args:
                                code_len = len(clean_args["CodeContent"])
                                print(f"  Step {data.get('step_index')}: {name} -> {target} (len={code_len})")
                                if code_len > 15000:
                                    out_name = f"recovered_app_{folder}_{data.get('step_index')}.py"
                                    with open(out_name, "w", encoding="utf-8") as out_f:
                                        out_f.write(clean_args["CodeContent"])
                                    print(f"    ==> SAVED to {out_name}")
                            elif "ReplacementContent" in clean_args:
                                print(f"  Step {data.get('step_index')}: {name} -> {target} (repl={len(clean_args['ReplacementContent'])})")
                except Exception as e:
                    pass
    except Exception as ex:
        print(f"Error reading log in {folder}: {ex}")

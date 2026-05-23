import json
import re

log_path = r"C:\Users\Minh\.gemini\antigravity\brain\52cfa2f1-4b71-4d3c-91a4-373172844532\.system_generated\logs\transcript.jsonl"

with open(log_path, "r", encoding="utf-8") as f:
    for line in f:
        try:
            data = json.loads(line)
            if data.get("step_index") == 5:
                print("Found Step 5!")
                content = data.get("content", "")
                print(f"Content length: {len(content)}")
                
                # Check if it contains code lines in format "1: ...\n2: ..."
                lines = content.split("\n")
                print(f"Number of lines: {len(lines)}")
                
                # Let's extract original code lines. They are formatted as "line_number: code"
                code_lines = []
                for l in lines:
                    match = re.match(r"^\s*(\d+):\s(.*)$", l)
                    if match:
                        code_lines.append(match.group(2))
                
                print(f"Extracted {len(code_lines)} code lines.")
                if code_lines:
                    recovered_code = "\n".join(code_lines)
                    with open("recovered_original_app.py", "w", encoding="utf-8") as out_f:
                        out_f.write(recovered_code)
                    print("Saved recovered code to recovered_original_app.py!")
                break
        except Exception as e:
            print(f"Error: {e}")

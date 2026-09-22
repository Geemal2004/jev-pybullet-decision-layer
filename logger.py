import json, time, os
PATH = os.path.join(os.path.dirname(__file__), "runs.jsonl")

def log(record):
    record["t"] = time.time()
    with open(PATH, "a") as f:
        f.write(json.dumps(record) + "\n")

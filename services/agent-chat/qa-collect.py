#!/usr/bin/env python3
"""Collect Q&A from L's agent via the haha agent channel.
Reads questions from qa-collect-questions.md, submits them as ha.haha (agentId 30),
polls for answers, saves to qa-library.json (incremental, resumable).

Rate limit: 1 question / 5s per agent. Poll answer up to 60s.
Run on the server (reads Bearer key from /etc/haha/agent-chat.env).
Usage: python3 qa-collect.py [--limit N] [--start N]
"""
import json, os, re, sys, time, urllib.request, urllib.error

BASE = "http://127.0.0.1:8899"
AGENT_ID = 30
NAME = "ha.haha"
AI_ID = "0x17367f0410c1e90ee380b4a47be765a910dbf2be0db717b1da19e1d6f03670ed"
OUT = "/opt/haha-agent-chat/qa-library.json"
QUESTIONS_FILE = "/opt/haha-agent-chat/qa-collect-questions.md"

def load_key():
    with open("/etc/haha/agent-chat.env") as f:
        for line in f:
            if line.startswith("CHANNEL_API_KEY="):
                return line.strip().split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("CHANNEL_API_KEY not found in env")

KEY = load_key()

def req(method, path, body=None):
    r = urllib.request.Request(BASE + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read() or b"{}")
        except Exception: return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}

def load_questions():
    qs = []
    with open(QUESTIONS_FILE) as f:
        for line in f:
            m = re.match(r"^(\d+)\.\s+(.+)$", line.strip())
            if m:
                qs.append((int(m.group(1)), m.group(2).strip()))
    qs.sort()
    return qs

def load_out():
    if os.path.exists(OUT):
        with open(OUT) as f:
            try: return json.load(f)
            except Exception: return {"questions": []}
    return {"questions": []}

def save_out(data):
    tmp = OUT + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, OUT)

def main():
    limit = None; start = 1
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--limit": limit = int(args[i+1])
        if a == "--start": start = int(args[i+1])
    qs = load_questions()
    data = load_out()
    done_ids = {q.get("n") for q in data["questions"]}
    print(f"total questions: {len(qs)}, already done: {len(done_ids)}", flush=True)
    count = 0
    for n, q in qs:
        if n < start: continue
        if limit is not None and count >= limit: break
        if n in done_ids:
            continue
        # submit
        status, resp = req("POST", "/questions", {"agentId": AGENT_ID, "name": NAME, "aiId": AI_ID, "message": q, "lang": "zh"})
        if status != 200:
            print(f"[{n}] submit FAIL {status} {resp} :: {q}", flush=True)
            data["questions"].append({"n": n, "q": q, "status": "submit_fail", "detail": resp})
            save_out(data); count += 1; time.sleep(5); continue
        qid = resp.get("questionId")
        # poll up to 60s
        answer = None
        t0 = time.time()
        while time.time() - t0 < 60:
            s2, r2 = req("GET", f"/questions/{qid}")
            if s2 == 200 and r2.get("status") == "answered":
                answer = r2.get("answer"); break
            if s2 == 404:
                break
            time.sleep(1)
        if answer:
            print(f"[{n}] OK ({time.time()-t0:.0f}s) :: {q} -> {answer[:40]}", flush=True)
            data["questions"].append({"n": n, "q": q, "status": "answered", "answer": answer, "questionId": qid})
        else:
            print(f"[{n}] TIMEOUT :: {q}", flush=True)
            data["questions"].append({"n": n, "q": q, "status": "timeout", "questionId": qid})
        save_out(data)
        count += 1
        time.sleep(5)  # rate limit: 1 question / 5s
    print(f"done this run: {count}, total saved: {len(data['questions'])}", flush=True)

if __name__ == "__main__":
    main()

"""Stand-in for agy in tests: reads the brief path from -p, writes whatever that job must output.
FAKE_QUOTA_AFTER=N makes call N+1 onward fail like a quota error (stderr, no outputs, exit 0)."""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skills", "gemini-arena"))
import bracket as B  # noqa: E402

msg = sys.argv[-1]
path = re.search(r"Read (.+?) and follow", msg).group(1)
d = os.path.dirname(os.path.dirname(os.path.dirname(path)))

limit = os.environ.get("FAKE_QUOTA_AFTER")
if limit is not None:
    counter = os.path.join(d, "fake_calls")
    n = int(open(counter).read()) if os.path.exists(counter) else 0
    open(counter, "w").write(str(n + 1))
    if n >= int(limit):
        sys.stderr.write('AGY_ERROR: {"short_error":"RESOURCE_EXHAUSTED (code 429)"}\n')
        sys.exit(0)

state = B.load_state(type("A", (), {"dir": d})())
job = next(j for ph in B.PHASES for j in B.phase_jobs(state, ph) if j["prompt"] == path)
box = {k: 9 for k in ("correctness", "completeness", "specificity", "robustness", "clarity")}
low = dict(box, correctness=4)
for out in job["outputs"]:
    os.makedirs(os.path.dirname(out), exist_ok=True)
    kind = job["kind"]
    if kind == "judge":
        a, b = job["a"], job["b"]  # first listed side always wins: deterministic
        body = json.dumps({"match": job["match"], "scores": {a: dict(box, fatal=False), b: dict(low, fatal=False)},
                           "winner": a, "reason": "fake", "survived": ["x"], "standing": {a: [], b: ["y"]}})
    elif kind == "final":
        body = json.dumps({"scores": {"X": dict(box, fatal=False), "Y": dict(low, fatal=False)},
                           "winner": "X", "reason": "fake", "fixed": []})
    elif kind == "attacker":
        body = "ATTACK 1 [MINOR] fake\nWhere: -\nProblem: fake\n"
    else:
        body = "fake %s output for %s\n" % (kind, os.path.basename(out))
    open(out, "w", encoding="utf-8").write(body)
print(json.dumps({"status": "SUCCESS", "response": "ok"}))

#!/usr/bin/env python3
"""drive.py: runs a gemini-arena tournament on Antigravity CLI (agy), outside Claude's context.

    drive.py init --slug S [--agents 4 | --quick] [--seed N] --task-file F [--baseline-file F]
    drive.py run  --slug S [--jobs 3] [--claude-judge-alive 4]

Uses bracket.py (the unchanged state machine) as a library. `run` loops spawn, attack, defend,
judge, collect, advance until a champion exists. State lives on disk, so it resumes any time.

Exit codes: 0 done, 3 Claude must judge (briefs listed), 4 quota/rate limit, 5 hard failure.
Python 3.8+, standard library only.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import bracket as B

ROOT = os.path.abspath(os.environ.get("AGY_WORK_ROOT", os.path.join(os.path.expanduser("~"), "gemini-work")))
# AGY_CMD (JSON list) overrides the agy command; tests use it to swap in a fake agy.
AGY_CMD = json.loads(os.environ["AGY_CMD"]) if os.environ.get("AGY_CMD") else [
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "agy", "bin", "agy.exe") if os.name == "nt" else "agy"]
JOB_TIMEOUT_S = 15 * 60
QUOTA_RE = re.compile(r"RESOURCE_EXHAUSTED|\b429\b|quota|rate.?limit|exhausted", re.I)
SAFE_SLUG = re.compile(r"^[A-Za-z0-9._-]+$")


def run_dir(slug):
    if not SAFE_SLUG.match(slug):
        raise B.ArenaError("slug may only contain letters, digits, . _ -")
    return os.path.join(ROOT, "arena", slug)


def say(msg):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


def run_one(d, job, stop):
    """One agy job. Output goes to files, not pipes (agy print mode can be silent on a pipe)."""
    if stop["quota"]:
        return
    logs = os.path.join(d, "logs")
    os.makedirs(logs, exist_ok=True)
    out_p, err_p = (os.path.join(logs, job["id"] + ext) for ext in (".json", ".err"))
    msg = "Read %s and follow it exactly. It is your whole brief." % job["prompt"]
    cmd = AGY_CMD + ["--output-format", "json", "--dangerously-skip-permissions",
                     "--print-timeout", "10m", "-p", msg]
    with open(out_p, "w") as out, open(err_p, "w") as err:
        try:
            subprocess.run(cmd, cwd=d, stdin=subprocess.DEVNULL, stdout=out, stderr=err, timeout=JOB_TIMEOUT_S)
        except (subprocess.TimeoutExpired, OSError) as e:
            err.write("driver: %s\n" % e)
    if B.missing_jobs([job]):
        with open(err_p, encoding="utf-8", errors="replace") as fh:
            if QUOTA_RE.search(fh.read()):
                stop["quota"] = True


def run_jobs(d, jobs, workers):
    stop = {"quota": False}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for f in [pool.submit(run_one, d, j, stop) for j in jobs]:
            f.result()
    return stop["quota"]


def claude_judging(state, phase, limit):
    if phase == "final":
        return True
    rd = B.current_round(state)
    return phase == "judge" and rd is not None and len(rd["alive"]) <= limit


def run(args):
    d = run_dir(args.slug)
    while True:
        state = B.load_state(argparse.Namespace(dir=d))
        phase, left, jobs = B.next_action(state)
        if phase == "done":
            say("DONE. python \"%s\" winner --dir \"%s\"" % (B.SELF, d))
            return 0
        if phase in ("collect", "advance"):
            if phase == "collect":
                results = B.collect(state)
                for mid, what, note in results:
                    if what != "recorded":
                        say("verdict %s %s %s" % (mid, what, note))
            else:
                rd = B.current_round(state)
                survivors = B.advance(state)
                say("round %d done: %d of %d left" % (rd["n"], len(survivors), len(rd["alive"])))
            B.save_state(state)
            continue
        jobs = B.write_prompts(state, phase)
        if claude_judging(state, phase, args.claude_judge_alive):
            say("CLAUDE JUDGES NEEDED: %d brief(s). Each brief writes its own verdict file." % len(B.missing_jobs(jobs)))
            for j in B.missing_jobs(jobs):
                print("  %s  %s" % (j["id"], j["prompt"]), flush=True)
            say("then run the same `run` command again")
            return 3
        # judges get 3 passes, everything else 2 (a second pass, then NO OUTPUT per bracket rules)
        for attempt in range(3 if phase == "judge" else 2):
            left = B.missing_jobs(jobs)
            if not left:
                break
            say("%s: running %d job(s) on agy (%d at a time)%s"
                % (phase, len(left), args.jobs, "" if attempt == 0 else ", retry"))
            if run_jobs(d, left, args.jobs):
                say("QUOTA/RATE LIMIT from agy. Stopped; state is saved. Resume later with the same `run` command.")
                return 4
        left = B.missing_jobs(jobs)
        if left and phase == "judge":
            say("HARD FAILURE: judge(s) failed 3 times: %s (see %s)" % (", ".join(j["id"] for j in left), os.path.join(d, "logs")))
            return 5
        for j in left:  # missing attack counts as no attacks, missing solution loses its match
            for p in j["outputs"]:
                if not os.path.isfile(p) or os.path.getsize(p) == 0:
                    with open(p, "w", encoding="utf-8") as fh:
                        fh.write("NO OUTPUT\n")
            say("job %s produced nothing twice: wrote NO OUTPUT" % j["id"])


def init(args):
    d = run_dir(args.slug)
    argv = ["init", "--dir", d, "--wave", "3", "--task-file", args.task_file]
    argv += ["--quick"] if args.quick else ["--agents", str(args.agents)]
    if args.seed is not None:
        argv += ["--seed", str(args.seed)]
    if args.baseline_file:
        argv += ["--baseline-file", args.baseline_file]
    return B.main(argv)


def main(argv=None):
    p = argparse.ArgumentParser(prog="drive.py", description="Run gemini-arena on agy.")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("init")
    s.add_argument("--slug", required=True)
    s.add_argument("--agents", type=int, default=4)  # each job is ~250k Gemini tokens and ~6 min
    s.add_argument("--quick", action="store_true")
    s.add_argument("--seed", type=int)
    s.add_argument("--task-file", required=True)
    s.add_argument("--baseline-file")
    s.set_defaults(func=init)
    s = sub.add_parser("run")
    s.add_argument("--slug", required=True)
    s.add_argument("--jobs", type=int, default=3)
    s.add_argument("--claude-judge-alive", type=int, default=4,
                   help="rounds that start with this many alive or fewer, and the final, are judged by Claude")
    s.set_defaults(func=run)
    args = p.parse_args(argv)
    try:
        return args.func(args)
    except B.ArenaError as e:
        print("error: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

---
name: gemini-arena
description: >-
  Tournament of Gemini agents over one task (port of arena-skill, runs on the user's
  Google AI Pro login through Antigravity CLI, not on Claude limits). Default 4
  competitors, each gets the same task plus a different strategy card; they attack and
  defend each other's solutions in a single-elimination bracket; Gemini judges the early
  rounds and Claude judges only the semi-finals and the final. Use when the user says
  "gemini arena", "arena", asks to make Gemini versions compete, or is unhappy with an
  answer and wants the best of many attempts without spending Claude limits.
argument-hint: "[--agents N | --quick] [--seed S] <task>"
---

# gemini-arena

Same tournament as https://github.com/Jakeschincariol/arena-skill (MIT, see `LICENSE-arena-skill`),
but the competitors, attackers, defenders and early judges are Gemini processes (`agy`), driven by
`drive.py`, so almost nothing runs through your own context. `bracket.py` (state machine),
`strategies.json` and `rubric.md` are unchanged from the original. You are the orchestrator: you
write the task, start the driver, judge the last rounds, and report.

What the user typed after the skill name: `$ARGUMENTS`. If blank, take the task from the conversation.

## Paths and tools

- Skill folder: the "Base directory for this skill" printed at the top. Below `SKILL` means it.
- Run the driver somewhere that can see the user's agy login. A sandboxed Bash cannot (observed in the
  Claude desktop app: its sandbox did not see the user's AppData); there, use the terminal tool
  (`mcp__terminal__run_in_terminal`, then `read_terminal` with `wait_for_output_ms` to watch). In plain
  Claude Code a normal Bash call works. Long runs: start in the background and poll.
- `WORK_ROOT` is `AGY_WORK_ROOT`, default `~/gemini-work`. Runs live in `WORK_ROOT/arena/<slug>/`.
  Gemini runs with auto-approve, so it must stay there. Never point a run elsewhere.
- Put the task file anywhere you can write (for example `.arena-input/task.md` in the current
  project, git-ignored) and give its path to `init`. The driver copies it into the run folder.

## Step 1: size it

| flag | meaning |
| --- | --- |
| `--agents N` | N competitors. **Default 4**, `--agents 2` is the cheapest (1 round, 7 jobs). |
| `--quick` | 16 competitors. |
| `--seed S` | Fixes cards and pairings. |

**Cost is real.** Measured: each Gemini job is about 250k tokens and 6 minutes. 4 agents = 19 jobs =
about 5M tokens, ~40 min. 8 agents = 43 jobs, 16 agents = 91 jobs, 100 agents = 595 jobs. The user
asked to keep it small: use the default 4 unless the user names a bigger number, and for anything
above 4 agents ask once before starting. Run `python SKILL\bracket.py plan --agents N --wave 3`, tell
the user in one line ("4 agents, 2 rounds, 19 Gemini jobs, ~40 min"), and start.

## Step 2: write the task file

Sub-agents cannot see this conversation. Write the task file so it stands alone:
the user's request in their words, every requirement and constraint, absolute paths of files that
matter, what done looks like. Do not add requirements the user never gave and do not push your own
answer into it. If there is an answer the user rejected, write it word for word to
`baseline.md` next to the task file.

## Step 3: init and drive

```text
python SKILL\drive.py init --slug <short-name> --agents 4 --task-file <path to task.md>
python SKILL\drive.py run --slug <short-name>
```

Add `--baseline-file ...\baseline.md` and `--seed S` to `init` when needed. `run` loops by itself:
spawn, then per round attack, defend, judge, collect, advance, with 3 agy jobs at a time. It prints
one line per phase. Watch it with `read_terminal`; give the user one line per finished round, nothing
more. Never paste solutions, attacks or verdicts into the chat.

`run` exits with a code:

| exit | meaning | you do |
| --- | --- | --- |
| 0 | DONE, champion exists | step 5 |
| 3 | `CLAUDE JUDGES NEEDED` (semi-finals / final) | step 4 |
| 4 | quota or rate limit (429, RESOURCE_EXHAUSTED) | stop. State is on disk. Tell the user, resume with the same `run` command later (next day). Do not retry in a loop. |
| 5 | a judge failed three times, or a hard error | show the last driver lines to the user |

If the user says stop, close the terminal tab; `run` resumes from disk any time.

## Step 4: Claude judges (exit 3)

The driver printed the judge brief paths. For each, spawn one `general-purpose` Agent
(`run_in_background: false`, up to 3 in one message): prompt
`Read <brief path> and follow it exactly. It is your whole brief.` The brief tells it where to write the
verdict JSON. Do not judge by reading solutions in your own context and never pick a winner yourself.
Then run the same `drive.py run --slug ...` again. It collects the verdicts and continues. If an agent
cannot write to `WORK_ROOT` because of permissions, ask the user to allow that folder for the session.

## Step 5: the result

```text
python SKILL\bracket.py winner --dir WORK_ROOT/arena/<slug>
```

(`drive.py run` prints the exact `winner` command at the end.) Read the champion's solution file, the
only solution you read. Give the user: the winning solution in full; why it won (attacks it survived,
its card on one line); rounds ("2 rounds, 4 agents in, 1 left"); if there was a baseline, the final
check's scores honestly, even if the old answer won; where the run folder is. If the solution changes
the user's project files, do not apply it: ask.

## Rules

- You run the tournament; you never compete, attack or judge, except the Claude judging in step 4.
- Every brief is byte for byte the same task for every agent. Never hint to one agent.
- Do not read solutions, attacks or verdicts during the run. State is on disk: `bracket.py status`.
- Gemini agents only write inside the run folder. If something else changed, tell the user.
- Quota exhausted means stop and wait. Never loop retries against a rate limit.

## The prompt templates

`bracket.py` fills these in (the `{{placeholders}}`) and writes one brief per job. Never edit a brief
for a single agent. The text below is read by `bracket.py` itself: keep every template block intact.

### Competitor, in the spawn phase

<!-- template:competitor -->
```text
You are competitor {{agent}} in an arena of {{n}}. All {{n}} competitors got the exact same task, word for word. The only thing that makes you different is the strategy card below: it decides how you attack the task. Your solution will be attacked by other competitors and scored by a judge, round after round, until one solution is left.

=== THE TASK (identical for every competitor) ===
{{task}}
=== END OF THE TASK ===

{{baseline_note}}

=== YOUR STRATEGY CARD ===
Reasoning mode: {{reasoning_name}}. {{reasoning_how}}
Workflow: {{workflow_name}}. {{workflow_how}}
Strategy: {{strategy_name}}. {{strategy_how}}
=== END OF THE CARD ===

How to work:
1. Use the card for real. Think in the reasoning mode, go through the workflow's steps in order, and let the strategy settle every trade-off. A generic answer with the card's name on top will lose.
2. Meet every requirement the task states. The judge scores you against the task, not against your card.
3. You cannot ask the user anything. Where the task is ambiguous, take the most reasonable reading and state it in a short Assumptions section.
4. Expect attacks: concrete flaws, counterexamples, missed requirements. Close those holes before you submit.
5. Do not create, edit or delete anything outside {{arena_dir}}. Read whatever the task points to. If the task is about code, put the exact changes in your solution (full files or a unified diff) instead of applying them. If your workflow needs scratch space, use {{arena_dir}}/scratch/{{agent}}/.

Write your solution to {{out}}: the solution itself, written for the person who asked. Leave out your drafts and your working. Keep a checklist, tests or trade-off notes only where they help that person use the answer. Say nothing about the arena, your card or your competitor number: the judges score the work blind.

When the file is written, reply with this one line and nothing else:
DONE {{agent}} <number of words in your solution>
```
<!-- /template:competitor -->

### Attacker, in every round

<!-- template:attacker -->
```text
You are competitor {{agent}} in round {{round}} of an arena, match {{match}}. Your opponent is {{target}}. Only one of you gets out of this match. Right now your job is to attack your opponent's solution.

=== THE TASK (identical for every competitor) ===
{{task}}
=== END OF THE TASK ===

Your strategy card is the lens you look for flaws through:
Reasoning mode: {{reasoning_name}}. {{reasoning_how}}
Workflow: {{workflow_name}}. {{workflow_how}}
Strategy: {{strategy_name}}. {{strategy_how}}

Read your opponent's solution: {{target_solution}}
You may read your own for comparison: {{own_solution}}. Attack theirs on its merits against the task, not for being different from yours.

Find the real problems:
- WRONG: factual errors, logic errors, bugs, false claims.
- MISSING: a requirement the task states that it skips or only half meets. Quote the requirement.
- BREAKS: a concrete input, scenario or edge case where it fails. Give the exact counterexample.
- VAGUE: a place where the user could not act on it without guessing.

Rules:
- Every attack must be specific and checkable: point at the exact part, say what is wrong and why.
- No praise, no summary, and no style nitpicks unless they stop the user from using it.
- Do not invent requirements the task does not state. Do not attack the approach, only what it gets wrong.
- At most 7 attacks, strongest first. If you only find 2 real ones, write 2.
- Label each FATAL (wrong or unusable for the task), MAJOR (a real gap) or MINOR.
- Do not create, edit or delete any file except the one below.

Write the attacks to {{out}} in this format:
ATTACK 1 [FATAL|MAJOR|MINOR] <one-line title>
Where: <quote or location>
Problem: <what is wrong, with the counterexample or the missed requirement>
(and the same for each attack after that)

When the file is written, reply with this one line and nothing else:
ATTACKED {{target}} <number of attacks> (<number that are FATAL> fatal)
```
<!-- /template:attacker -->

### Defender, in every round

<!-- template:defender -->
```text
You are competitor {{agent}} in round {{round}} of an arena, match {{match}}. Your opponent {{attacker}} has attacked your solution. Now you defend it and revise it. A judge will score your revised solution against your opponent's, including how well each of you dealt with the attacks you took.

=== THE TASK (identical for every competitor) ===
{{task}}
=== END OF THE TASK ===

Your strategy card. Keep your approach: it is why you are still here.
Reasoning mode: {{reasoning_name}}. {{reasoning_how}}
Workflow: {{workflow_name}}. {{workflow_how}}
Strategy: {{strategy_name}}. {{strategy_how}}

Your current solution: {{own_solution}}
The attacks against it: {{attacks}}

Do this:
1. Take every attack in turn and decide honestly. CONCEDE if it is right, and fix it. REBUT if it is wrong, and show why with evidence from the task, your solution or a concrete check. A rebuttal that only insists you are right counts as a concession. Conceding a real flaw and fixing it scores better than defending it.
2. Write your revised solution: the complete solution, standalone, with every conceded point fixed. The judge reads only this file, so never write "see the previous version". Say nothing about the arena or your card.
3. Fix what was attacked and anything the attacks made you notice. Do not start again from scratch and do not copy your opponent.
4. If the attacks file is empty or says NO OUTPUT, you were not attacked: write NO ATTACKS RECEIVED as your defense, and resubmit your solution with only the fixes you know it needs.
5. Do not create, edit or delete anything outside {{arena_dir}}.

Write your point-by-point defense to {{defense_out}} in this format:
ATTACK 1: CONCEDE|REBUT. <one to three lines>
(one entry per attack)

Write your revised solution to {{solution_out}}.

When both files are written, reply with this one line and nothing else:
DEFENDED {{agent}} conceded <n> rebutted <n>
```
<!-- /template:defender -->

### Judge, one per match

<!-- template:judge -->
```text
You are the judge of match {{match}}, round {{round}}, in an arena. Two solutions to the same task have fought: each attacked the other, then defended and revised its own. Score both against the rubric. The one with the higher score goes through and the other is eliminated.

=== THE TASK (identical for every competitor) ===
{{task}}
=== END OF THE TASK ===

Read the rubric first: {{rubric}}

Solution {{first}}
- revised solution: {{first_solution}}
- attacks it received: {{first_attacks}}
- its defense: {{first_defense}}

Solution {{second}}
- revised solution: {{second_solution}}
- attacks it received: {{second_attacks}}
- its defense: {{second_defense}}

How to judge:
1. Read both revised solutions in full before you score either one.
2. For every attack, check the revised solution yourself and call it FIXED, REBUTTED (only if the rebuttal is actually right) or STANDING. A defense that says "fixed" is not proof. Look.
3. Look for flaws the attackers missed, too.
4. Score each criterion from 0 to 10 using the rubric's anchors. Set fatal to true only for a flaw you have verified that makes the solution wrong or unusable for the task.
5. The winner is the higher weighted total (the weights are in the rubric). A fatal solution cannot beat one that is not fatal. On an exact tie, fewer standing attacks wins, then higher correctness.
6. Judge the work, not the writing about the work. Length is not quality. You do not know either competitor's strategy and should not guess it.
7. Do not create, edit or delete any file except the verdict. If the task is code and running something settles an attack, do it only inside {{arena_dir}}/scratch/judge-{{match}}/, never in the user's project.

Write this JSON, and nothing else, to {{out}}:
{
  "match": "{{match}}",
  "scores": {
    "{{first}}": {"correctness": 0, "completeness": 0, "specificity": 0, "robustness": 0, "clarity": 0, "fatal": false},
    "{{second}}": {"correctness": 0, "completeness": 0, "specificity": 0, "robustness": 0, "clarity": 0, "fatal": false}
  },
  "winner": "{{first}} or {{second}}",
  "reason": "one sentence: the decisive difference",
  "survived": ["each attack the winner took and beat, in a few words"],
  "standing": {"{{first}}": ["attacks still standing"], "{{second}}": ["attacks still standing"]}
}

When the file is written, reply with this one line and nothing else:
WINNER <winner id> <winner total>-<loser total>
```
<!-- /template:judge -->

### Final check, only when there is an answer to beat

<!-- template:final -->
```text
You are the final check in an arena. {{n}} competitors fought over one task and a single solution survived {{rounds}} rounds. Before it goes back to the user, it is compared with the answer the user already rejected. You are not told which of the two is which. Score what is in front of you. Either one can win.

=== THE TASK ===
{{task}}
=== END OF THE TASK ===

Read the rubric first: {{rubric}}

Solution X: {{x_solution}}
Solution Y: {{y_solution}}

How to judge:
1. Read both in full before you score either.
2. Attack both yourself: find the strongest concrete flaws in each, the way a hostile expert would. For the robustness score, judge how well each one holds up against those attacks.
3. Score each criterion from 0 to 10 using the rubric's anchors. Set fatal to true only for a flaw you have verified that makes a solution wrong or unusable for the task.
4. The winner is the higher weighted total. A fatal solution cannot beat one that is not fatal.
5. Judge the work, not the writing about the work. Length is not quality.
6. Do not create, edit or delete any file except the verdict.

Write this JSON, and nothing else, to {{out}}:
{
  "scores": {
    "X": {"correctness": 0, "completeness": 0, "specificity": 0, "robustness": 0, "clarity": 0, "fatal": false},
    "Y": {"correctness": 0, "completeness": 0, "specificity": 0, "robustness": 0, "clarity": 0, "fatal": false}
  },
  "winner": "X or Y",
  "reason": "one sentence: the decisive difference",
  "fixed": ["each thing the winner gets right that the other gets wrong, in a few words"]
}

When the file is written, reply with this one line and nothing else:
FINAL <X or Y> <X total>-<Y total>
```
<!-- /template:final -->

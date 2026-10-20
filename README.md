# gemini-arena-skill

English first, Russian below / Русская версия ниже.

## English

A Claude Code skill that runs a tournament of Gemini agents over one task and returns the best
answer. It is a port of [arena-skill](https://github.com/Jakeschincariol/arena-skill) by Jake
Schincariol (MIT) that runs the competitors on Gemini through the Antigravity CLI (`agy`) instead of
on Claude sub-agents, so the heavy work does not spend your Claude limits. It is a companion to
[agy-gemini-mcp](https://github.com/velime/agy-gemini-mcp) (the same `agy` login), but it does not need
the MCP server to run.

How it works: N competitors each get the same task and a different strategy card, then fight in a
single-elimination bracket: they attack each other's solutions, defend and revise, and a judge scores
them against a rubric until one survives. `bracket.py`, `strategies.json` and `rubric.md` are
unchanged from the original. What is new:

- `drive.py` runs the whole tournament outside Claude's context: it starts 3 `agy` jobs at a time,
  moves through spawn, attack, defend, judge, collect and advance by itself, and writes everything to
  disk, so a run can be resumed at any time.
- Gemini judges the early rounds. Claude judges only the semi-finals and the final (the driver stops
  and hands those briefs to Claude), which keeps Claude's usage small.
- If agy reports a quota or rate limit (429, RESOURCE_EXHAUSTED), the driver stops immediately and keeps
  the state. Resume the next day with the same command.
- The default is 4 agents, because a Gemini job is expensive.

Measured cost (our runs): about 250k tokens and 4 to 6 minutes per Gemini job. 2 agents is 7 jobs
(6 on Gemini, 1 judged by Claude), 4 agents is 19 jobs, 8 agents is 43, 16 agents is 91, 100 agents is
595. A 2-agent run took about 14 minutes and about 1.1M Gemini tokens; Claude judging that one match
cost about 78k tokens.

### Install

Requirements: Python 3.8+, `agy` installed and signed in (see the setup in
[agy-gemini-mcp](https://github.com/velime/agy-gemini-mcp)). Copy `skills/gemini-arena` into
`.claude/skills/` of your project or `~/.claude/skills/`. Then ask Claude to run the skill with a task.
Tested on Windows 11 with Python 3.13 and Antigravity CLI 1.4.2; the upstream `bracket.py` declares
Python 3.8+, which we did not run. Linux and macOS are not tested. The final check against a rejected
answer (`--baseline-file`) is covered only by the offline tests, not by a real Gemini run.

Manual use without Claude:

```bash
python skills/gemini-arena/drive.py init --slug demo --agents 2 --task-file task.md
python skills/gemini-arena/drive.py run --slug demo
```

Runs live under `AGY_WORK_ROOT` (default `~/gemini-work`) in `arena/<slug>/`. Exit codes of `run`:
0 done, 3 Claude must judge, 4 quota or rate limit, 5 hard failure.

### Tests

```bash
python -m unittest discover -s tests
```

31 tests, no network: the upstream bracket tests plus end-to-end tests of the driver against a fake
`agy` (full run, Claude-judge handoff and resume, quota stop and resume, path escape).

### Risks

`agy` runs with `--dangerously-skip-permissions` (auto-approve). The skill tells agents to write only
inside the run folder, but nothing enforces it; use a work root away from anything important. The same
account, region and terms-of-service risks as in agy-gemini-mcp apply. Provided as is, no warranty.
Not affiliated with Google or Anthropic.

## Русский

Скилл для Claude Code: турнир агентов Gemini над одной задачей, на выходе лучший ответ. Это порт
[arena-skill](https://github.com/Jakeschincariol/arena-skill) Jake Schincariol (MIT), в котором
конкуренты работают на Gemini через Antigravity CLI (`agy`), а не на субагентах Claude, поэтому
тяжёлая работа не тратит лимиты Claude. Парный проект к
[agy-gemini-mcp](https://github.com/velime/agy-gemini-mcp) (тот же вход в `agy`), но для работы MCP-сервер
не нужен.

Как это работает: N конкурентов получают одну и ту же задачу и разные карточки стратегий, затем
играют в турнире на вылет: атакуют решения друг друга, защищаются и дорабатывают, судья ставит оценки
по рубрике, пока не останется один. `bracket.py`, `strategies.json` и `rubric.md` взяты из оригинала
без изменений. Что добавлено:

- `drive.py` проводит весь турнир вне контекста Claude: запускает по 3 задачи `agy` одновременно,
  сам проходит фазы spawn, attack, defend, judge, collect и advance, всё пишет на диск, поэтому прогон
  можно возобновить в любой момент.
- Ранние раунды судит Gemini. Claude судит только полуфиналы и финал (драйвер останавливается и отдаёт
  эти брифы Claude), поэтому расход Claude небольшой.
- Если `agy` сообщает о квоте или лимите запросов (429, RESOURCE_EXHAUSTED), драйвер сразу
  останавливается и сохраняет состояние. На следующий день продолжите той же командой.
- По умолчанию 4 агента, потому что задача Gemini дорогая.

Измеренная стоимость (наши запуски): около 250 тысяч токенов и 4-6 минут на одну задачу Gemini. 2
агента это 7 задач (6 у Gemini, 1 судит Claude), 4 агента 19, 8 агентов 43, 16 агентов 91, 100 агентов
595. Прогон на 2 агентов занял около 14 минут и около 1,1 млн токенов Gemini; судейство этого одного
матча Claude стоило около 78 тысяч токенов.

### Установка

Нужны: Python 3.8+, установленный и авторизованный `agy` (см. установку в
[agy-gemini-mcp](https://github.com/velime/agy-gemini-mcp)). Скопируйте `skills/gemini-arena` в
`.claude/skills/` проекта или в `~/.claude/skills/`. Затем попросите Claude запустить скилл с задачей.

Вручную без Claude:

```bash
python skills/gemini-arena/drive.py init --slug demo --agents 2 --task-file task.md
python skills/gemini-arena/drive.py run --slug demo
```

Прогоны лежат в `AGY_WORK_ROOT` (по умолчанию `~/gemini-work`) в `arena/<slug>/`. Коды выхода `run`:
0 готово, 3 должен судить Claude, 4 квота или лимит запросов, 5 серьёзный сбой.

### Тесты

```bash
python -m unittest discover -s tests
```

31 тест без сети: тесты `bracket.py` из оригинала плюс сквозные тесты драйвера с поддельным `agy`
(полный прогон, передача судейства Claude и возобновление, остановка по квоте и возобновление, выход
за пределы папки).

### Риски

`agy` запускается с `--dangerously-skip-permissions` (автоподтверждение). Скилл велит агентам писать
только внутри папки прогона, но ничто этого не гарантирует; держите рабочий корень подальше от важного.
Те же риски аккаунта, региона и условий использования, что и в agy-gemini-mcp. Предоставляется «как
есть», без гарантий. Проект не связан с Google и Anthropic.

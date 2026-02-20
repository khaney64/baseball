# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is an **OpenClaw skill** for MLB baseball game tracking. It fetches real-time game data from the MLB Stats API — schedules, live game status, and box scores. The skill manifest is in `SKILL.md`.

## Architecture

```
baseball/
  SKILL.md          — Skill manifest (frontmatter + docs)
  CLAUDE.md         — This file
  PLAN.md           — Implementation guide
  mlb.py            — Legacy MLB API client (uses requests, dateutil)
  gameday.py        — Legacy LED cube display driver (imports mlb.py)
  scripts/
    baseball.py     — Main skill entry point (argparse subcommands)
    mlb_api.py      — Clean MLB API client (stdlib only)
```

### OpenClaw Skill (`scripts/`)

The skill entry point is `scripts/baseball.py` with subcommands `games`, `live`, and `score`. It imports from `scripts/mlb_api.py`, which is a clean rewrite of the MLB API client using only the Python standard library.

```bash
# List today's games
python scripts/baseball.py games

# Live game status by team abbreviation
python scripts/baseball.py live PHI

# Box score
python scripts/baseball.py score 718415
```

### Legacy Files (root)

- **`mlb.py`** — Original MLB Stats API client. Uses `requests` and `python-dateutil`. Has known bugs (see PLAN.md). Kept for backward compatibility with `gameday.py`.
- **`gameday.py`** — LED display driver that imports root `mlb.py`. Maps game state to LED coordinates on a 9x9x9 cube. Requires AbstractFoundry Daemon runtime on a Raspberry Pi.

## Key API

- MLB Schedule: `https://statsapi.mlb.com/api/v1/schedule/games?sportId=1&date={date}`
- MLB Live Feed: `https://statsapi.mlb.com/api/v1.1/game/{gamePk}/feed/live`
- Copyright info: `http://gdx.mlb.com/components/copyright.txt`

## Dependencies

- **scripts/** — Standard library only (`urllib.request`, `json`, `argparse`, `datetime`)
- **Legacy** — `requests`, `python-dateutil`, AbstractFoundry Daemon runtime

## Notes

- Do not modify `mlb.py` or `gameday.py` without considering that `gameday.py` imports from root `mlb.py`.
- Be mindful of MLB API rate limits — avoid polling more frequently than every 15 seconds.
- The `scripts/mlb_api.py` schedule function does NOT call the live feed per game (unlike the legacy `mlb.py`), avoiding N+1 API calls.

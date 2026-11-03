# dota-coach

Discord bot that reviews Dota 2 matches. Python computes every number (`metrics.py`); the LLM only interprets them.

## Commands (Phase 1)
- `/link <steam_id>`: store your Steam ID (32-bit or 64-bit). Enable **Expose Public Match Data** in Dota 2 Settings > Options > Social.
- `/review <match_id> [player]`: `player` = account id or hero name. Defaults to your linked account.
- `/lastmatch`: review your most recent match.

Unparsed matches: the bot requests a parse on OpenDota; retry in a few minutes. Reviews are saved in `dota_coach.db` (table `reviews`).

## Setup
1. **Discord app**: https://discord.com/developers/applications > New Application > name it.
2. **Bot**: Bot tab > Reset Token > copy into `DISCORD_TOKEN`. No privileged intents needed.
3. **Invite**: OAuth2 > URL Generator > scopes `bot` + `applications.commands` > permissions `Send Messages` > open the URL, pick your server.
4. **LLM key**: create a key at https://platform.deepseek.com > `LLM_API_KEY`.
5. Install and configure:
   ```bash
   uv venv --python 3.12 && uv pip install -e '.[dev]'   # or python3.11+ -m venv .venv && pip install -e '.[dev]'
   cp .env.example .env   # fill in values
   ```
6. Run: `.venv/bin/python -m dota_coach.bot` (slash commands sync on startup; may take a minute to show up).
7. Tests: `.venv/bin/pytest`

## Swapping LLM
Edit `.env` only: `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`. Any OpenAI-compatible endpoint works (Claude via an OpenAI-compatible gateway, OpenRouter, etc.). Check https://api-docs.deepseek.com for current DeepSeek model names.

## Layout
`bot.py` commands, `opendota.py` API client, `metrics.py` pure calculations, `llm.py` `ask(messages, tools=None)`, `prompts.py`, `db.py`.
Later phases slot in as new modules (e.g. `draft.py`, `team.py`) plus commands in `bot.py`; `reviews.metrics` is stored as JSON for pattern tracking.

## Notes
- Public match data only. No hidden enemy info.
- Core items = purchases costing >= 2000 gold; compared via OpenDota per-player benchmark percentiles (GPM, XPM, LH/min, hero damage/min). OpenDota `/benchmarks` has no item timings.
- Lane result: net worth diff vs same-lane enemy at 10:00 (+-300 threshold).

## /draft (phase 2)
`/draft enemy:"dp, pudge" pool:"od, lina"` ranks your pool by bracket win rate (OpenDota heroStats, 7-day window) + shrunk matchup edge + shrunk personal record. Patch notes for changed heroes come from `data/patch_notes.md`; regenerate with `python -m dota_coach.patch 7.41f`. CLI: `python -m dota_coach.cli --draft "dp" --pool "od,lina" --account <id>`.

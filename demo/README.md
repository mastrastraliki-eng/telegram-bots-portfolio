# demo/

Offline end-to-end scenarios and the screenshot pipeline.

- `simulator.py` — a fake Telegram Bot API session: runs the real aiogram dispatcher, records every
  message/edit the bot makes and lets a script send texts, tap inline buttons and share contacts.
- `scenario_*.py` — one per bot; each drives a full conversation and asserts on the replies.
  `scenario_ai.py` replaces the Claude call with a stub, so it needs no API key.
- `render.py` + `screenshot.mjs` — turn the recorded chats into Telegram-style PNGs in `docs/screenshots/`.

Run everything: `./demo/run_all.sh` (Python deps from the bots' requirements, plus Node.js with Playwright).

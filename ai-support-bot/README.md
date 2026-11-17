# AI support bot

A customer support assistant for Telegram. It answers questions about the business 24/7 using only
the company's own knowledge base, and passes anything it can't handle to a human operator, who
replies right from Telegram.

Runs on any of three AI backends, switched with one setting:
- **Google Gemini** (default): has a free tier, the key takes a minute to get
- **Free local model via [Ollama](https://ollama.com)** (Qwen, Llama, Mistral…): no API key, no cost per message,
  customer data never leaves your server
- **Claude API**: the best answer quality, for businesses that want premium support

The demo is set up for a fictional coffee roastery, "Brew Lab Coffee" — swap the knowledge file to
use it for any business.

## Features

- Answers grounded in [`knowledge/brewlab.md`](knowledge/brewlab.md): prices, delivery, returns,
  subscriptions, opening hours. The model is told not to invent anything that isn't there.
- Remembers the conversation (last 20 messages per user) so follow-up questions work
- Quick-topic buttons on `/start`, `/reset` to clear the chat
- Replies in the customer's language
- **Human hand-off**: when the question is about a specific order, a refund, an upset customer, or
  something outside the knowledge base, the bot offers "Talk to a human". The operator gets the
  recent conversation in a support chat and answers by simply *replying* to that message; the
  customer receives the answer from the bot.
- Cost-aware on Claude: the knowledge base is a cached prompt prefix, so follow-up questions are cheap,
  and effort is set to `low`, which is enough for FAQ-style answers
- Resilient: an unreachable model, rate limits or network errors get a friendly message; on Claude, if the
  model declines a request the API falls back to another model and the customer is offered a human
- One answer at a time per user, so fast double messages don't produce duplicate replies

## Setup

**Free setup with Gemini** (default)

1. Get a free API key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).
2. Configure and run:

```bash
cp .env.example .env            # fill in BOT_TOKEN, GEMINI_API_KEY and SUPPORT_CHAT_ID
pip install -r requirements.txt
python -m app.main
```

Note: on Google's free tier, prompts may be used to improve Google's products and there are rate
limits; for a business with real customer data, use a paid Gemini plan, Claude, or local Ollama.

**Free and fully local with Ollama** (set `AI_PROVIDER=ollama`)

```bash
# 1. Install Ollama from https://ollama.com, then download a model (≈4.7 GB):
ollama pull qwen2.5:7b          # on a weaker PC: qwen2.5:3b
# 2. In .env set AI_PROVIDER=ollama, then run the bot
cp .env.example .env
pip install -r requirements.txt
python -m app.main
```

**With Claude:** set `AI_PROVIDER=claude` and `ANTHROPIC_API_KEY` (from
[console.anthropic.com](https://console.anthropic.com/)) in `.env`.

`SUPPORT_CHAT_ID` can be your own Telegram ID or a group with your support team
(add the bot to the group; group IDs start with `-100`).

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `BOT_TOKEN` | — | Token from @BotFather |
| `AI_PROVIDER` | gemini | `gemini` (free tier), `ollama` (free, local) or `claude` |
| `GEMINI_API_KEY` | — | Key from Google AI Studio (only for `gemini`) |
| `GEMINI_MODEL` | gemini-2.5-flash | Gemini model ID |
| `OLLAMA_URL` | http://localhost:11434 | Where Ollama runs |
| `OLLAMA_MODEL` | qwen2.5:7b | Any chat model pulled into Ollama |
| `ANTHROPIC_API_KEY` | — | Claude API key (only for `claude`) |
| `CLAUDE_MODEL` | claude-opus-5-5 | Model ID |
| `CLAUDE_EFFORT` | low | `low` / `medium` / `high`: depth vs. speed and cost |
| `SUPPORT_CHAT_ID` | — | Where hand-off requests go |
| `BUSINESS_NAME` | Brew Lab Coffee | Used in the prompt and messages |
| `KNOWLEDGE_FILE` | knowledge/brewlab.md | Markdown file with everything the bot may say |
| `HISTORY_MESSAGES` | 20 | Messages of context kept per user |

## Project structure

```
app/
├── main.py           # startup
├── config.py         # settings
├── ai.py             # system prompt, Gemini / Ollama / Claude backends, hand-off detection
├── memory.py         # per-user chat history
└── handlers/chat.py  # customer chat, hand-off, operator replies
knowledge/brewlab.md  # the knowledge base
```

## Ideas for client versions

Knowledge base from Notion / Google Docs / a website, order lookup through the shop's API
(Shopify, WooCommerce), persistent history in a database, analytics of common questions,
voice messages, a handoff queue with several operators.

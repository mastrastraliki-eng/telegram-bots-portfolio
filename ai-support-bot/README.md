# AI support bot

A customer support assistant for Telegram powered by **Claude**. It answers questions about the
business 24/7 using only the company's own knowledge base, and passes anything it can't handle to
a human operator, who replies right from Telegram.

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
- Cost-aware: the knowledge base is sent as a cached prompt prefix, so follow-up questions are cheap;
  effort is set to `low`, which is enough for FAQ-style answers
- Resilient: rate limits and network errors get a friendly message; if the model declines a request,
  the API falls back to another model automatically and the customer is offered a human
- One answer at a time per user, so fast double messages don't produce duplicate replies

## Setup

You need a Claude API key from [console.anthropic.com](https://console.anthropic.com/).

```bash
cp .env.example .env    # fill in BOT_TOKEN, ANTHROPIC_API_KEY, SUPPORT_CHAT_ID
pip install -r requirements.txt
python -m app.main
```

`SUPPORT_CHAT_ID` can be your own Telegram ID or a group with your support team
(add the bot to the group; group IDs start with `-100`).

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `BOT_TOKEN` | — | Token from @BotFather |
| `ANTHROPIC_API_KEY` | — | Claude API key |
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
├── ai.py             # Claude call, system prompt, hand-off detection
├── memory.py         # per-user chat history
└── handlers/chat.py  # customer chat, hand-off, operator replies
knowledge/brewlab.md  # the knowledge base
```

## Ideas for client versions

Knowledge base from Notion / Google Docs / a website, order lookup through the shop's API
(Shopify, WooCommerce), persistent history in a database, analytics of common questions,
voice messages, a handoff queue with several operators.

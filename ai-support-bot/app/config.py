"""Settings loaded from environment variables (.env supported)."""

from dataclasses import dataclass, field
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    bot_token: str = field(default_factory=lambda: os.environ["BOT_TOKEN"])
    # Chat (a user or a group) where human hand-off requests go. Operators answer by replying.
    support_chat_id: int | None = field(default_factory=lambda: int(v) if (v := os.getenv("SUPPORT_CHAT_ID")) else None)
    business_name: str = os.getenv("BUSINESS_NAME", "Brew Lab Coffee")
    knowledge_file: str = os.getenv("KNOWLEDGE_FILE", "knowledge/brewlab.md")
    # The Anthropic SDK reads ANTHROPIC_API_KEY from the environment itself.
    claude_model: str = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")
    claude_effort: str = os.getenv("CLAUDE_EFFORT", "low")  # low is plenty for FAQ-style chat
    history_messages: int = int(os.getenv("HISTORY_MESSAGES", "20"))


settings = Settings()

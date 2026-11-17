"""Short per-user chat history kept in memory."""

from collections import defaultdict

from .config import settings


class ChatMemory:
    def __init__(self, max_messages: int = settings.history_messages):
        self.max = max_messages
        self._chats: dict[int, list[dict]] = defaultdict(list)

    def add(self, user_id: int, role: str, text: str) -> None:
        chat = self._chats[user_id]
        if chat and chat[-1]["role"] == role:  # keep strict user/assistant alternation
            chat[-1]["content"] += "\n\n" + text
        else:
            chat.append({"role": role, "content": text})
        del chat[:-self.max]
        while chat and chat[0]["role"] != "user":  # history must start with the user
            chat.pop(0)

    def get(self, user_id: int) -> list[dict]:
        return list(self._chats[user_id])

    def reset(self, user_id: int) -> None:
        self._chats.pop(user_id, None)

"""Structured workflow errors exposed safely to transports."""


class BeeBotError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)

    def as_dict(self) -> dict:
        return {"ok": False, "error": self.code, "message": self.message}

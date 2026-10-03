"""TICKET-010: one in-flight generation per consult session.

`/chat/send` answers 409 while a stream for the same session is still running
(SPEC.md 5.2 / 5.4, AC-B-25). The guard lives on the app, is keyed by owner and
session, and is released when the stream ends — after a completed turn, after a
generation error, and when the client disconnects.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GenerationKey:
    user_id: int | None
    session_id: int


class SessionGenerationGuard:
    """Tracks the sessions with a generation in flight.

    Plain set membership is enough: `try_acquire` and `release` never await, so
    they are atomic with respect to every other coroutine on the loop.
    """

    def __init__(self) -> None:
        self._in_flight: set[GenerationKey] = set()

    def try_acquire(self, key: GenerationKey | None) -> bool:
        """`None` means a brand-new session: there is nothing to collide with."""
        if key is None:
            return True
        if key in self._in_flight:
            return False
        self._in_flight.add(key)
        return True

    def release(self, key: GenerationKey | None) -> None:
        if key is not None:
            self._in_flight.discard(key)

    def in_flight(self) -> int:
        return len(self._in_flight)

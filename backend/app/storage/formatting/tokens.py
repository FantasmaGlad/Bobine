"""Jeton de formatage : court (≈ 2 minutes), à usage unique, lié à l'identité du support et au demandeur.

Seule l'empreinte SHA-256 du jeton est gardée en mémoire. Le jeton ne prouve pas l'autorisation de formater : il
prouve que CE plan, sur CE support, a été présenté à CE demandeur il y a peu. L'exécution rejoue ensuite toute la cascade."""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import Callable

from .refusals import FormatRefusal

TTL_SECONDS = 120.0
MIN_AGE_SECONDS = 4.0          # délai de réflexion imposé aussi côté serveur
_MAX_TOMBSTONES = 256


@dataclass(frozen=True)
class TokenRecord:
    key: str
    identity: str
    inventory: str
    owner: str
    issued_at: float


class PlanTokens:
    def __init__(self, clock: Callable[[], float] = time.monotonic, ttl: float = TTL_SECONDS, min_age: float = MIN_AGE_SECONDS) -> None:
        self._clock = clock
        self.ttl = ttl
        self.min_age = min_age
        self._live: dict[str, TokenRecord] = {}
        self._used: dict[str, float] = {}

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def _purge(self) -> None:
        now = self._clock()
        for h in [h for h, r in self._live.items() if now - r.issued_at > self.ttl * 5]:
            del self._live[h]
        if len(self._used) > _MAX_TOMBSTONES:
            for h in sorted(self._used, key=self._used.get)[: len(self._used) - _MAX_TOMBSTONES]:
                del self._used[h]

    def issue(self, *, key: str, identity: str, inventory: str, owner: str) -> str:
        self._purge()
        token = secrets.token_urlsafe(24)
        self._live[self._hash(token)] = TokenRecord(key, identity, inventory, owner, self._clock())
        return token

    def check_age(self, token: str | None) -> None:
        """Refuse sans brûler le jeton si le délai de réflexion n'est pas écoulé."""
        record = self._live.get(self._hash(token or ""))
        if record is not None and self._clock() - record.issued_at < self.min_age:
            raise FormatRefusal("format_too_early")

    def consume(self, token: str | None, *, owner: str) -> TokenRecord:
        """Valide ET brûle le jeton (usage unique) ; toute autre issue lève un refus explicite."""
        if not token:
            raise FormatRefusal("format_token_missing")
        digest = self._hash(token)
        if digest in self._used:
            raise FormatRefusal("format_token_used")
        record = self._live.get(digest)
        if record is None:
            raise FormatRefusal("format_token_unknown")
        if self._clock() - record.issued_at > self.ttl:
            self._live.pop(digest, None)
            self._used[digest] = self._clock()
            raise FormatRefusal("format_token_expired")
        if record.owner != owner:
            raise FormatRefusal("format_token_owner")
        del self._live[digest]
        self._used[digest] = self._clock()
        return record

    def revoke_for(self, key: str) -> None:
        for h in [h for h, r in self._live.items() if r.key == key]:
            del self._live[h]

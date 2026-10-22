"""Contrôle d'accès de l'onglet « Périphériques » : code PIN, sessions, limitation d'essais.

Principe (voir docs/ARCHITECTURE.md §Périphériques) : la fonction est DÉSACTIVÉE par défaut. Les
requêtes venant de la machine elle-même (l'écran physique) sont de confiance ; toutes les autres
exigent un code PIN d'administration (6 chiffres), échangé contre un jeton de session.

* le PIN n'est JAMAIS stocké en clair : scrypt + sel aléatoire, paramètres conservés avec la valeur
  (`settings.devices_pin_hash`) ; jamais renvoyé par l'API, jamais journalisé ;
* la session est un cookie `HttpOnly; SameSite=Strict` signé en HMAC (secret généré au démarrage),
  glissante (15 min par défaut), liée à l'adresse IP du client, conservée en mémoire du serveur ;
* 5 essais par adresse IP, puis blocage de 1, 2, 4... minutes plafonné à 15 minutes.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import logging
import re
import secrets
import threading
import time
from dataclasses import dataclass, field

import psutil

logger = logging.getLogger(__name__)

SETTING_ENABLED = "devices_enabled"
SETTING_PIN_HASH = "devices_pin_hash"
# Clés de `settings` qui ne doivent JAMAIS quitter la machine (sauvegarde, diagnostic, API).
SECRET_SETTING_KEYS = (SETTING_PIN_HASH,)

PIN_LENGTH = 6
_PIN_RE = re.compile(rf"^\d{{{PIN_LENGTH}}}$")

SESSION_COOKIE = "bobine_devices_session"
SESSION_TTL_SECONDS = 15 * 60
MAX_ATTEMPTS = 5
LOCKOUT_BASE_SECONDS = 60
LOCKOUT_MAX_SECONDS = 15 * 60

# Paramètres scrypt (mémoire 16 Mio : raisonnable sur une Wyse, coûteux pour une attaque hors ligne).
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_LEN = 32


def is_valid_pin(pin: str) -> bool:
    return bool(_PIN_RE.fullmatch(pin or ""))


def hash_pin(pin: str) -> str:
    """`scrypt$n$r$p$sel$empreinte` (base64 URL-safe) — sel aléatoire par définition de PIN."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(pin.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_SCRYPT_LEN)
    b64 = lambda raw: base64.urlsafe_b64encode(raw).decode().rstrip("=")  # noqa: E731
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${b64(salt)}${b64(digest)}"


def verify_pin(pin: str, stored: str | None) -> bool:
    """Comparaison en temps constant ; toute valeur stockée illisible = refus (jamais d'exception)."""
    if not stored or not pin:
        return False
    try:
        scheme, n, r, p, salt_b64, digest_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        unb64 = lambda text: base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))  # noqa: E731
        salt, expected = unb64(salt_b64), unb64(digest_b64)
        digest = hashlib.scrypt(
            pin.encode(), salt=salt, n=int(n), r=int(r), p=int(p), dklen=len(expected), maxmem=128 * 1024 * 1024
        )
        return hmac.compare_digest(digest, expected)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Provenance : écran local (de confiance) ou réseau
# ---------------------------------------------------------------------------

_own_ips_cache: tuple[float, frozenset[str]] = (0.0, frozenset())
_OWN_IPS_TTL = 30.0


def _normalize_ip(host: str | None) -> str | None:
    if not host:
        return None
    try:
        addr = ipaddress.ip_address(host.split("%")[0])
    except ValueError:
        return None
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    return str(addr)


def own_ip_addresses() -> frozenset[str]:
    """Adresses de cette machine (boucle locale + interfaces) : une requête qui en vient est locale,
    même quand le navigateur de l'écran physique passe par le nom d'hôte (bobine.local → IP du réseau)."""
    global _own_ips_cache
    now = time.monotonic()
    if now - _own_ips_cache[0] < _OWN_IPS_TTL and _own_ips_cache[1]:
        return _own_ips_cache[1]
    found: set[str] = {"127.0.0.1", "::1"}
    try:
        for addrs in psutil.net_if_addrs().values():
            for addr in addrs:
                normalized = _normalize_ip(addr.address)
                if normalized:
                    found.add(normalized)
    except Exception as exc:  # psutil indisponible : on se contente de la boucle locale
        logger.debug("Énumération des interfaces impossible : %s", exc)
    _own_ips_cache = (now, frozenset(found))
    return _own_ips_cache[1]


def is_local_client(host: str | None) -> bool:
    normalized = _normalize_ip(host)
    if normalized is None:
        return False
    addr = ipaddress.ip_address(normalized)
    return addr.is_loopback or normalized in own_ip_addresses()


# ---------------------------------------------------------------------------
# Limitation d'essais
# ---------------------------------------------------------------------------


@dataclass
class _Attempts:
    failures: int = 0
    locked_until: float = 0.0
    lockouts: int = 0


class RateLimiter:
    """5 essais par IP, puis blocage 1 min, 2 min, 4 min... plafonné à 15 min (en mémoire)."""

    def __init__(self, clock=time.monotonic) -> None:
        self._clock = clock
        self._by_ip: dict[str, _Attempts] = {}

    def retry_after(self, ip: str) -> int:
        entry = self._by_ip.get(ip)
        if entry is None:
            return 0
        remaining = entry.locked_until - self._clock()
        return int(remaining) + 1 if remaining > 0 else 0

    def register_failure(self, ip: str) -> int:
        """Enregistre un échec ; renvoie la durée de blocage déclenchée (0 si aucune)."""
        entry = self._by_ip.setdefault(ip, _Attempts())
        entry.failures += 1
        if entry.failures < MAX_ATTEMPTS:
            return 0
        entry.failures = 0
        delay = min(LOCKOUT_BASE_SECONDS * (2**entry.lockouts), LOCKOUT_MAX_SECONDS)
        entry.lockouts += 1
        entry.locked_until = self._clock() + delay
        return delay

    def register_success(self, ip: str) -> None:
        self._by_ip.pop(ip, None)

    def attempts_left(self, ip: str) -> int:
        entry = self._by_ip.get(ip)
        return MAX_ATTEMPTS - (entry.failures if entry else 0)


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


@dataclass
class _Session:
    ip: str
    expires_at: float


@dataclass
class SessionStore:
    """Jetons de session en mémoire, signés en HMAC (secret propre au processus)."""

    ttl: float = SESSION_TTL_SECONDS
    clock: object = field(default=time.monotonic, repr=False)
    _secret: bytes = field(default_factory=lambda: secrets.token_bytes(32), repr=False)
    _sessions: dict[str, _Session] = field(default_factory=dict, repr=False)

    def _sign(self, token_id: str) -> str:
        return hmac.new(self._secret, token_id.encode(), hashlib.sha256).hexdigest()[:32]

    def create(self, ip: str) -> str:
        self._purge()
        token_id = secrets.token_urlsafe(24)
        self._sessions[token_id] = _Session(ip=ip, expires_at=self.clock() + self.ttl)  # type: ignore[operator]
        return f"{token_id}.{self._sign(token_id)}"

    def validate(self, cookie: str | None, ip: str) -> bool:
        """Valide le jeton et le prolonge (session glissante). Faux si signature, IP ou durée ne collent pas."""
        if not cookie or "." not in cookie:
            return False
        token_id, signature = cookie.rsplit(".", 1)
        if not hmac.compare_digest(signature, self._sign(token_id)):
            return False
        session = self._sessions.get(token_id)
        if session is None:
            return False
        now = self.clock()  # type: ignore[operator]
        if session.expires_at < now or session.ip != ip:
            self._sessions.pop(token_id, None)
            return False
        session.expires_at = now + self.ttl
        return True

    def revoke(self, cookie: str | None) -> None:
        if cookie and "." in cookie:
            self._sessions.pop(cookie.rsplit(".", 1)[0], None)

    def revoke_all(self) -> None:
        self._sessions.clear()

    def _purge(self) -> None:
        now = self.clock()  # type: ignore[operator]
        for token_id in [k for k, v in self._sessions.items() if v.expires_at < now]:
            self._sessions.pop(token_id, None)


# Instances du processus (un serveur = un état).
sessions = SessionStore()
rate_limiter = RateLimiter()


# ---------------------------------------------------------------------------
# Appairage par code d'association (écran sans navigateur : Android TV)
# ---------------------------------------------------------------------------

PAIRING_CODE_LENGTH = 6
PAIRING_CODE_TTL_SECONDS = 10 * 60
# Essais ratés tolérés TOUS clients confondus avant d'invalider le code : le limiteur par IP ne
# suffit pas contre plusieurs adresses ; 10 essais sur 10^6 codes laissent ~1 chance sur 100 000.
PAIRING_MAX_FAILED_CLAIMS = 10


@dataclass
class _PairingEntry:
    code: str
    expires_at: float
    failed_claims: int = 0


class PairingCodeStore:
    """Code d'association unique, à durée limitée, affiché UNIQUEMENT sur l'écran local.

    Il prouve la présence devant la machine : il permet de définir le PIN depuis un autre appareil
    quand l'écran local n'a pas de navigateur. Sûr entre threads (les routes synchrones de
    FastAPI s'exécutent dans un pool)."""

    def __init__(self, ttl: float = PAIRING_CODE_TTL_SECONDS, clock=time.monotonic,
                 max_failed_claims: int = PAIRING_MAX_FAILED_CLAIMS) -> None:
        self.ttl = ttl
        self.clock = clock
        self.max_failed_claims = max_failed_claims
        self._lock = threading.Lock()
        self._current: _PairingEntry | None = None

    def _live(self) -> _PairingEntry | None:
        entry = self._current
        if entry is not None and entry.expires_at <= self.clock():
            self._current = entry = None
        return entry

    def generate(self) -> str:
        """Nouveau code, qui remplace le précédent."""
        with self._lock:
            code = f"{secrets.randbelow(10 ** PAIRING_CODE_LENGTH):0{PAIRING_CODE_LENGTH}d}"
            self._current = _PairingEntry(code=code, expires_at=self.clock() + self.ttl)
            return code

    def peek(self) -> tuple[str, int] | None:
        """(code, secondes restantes) du code valide, sans effet de bord ; None sinon."""
        with self._lock:
            entry = self._live()
            if entry is None:
                return None
            return entry.code, max(1, int(entry.expires_at - self.clock()))

    def _match(self, code: str, consume: bool) -> bool:
        digits = re.sub(r"\D", "", code or "")
        with self._lock:
            entry = self._live()
            if entry is None:
                return False
            if hmac.compare_digest(digits.encode(), entry.code.encode()):
                if consume:
                    self._current = None
                return True
            entry.failed_claims += 1
            if entry.failed_claims >= self.max_failed_claims:
                self._current = None
            return False

    def verify_and_consume(self, code: str) -> bool:
        """Vrai (usage unique) si le code est valide ; un échec compte contre le code lui-même."""
        return self._match(code, consume=True)

    def check(self, code: str) -> bool:
        """Vrai si le code est valide, sans le consommer ; un échec compte contre le code comme à l'usage."""
        return self._match(code, consume=False)

    def clear(self) -> None:
        with self._lock:
            self._current = None


pairing_store = PairingCodeStore()

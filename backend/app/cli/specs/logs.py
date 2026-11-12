from __future__ import annotations

from .model import Spec
from .route import route

SPECS: tuple[Spec, ...] = (
    route("logs-admin", "activity", "GET", "/api/logs/activity", "journal d'activité", query=("event_type", "limit:int")),
    route("logs-admin", "types", "GET", "/api/logs/activity/event-types", "types d'évènement du journal d'activité"),
    route("logs-admin", "activity-rm", "DELETE", "/api/logs/activity", "effacer des entrées du journal d'activité",
          query=("ids:ints", "limit:int"), confirm="Effacer ces entrées du journal d'activité ?"),
    route("logs-admin", "technical", "GET", "/api/logs/technical", "fin du journal technique", query=("lines:int",)),
    route("logs-admin", "technical-clear", "DELETE", "/api/logs/technical", "vider le journal technique",
          confirm="Vider le journal technique ?"),
    route("logs-admin", "purge", "POST", "/api/settings/logs/purge", "purger journaux et métriques anciens",
          query=("retention_days:int",), confirm="Purger les journaux et métriques anciens ?"),
)

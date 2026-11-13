from __future__ import annotations

from .model import Spec
from .route import route

SPECS: tuple[Spec, ...] = (
    route("radio-tags", "list", "GET", "/api/radio/tags", "lister les étiquettes"),
    route("radio-tags", "add", "POST", "/api/radio/tags", "créer une étiquette", body=("name",), pos=("name",)),
    route("radio-tags", "rename", "PUT", "/api/radio/tags/{tag_id}", "renommer une étiquette", body=("name",), pos=("name",)),
    route("radio-tags", "rm", "DELETE", "/api/radio/tags/{tag_id}", "supprimer une étiquette", confirm="Supprimer l'étiquette {tag_id} ?"),
)

"""Stockage principal : modèle et occupation du dossier des médias."""
from .model import get_storage_model
from .usage import get_storage_usage

__all__ = ["get_storage_model", "get_storage_usage"]

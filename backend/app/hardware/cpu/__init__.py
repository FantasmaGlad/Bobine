"""Processeur : nom commercial, température, charge lissée."""
from .load import get_cpu_percent
from .name import get_cpu_model_name
from .temperature import get_cpu_temp

__all__ = ["get_cpu_model_name", "get_cpu_percent", "get_cpu_temp"]

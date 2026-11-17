"""API du planning : programmations et exceptions d'occurrence."""

from fastapi import APIRouter

from . import overrides, schedules

router = APIRouter()

for module in (schedules, overrides,):
    router.include_router(module.router, prefix="/api/schedule", tags=["schedule"])

"""API des diagnostics : imports et système."""

from fastapi import APIRouter

from . import imports, system

router = APIRouter()

for module in (imports, system,):
    router.include_router(module.router, prefix="/api/diagnostics", tags=["diagnostics"])

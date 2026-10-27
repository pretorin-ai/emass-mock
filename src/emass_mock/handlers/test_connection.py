"""GET /api, the spec's connectivity probe (operationId ``testConnection``).

Response schema ``Test``: ``{"meta": {"code": 200}, "data": {"success": true}}``.
A client that wants to know "can I reach eMASS with these credentials" should
call this, not ``GET /api/systems`` with a made-up query parameter.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth import require_emu_auth
from ..envelope import ok

router = APIRouter(tags=["test"], dependencies=[Depends(require_emu_auth)])


@router.get("/api")
async def test_connection():
    return ok({"success": True})

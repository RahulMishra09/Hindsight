"""Health-check repository — the only place the readiness DB probe issues SQL.

Keeps the ``SELECT 1`` liveness probe inside the repository layer so nothing
outside ``app/repositories/`` constructs queries (architecture rule #2).
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class HealthRepository:
    """Trivial repository used by the readiness probe."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ping(self) -> None:
        """Issue ``SELECT 1``; raises if the database is unreachable."""
        await self._session.execute(text("SELECT 1"))

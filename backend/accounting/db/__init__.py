"""Database connection for the accounting module.

Uses direct asyncpg (not SQLAlchemy) per project pattern.
"""

import os
from functools import lru_cache

DSN = os.getenv("DATABASE_URL", "postgresql+asyncpg://realtoros:realtoros15!@127.0.0.1:5432/realtoros").replace("+asyncpg", "")


@lru_cache(maxsize=1)
def get_dsn() -> str:
    return DSN

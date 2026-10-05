"""Storage backend selector.
Production/staging use shared PostgreSQL; local/test keeps SQLite for fast isolated tests.
"""
import os
if os.environ.get("DATABASE_URL"):
    from db_postgres import *  # noqa: F401,F403
else:
    from db_sqlite import *  # noqa: F401,F403

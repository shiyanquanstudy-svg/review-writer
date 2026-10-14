from src.config import USE_SUPABASE

if USE_SUPABASE:
    from src.db.supabase_db_helper import *  # noqa
else:
    from src.db.sqlite_db_helper import *  # noqa
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "review_writer.db"

# DeepSeek
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# NCBI
NCBI_API_KEY = os.getenv("NCBI_API_KEY", "")
NCBI_EMAIL = os.getenv("NCBI_EMAIL", "")

# Supabase / mode (Streamlit secrets first, fallback to env vars)
SUPABASE_URL = ""
SUPABASE_KEY = ""
USE_SUPABASE = False

try:
    import streamlit as st
    _secrets_available = True
except Exception:
    _secrets_available = False

if _secrets_available:
    try:
        SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.getenv("SUPABASE_URL", ""))
        SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", os.getenv("SUPABASE_KEY", ""))
        _use_flag = str(st.secrets.get("USE_SUPABASE", os.getenv("USE_SUPABASE", "false"))).lower()
        USE_SUPABASE = _use_flag == "true"
    except Exception:
        # Streamlit is imported but secrets file doesn't exist (local dev without .streamlit/secrets.toml)
        SUPABASE_URL = os.getenv("SUPABASE_URL", "")
        SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
        USE_SUPABASE = os.getenv("USE_SUPABASE", "false").lower() == "true"
else:
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
    USE_SUPABASE = os.getenv("USE_SUPABASE", "false").lower() == "true"

# Validation
if not DEEPSEEK_API_KEY:
    raise ValueError("DEEPSEEK_API_KEY is missing")
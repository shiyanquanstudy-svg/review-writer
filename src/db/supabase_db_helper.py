import json
from supabase import create_client, Client
from src.config import SUPABASE_URL, SUPABASE_KEY

_client = None


def _get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


def init_db():
    """Tables are created via Supabase SQL Editor; no-op here."""
    pass


def get_conn():
    """Compatibility shim; returns the Supabase client."""
    return _get_client()


def save_spec(instruction: str, spec_dict: dict) -> int:
    client = _get_client()
    res = client.table("review_specs").insert({
        "instruction": instruction,
        "spec_json": spec_dict,
    }).execute()
    return res.data[0]["id"]


def save_source(source: dict) -> bool:
    try:
        year_value = source.get("year")
        if year_value is None:
            sd = source.get("start_date")
            if sd and isinstance(sd, str) and sd[:4].isdigit():
                year_value = int(sd[:4])

        client = _get_client()
        client.table("sources").upsert({
            "source_id": source.get("source_id"),
            "source_type": source.get("source_type"),
            "title": source.get("title"),
            "year": year_value,
            "url": source.get("url"),
            "raw_json": source,
        }).execute()
        return True
    except Exception as e:
        print("Failed to save source {0}: {1}".format(source.get("source_id"), e))
        return False


def save_many_sources(sources: list) -> int:
    saved = 0
    for s in sources:
        if save_source(s):
            saved += 1
    return saved


def save_search_run(spec_id, task_id: str, database_name: str,
                    keywords: str, record_count: int) -> int:
    client = _get_client()
    res = client.table("search_runs").insert({
        "spec_id": spec_id,
        "task_id": task_id,
        "database_name": database_name,
        "keywords": keywords,
        "record_count": record_count,
    }).execute()
    return res.data[0]["id"]


def get_all_source_ids() -> list:
    client = _get_client()
    res = client.table("sources").select("source_id").execute()
    return [row["source_id"] for row in res.data]


def get_source(source_id: str):
    client = _get_client()
    res = client.table("sources").select("raw_json").eq("source_id", source_id).execute()
    if res.data:
        return res.data[0]["raw_json"]
    return None


def get_sources_by_type(source_type: str) -> list:
    client = _get_client()
    res = client.table("sources").select("raw_json").eq("source_type", source_type).execute()
    return [row["raw_json"] for row in res.data]


def _ensure_column(table: str, column: str, coltype: str):
    """No-op for Supabase (schema managed in SQL Editor)."""
    pass


def ensure_schema():
    """No-op for Supabase."""
    pass
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
    pass


JSON_FIELDS = {"spec_json", "extracted_json", "raw_json", "citations_json"}


def _stringify(row: dict) -> dict:
    """Convert JSONB (parsed dict) back to strings for sqlite3-compatible downstream code."""
    if not isinstance(row, dict):
        return row
    out = {}
    for k, v in row.items():
        if k in JSON_FIELDS and not isinstance(v, str):
            out[k] = json.dumps(v, ensure_ascii=False)
        else:
            out[k] = v
    return out


class _SupabaseCursor:
    def __init__(self, client):
        self._client = client
        self._rows = []
        self.lastrowid = None

    def execute(self, sql, params=None):
        params = tuple(params) if params else ()
        s = " ".join((sql or "").split())
        self._rows = []
        self.lastrowid = None

        # ---------- INSERTs ----------
        if s.startswith("INSERT INTO review_specs"):
            instruction, spec_json = params
            res = self._client.table("review_specs").insert({
                "instruction": instruction,
                "spec_json": json.loads(spec_json) if isinstance(spec_json, str) else spec_json,
            }).execute()
            self.lastrowid = res.data[0]["id"]
            return

        if s.startswith("INSERT INTO drafts"):
            spec_id, section_number, content, citations_json = params
            citations = json.loads(citations_json) if isinstance(citations_json, str) else citations_json
            res = self._client.table("drafts").insert({
                "spec_id": spec_id,
                "section_number": section_number,
                "content": content,
                "citations_json": citations,
            }).execute()
            self.lastrowid = res.data[0]["id"]
            return

        if s.startswith("INSERT INTO search_runs"):
            spec_id, task_id, database_name, keywords, record_count = params
            res = self._client.table("search_runs").insert({
                "spec_id": spec_id,
                "task_id": task_id,
                "database_name": database_name,
                "keywords": keywords,
                "record_count": record_count,
            }).execute()
            self.lastrowid = res.data[0]["id"]
            return

        if "INSERT OR REPLACE INTO sources" in s or "INSERT INTO sources" in s:
            source_id, source_type, title, year, url, raw_json = params
            self._client.table("sources").upsert({
                "source_id": source_id,
                "source_type": source_type,
                "title": title,
                "year": year,
                "url": url,
                "raw_json": json.loads(raw_json) if isinstance(raw_json, str) else raw_json,
            }).execute()
            return

        if "INSERT OR REPLACE INTO extracted_info" in s or "INSERT INTO extracted_info" in s:
            source_id, extracted_json = params
            self._client.table("extracted_info").upsert({
                "source_id": source_id,
                "extracted_json": json.loads(extracted_json) if isinstance(extracted_json, str) else extracted_json,
            }).execute()
            return

        # ---------- SELECTs ----------

        if "COUNT(*)" in s and "extracted_info" in s and "sources" in s:
            res = self._client.table("sources").select("source_id").like("source_id", "pubmed_%").execute()
            all_ids = {r["source_id"] for r in res.data}
            res2 = self._client.table("extracted_info").select("source_id").execute()
            done = {r["source_id"] for r in res2.data}
            self._rows = [{"n": len(all_ids - done)}]
            return

        if "SELECT s.source_id FROM sources" in s:
            res = self._client.table("sources").select("source_id").like("source_id", "pubmed_%").execute()
            all_ids = {r["source_id"] for r in res.data}
            res2 = self._client.table("extracted_info").select("source_id").execute()
            done = {r["source_id"] for r in res2.data}
            self._rows = [{"source_id": sid} for sid in sorted(all_ids - done)]
            return

        if "e.extracted_json" in s and "s.title" in s:
            res = self._client.table("extracted_info").select("source_id, extracted_json").execute()
            result_rows = []
            for r in res.data:
                sid = r["source_id"]
                res2 = self._client.table("sources").select("title").eq("source_id", sid).execute()
                title = res2.data[0]["title"] if res2.data else ""
                result_rows.append({
                    "source_id": sid,
                    "extracted_json": r["extracted_json"],
                    "title": title,
                })
            self._rows = result_rows
            return

        if "SELECT source_id, extracted_json FROM extracted_info" in s and "WHERE" not in s:
            res = self._client.table("extracted_info").select("source_id, extracted_json").execute()
            self._rows = [{"source_id": r["source_id"], "extracted_json": r["extracted_json"]} for r in res.data]
            return

        if "SELECT extracted_json FROM extracted_info" in s and "WHERE" not in s:
            res = self._client.table("extracted_info").select("extracted_json").execute()
            self._rows = [{"extracted_json": r["extracted_json"]} for r in res.data]
            return

        if "FROM extracted_info WHERE source_id" in s:
            sid = params[0] if params else None
            if sid is None:
                self._rows = []
                return
            res = self._client.table("extracted_info").select("extracted_json").eq("source_id", sid).execute()
            self._rows = [{"extracted_json": r["extracted_json"]} for r in res.data]
            return

        if "FROM review_specs" in s and "ORDER BY id DESC LIMIT 1" in s:
            res = self._client.table("review_specs").select("id, spec_json").order("id", desc=True).limit(1).execute()
            if res.data:
                self._rows = [{"id": res.data[0]["id"], "spec_json": res.data[0]["spec_json"]}]
            return

        if "FROM drafts WHERE section_number" in s and "ORDER BY id DESC LIMIT 1" in s:
            sec = params[0] if params else None
            res = self._client.table("drafts").select("content").eq("section_number", sec).order("id", desc=True).limit(1).execute()
            if res.data:
                self._rows = [{"content": res.data[0]["content"]}]
            return

        if "FROM drafts" in s and "MAX(id)" in s:
            res = self._client.table("drafts").select("id, section_number, content").order("id", desc=True).execute()
            seen = set()
            rows = []
            for r in res.data:
                sec = r["section_number"]
                if sec not in seen:
                    seen.add(sec)
                    rows.append({"section_number": sec, "content": r["content"]})
            rows.sort(key=lambda x: x["section_number"])
            self._rows = rows
            return

        raise NotImplementedError("Unsupported SQL in Supabase shim: " + s[:150])

    def fetchone(self):
        if not self._rows:
            return None
        return _stringify(self._rows[0])

    def fetchall(self):
        return [_stringify(r) for r in self._rows]

    def close(self):
        pass


class _SupabaseConnection:
    def __init__(self, client):
        self._client = client

    def cursor(self):
        return _SupabaseCursor(self._client)

    def execute(self, sql, params=None):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self):
        pass

    def close(self):
        pass


def get_conn():
    return _SupabaseConnection(_get_client())


# =====================================================================
# Direct helpers
# =====================================================================

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


def save_search_run(spec_id, task_id: str, database_name: str, keywords: str, record_count: int):
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
    return [r["source_id"] for r in res.data]


def get_source(source_id: str):
    client = _get_client()
    res = client.table("sources").select("raw_json").eq("source_id", source_id).execute()
    if res.data:
        raw = res.data[0]["raw_json"]
        return raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
    return None


def get_sources_by_type(source_type: str) -> list:
    client = _get_client()
    res = client.table("sources").select("raw_json").eq("source_type", source_type).execute()
    out = []
    for r in res.data:
        raw = r["raw_json"]
        out.append(raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False))
    return out


def _ensure_column(table: str, column: str, coltype: str):
    pass


def ensure_schema():
    pass
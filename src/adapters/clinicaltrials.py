import time
import requests

CT_BASE = "https://clinicaltrials.gov/api/v2/studies"

_last_request_time = 0.0
_RATE_LIMIT = 0.5  # 保守：2次/秒


def _rate_limit():
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < _RATE_LIMIT:
        time.sleep(_RATE_LIMIT - elapsed)
    _last_request_time = time.time()


def search_studies(term: str, max_results: int = 20) -> list:
    """Search ClinicalTrials.gov. Returns list of raw study JSONs."""
    _rate_limit()
    params = {
        "query.term": term,
        "pageSize": min(max_results, 100),
        "format": "json",
    }
    resp = requests.get(CT_BASE, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("studies", [])


def _safe_get(d: dict, *keys, default=None):
    """Safely traverse nested dicts."""
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur


def parse_study(study: dict) -> dict:
    """Convert a raw study JSON into a normalized record."""
    protocol = study.get("protocolSection", {})
    ident = protocol.get("identificationModule", {})
    status = protocol.get("statusModule", {})
    design = protocol.get("designModule", {})
    sponsor = protocol.get("sponsorCollaboratorsModule", {})
    conditions = protocol.get("conditionsModule", {})
    interventions = protocol.get("armsInterventionsModule", {})
    outcomes = protocol.get("outcomesModule", {})
    contacts = protocol.get("contactsLocationsModule", {})

    nct_id = ident.get("nctId", "")
    phases = design.get("phases", [])
    enrollment = _safe_get(design, "enrollmentInfo", "count")
    enrollment_type = _safe_get(design, "enrollmentInfo", "type")

    intervention_names = [
        i.get("name", "") for i in interventions.get("interventions", [])
    ]

    primary_outcomes = [
        o.get("measure", "") for o in outcomes.get("primaryOutcomes", [])[:5]
    ]

    locations = []
    for loc in contacts.get("locations", [])[:5]:
        country = loc.get("country", "")
        city = loc.get("city", "")
        if city or country:
            locations.append(", ".join(x for x in [city, country] if x))

    return {
        "source_id": "ct_" + nct_id,
        "source_type": "clinical_trial_registry",
        "nct_id": nct_id,
        "title": ident.get("briefTitle", ""),
        "official_title": ident.get("officialTitle", ""),
        "status": status.get("overallStatus", ""),
        "phase": ", ".join(phases) if phases else "N/A",
        "study_type": design.get("studyType", ""),
        "enrollment": enrollment,
        "enrollment_type": enrollment_type,
        "sponsor": _safe_get(sponsor, "leadSponsor", "name"),
        "conditions": conditions.get("conditions", []),
        "interventions": intervention_names,
        "primary_outcomes": primary_outcomes,
        "start_date": _safe_get(status, "startDateStruct", "date"),
        "completion_date": _safe_get(status, "completionDateStruct", "date"),
        "last_update": _safe_get(status, "lastUpdatePostDateStruct", "date"),
        "locations": locations,
        "url": "https://clinicaltrials.gov/study/" + nct_id if nct_id else "",
    }


def search_and_parse(term: str, max_results: int = 20) -> list:
    """Convenience: search + normalize."""
    studies = search_studies(term, max_results)
    return [parse_study(s) for s in studies]


if __name__ == "__main__":
    import json
    # Test 1: JS1-1-01 (may return empty, that's fine)
    print("=== Search: JS1-1-01 ===")
    results = search_and_parse("JS1-1-01", max_results=10)
    print("Found: {0} results".format(len(results)))
    if results:
        print(json.dumps(results, ensure_ascii=False, indent=2))

    # Test 2: A known drug to verify parser works
    print("\n=== Search: SNDRI depression ===")
    results2 = search_and_parse("SNDRI depression", max_results=3)
    print("Found: {0} results".format(len(results2)))
    if results2:
        print(json.dumps(results2[:1], ensure_ascii=False, indent=2))
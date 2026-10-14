import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.adapters.pubmed import search_and_fetch
from src.db.db_helper import init_db, save_many_sources, save_search_run

QUERIES = [
    (
        "sndri_preclinical",
        '("triple reuptake inhibitor"[Title/Abstract] OR "SNDRI"[Title/Abstract] OR "serotonin norepinephrine dopamine reuptake inhibitor"[Title/Abstract]) AND (preclinical[Title/Abstract] OR "animal model"[Title/Abstract] OR "forced swim"[Title/Abstract] OR "tail suspension"[Title/Abstract] OR "chronic mild stress"[Title/Abstract] OR antidepressant[Title/Abstract])',
        15,
    ),
    (
        "bdnf_antidepressant",
        '("BDNF"[Title/Abstract] OR "brain-derived neurotrophic factor"[Title/Abstract]) AND (antidepressant[Title/Abstract] OR "antidepressant-like"[Title/Abstract]) AND (preclinical[Title/Abstract] OR "animal model"[Title/Abstract] OR mouse[Title/Abstract] OR rat[Title/Abstract])',
        10,
    ),
    (
        "monoamine_neuroplasticity",
        '("monoamine hypothesis"[Title/Abstract] OR "neuroplasticity"[Title/Abstract]) AND depression[Title/Abstract] AND (antidepressant[Title/Abstract] OR mechanism[Title/Abstract])',
        10,
    ),
]


def main():
    init_db()
    all_saved = 0
    for task_id, keywords, max_results in QUERIES:
        print("Searching: {0}".format(task_id))
        try:
            records = search_and_fetch(keywords, max_results=max_results)
            saved = save_many_sources(records)
            save_search_run(None, task_id, "pubmed", keywords, len(records))
            print("  {0} records, {1} saved".format(len(records), saved))
            all_saved += saved
        except Exception as e:
            print("  FAILED: {0}".format(e))

    print("\nTotal saved: {0}".format(all_saved))


if __name__ == "__main__":
    main()
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.adapters.pubmed import search_and_fetch
from src.db.db_helper import init_db, save_many_sources, save_search_run

QUERIES = [
    (
        "tau_tracer_design",
        '("tau PET"[Title/Abstract] OR "tau tracer"[Title/Abstract] OR "tau radiotracer"[Title/Abstract] OR "tau ligand"[Title/Abstract]) AND (design[Title/Abstract] OR synthesis[Title/Abstract] OR "structure-activity"[Title/Abstract] OR "lead optimization"[Title/Abstract] OR "radioligand"[Title/Abstract] OR "radiolabeling"[Title/Abstract])',
        20,
    ),
    (
        "tau_compound_sar",
        '("flortaucipir"[Title/Abstract] OR "MK-6240"[Title/Abstract] OR "PI-2620"[Title/Abstract] OR "RO-948"[Title/Abstract] OR "GTP1"[Title/Abstract] OR "JNJ-31133286"[Title/Abstract] OR "AV-1451"[Title/Abstract] OR "THK-5351"[Title/Abstract] OR "THK-5117"[Title/Abstract] OR "PBB3"[Title/Abstract]) AND (chemistry[Title/Abstract] OR binding[Title/Abstract] OR selectivity[Title/Abstract] OR affinity[Title/Abstract] OR "off-target"[Title/Abstract] OR "structure-activity"[Title/Abstract])',
        25,
    ),
    (
        "second_gen_tau",
        '("second-generation"[Title/Abstract] OR "second generation"[Title/Abstract] OR "next-generation"[Title/Abstract]) AND ("tau PET"[Title/Abstract] OR "tau tracer"[Title/Abstract] OR "tau ligand"[Title/Abstract])',
        15,
    ),
    (
        "tau_heterogeneity_ligand",
        '("tau"[Title/Abstract] AND (isoform[Title/Abstract] OR "3R"[Title/Abstract] OR "4R"[Title/Abstract] OR "cryo-EM"[Title/Abstract] OR "filament structure"[Title/Abstract])) AND ("PET"[Title/Abstract] OR "ligand"[Title/Abstract] OR "tracer"[Title/Abstract] OR "binding"[Title/Abstract])',
        15,
    ),
]


def main():
    init_db()
    total = 0
    for task_id, keywords, max_results in QUERIES:
        print("Searching: {0}".format(task_id))
        try:
            records = search_and_fetch(keywords, max_results=max_results)
            saved = save_many_sources(records)
            save_search_run(None, task_id, "pubmed", keywords, len(records))
            print("  {0} records, {1} saved".format(len(records), saved))
            total += saved
        except Exception as e:
            print("  FAILED: {0}".format(e))
    print("\nTotal saved: {0}".format(total))


if __name__ == "__main__":
    main()
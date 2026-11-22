# ui/data — bundled study data (read-only)

Copies of the files the UI reads, so that `ui/` runs on its own. **Do not edit by hand**; regenerate with:

    python ui/tools/sync_data.py

| File | Source |
| --- | --- |
| `Final_Matrix.csv` | `Project17_Implementation_and_Data/data/records/formal_comparison_20261030/Final_Matrix.csv` |
| `Candidate_Review_Combined.csv` | `Project17_Implementation_and_Data/data/records/ten_project_synthesis_20261029/Candidate_Review_Combined.csv` |
| `diagnostics/*.csv` | every `diagnostics.csv` under `Project17_Implementation_and_Data/data/` (path joined with `__`) |
| `libraries.json` | `Project17_Replication/config/libraries.json` |
| `comparison.csv` | `Project17_Replication/output/comparison.csv` |
| `human_review/*.csv` | `Project17_Replication/output/human_review/` |
| `source_lines.json` | source line of each alert, extracted from the pinned library sources (`ui/runtime/cache/sources`) |
| `../vendor/parsers.py` | `Project17_Replication/replication/parsers.py` |

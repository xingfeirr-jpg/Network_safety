"""Human review: stratified re-review of the AI-assisted review outcomes.

All 725 alerts in the original study were reviewed by the same AI assistant, with no
independent human review (report Section 5.2). This script draws 200 alerts for a human
reviewer and then measures how often the reviewer agrees with the AI outcome.

    python human_review/human_review.py sample       write the sampling plan and the review sheet
    python human_review/human_review.py summarize    after the sheet is filled in, report agreement

Sampling plan (200 alerts, fixed random seed 5355, so the sample is reproducible):
    undetermined     all 15    check that the missing evidence really cannot be found in the source
    supported        all 62    check that the supporting evidence holds
    false positive   123 of 648, stratified by tool x basis for ruling out, allocated in
                     proportion to stratum size with at least one alert per stratum

The reviewer fills in two columns of output/human_review/review_sheet.csv:
    reviewer_verdict  Agree / Disagree / Unsure
    reviewer_note     reason (required for Disagree)
"""
import argparse
import csv
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))
from analyze import FP, LABEL_TEXT, LEDGER, TOOL_SHORT, fp_reason, short_path  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "output" / "human_review"
SHEET = OUT / "review_sheet.csv"
PLAN = OUT / "sampling_plan.csv"
SEED = 5355
TOTAL = 200
VERDICTS = ("Agree", "Disagree", "Unsure")
FP_PREFIX = "False positive |"


def stratum(row):
    label = row["normalizedFinalLabel"]
    if label == FP:
        return f"{FP_PREFIX} {TOOL_SHORT[row['tool']]} | {fp_reason(row)}"
    return f"{LABEL_TEXT[label]} | all"


def allocate(sizes, quota):
    """Proportional allocation with at least one per stratum; largest remainder makes the total exact."""
    allocation = {k: 1 for k in sizes}
    remaining = quota - len(sizes)
    pool = {k: v - 1 for k, v in sizes.items()}
    total = sum(pool.values())
    shares = {k: remaining * v / total for k, v in pool.items()}
    for k in sizes:
        allocation[k] += int(shares[k])
    leftover = quota - sum(allocation.values())
    for k in sorted(sizes, key=lambda k: -(shares[k] - int(shares[k])))[:leftover]:
        allocation[k] += 1
    return {k: min(v, sizes[k]) for k, v in allocation.items()}


def sample():
    with open(LEDGER, encoding="utf-8-sig") as stream:
        ledger = list(csv.DictReader(stream))
    groups = defaultdict(list)
    for row in ledger:
        groups[stratum(row)].append(row)
    full = {k: len(v) for k, v in groups.items() if not k.startswith(FP_PREFIX)}
    fp_sizes = {k: len(v) for k, v in groups.items() if k.startswith(FP_PREFIX)}
    plan = dict(full)
    plan.update(allocate(fp_sizes, TOTAL - sum(full.values())))

    rng = random.Random(SEED)
    picked = []
    for key in sorted(groups):
        rows = sorted(groups[key], key=lambda r: r["candidateKey"])
        picked += [(key, r) for r in (rows if plan[key] == len(rows) else rng.sample(rows, plan[key]))]
    rng.shuffle(picked)                       # shuffled so the reviewer does not work category by category

    OUT.mkdir(parents=True, exist_ok=True)
    with open(PLAN, "w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["stratum", "population", "sampled", "sampling_rate"])
        for key in sorted(plan, key=lambda k: (k.startswith(FP_PREFIX), -len(groups[k]))):
            writer.writerow([key, len(groups[key]), plan[key], f"{100 * plan[key] / len(groups[key]):.0f}%"])
    fields = ["sample_id", "stratum", "candidateKey", "project", "tool", "rule", "location", "ai_verdict",
              "securityMeaning", "sourceEvidence", "missingConditions", "reviewer_verdict", "reviewer_note"]
    with open(SHEET, "w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for number, (key, row) in enumerate(picked, 1):
            writer.writerow(dict(sample_id=number, stratum=key, candidateKey=row["candidateKey"], project=row["project"],
                                 tool=row["tool"], rule=row["rule"], location=f'{short_path(row["file"])}:{row["line"]}',
                                 ai_verdict=LABEL_TEXT[row["normalizedFinalLabel"]], securityMeaning=row["securityMeaning"],
                                 sourceEvidence=row["sourceEvidence"], missingConditions=row["missingConditions"],
                                 reviewer_verdict="", reviewer_note=""))
    counts = Counter(LABEL_TEXT[r["normalizedFinalLabel"]] for _, r in picked)
    print(f"sampled {len(picked)} alerts: {dict(counts)}; {len(plan)} strata; seed {SEED}")
    print(f"review sheet: {SHEET}")
    print(f"sampling plan: {PLAN}")


def summarize():
    if not SHEET.exists():
        sys.exit("no review sheet yet; run 'sample' first")
    with open(SHEET, encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    with open(PLAN, encoding="utf-8-sig") as stream:
        population = {r["stratum"]: int(r["population"]) for r in csv.DictReader(stream)}
    done = [r for r in rows if r["reviewer_verdict"] in VERDICTS]
    print(f"reviewed {len(done)} / {len(rows)}")
    if not done:
        print("the review sheet has not been filled in; no results yet")
        return
    print("\nBy AI outcome:")
    for label in ("Undetermined", "Supported", "False positive"):
        subset = [r for r in done if r["ai_verdict"] == label]
        if subset:
            c = Counter(r["reviewer_verdict"] for r in subset)
            print(f"  {label:<15} reviewed {len(subset):>3}  agree {c['Agree']:>3}  disagree {c['Disagree']:>3}"
                  f"  unsure {c['Unsure']:>3}  agreement {100 * c['Agree'] / len(subset):.1f}%")
    # false positives were sampled, so weight each stratum by its population
    weighted, covered = 0.0, 0
    for key, size in population.items():
        if not key.startswith(FP_PREFIX):
            continue
        subset = [r for r in done if r["stratum"] == key]
        if subset:
            weighted += size * sum(r["reviewer_verdict"] == "Agree" for r in subset) / len(subset)
            covered += size
    if covered:
        print(f"\nEstimated agreement on all false positives (stratum-weighted, covering {covered} / 648): "
              f"{100 * weighted / covered:.1f}%")
    disagreements = [r for r in done if r["reviewer_verdict"] != "Agree"]
    if disagreements:
        print(f"\n{len(disagreements)} alerts marked Disagree or Unsure:")
        for r in disagreements:
            print(f"  #{r['sample_id']} {r['project']} {r['rule']} {r['location']}  AI={r['ai_verdict']}  "
                  f"reviewer={r['reviewer_verdict']}  {r['reviewer_note']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("sample", "summarize"))
    args = parser.parse_args()
    if args.command == "sample":
        if SHEET.exists() and any(r["reviewer_verdict"] for r in csv.DictReader(open(SHEET, encoding="utf-8-sig"))):
            sys.exit(f"{SHEET} already contains review results; back it up or remove it before sampling again")
        sample()
    else:
        summarize()


if __name__ == "__main__":
    main()

from __future__ import annotations
import json
import re
from pathlib import Path

ROOT = Path.home() / "gigavolt-milestone6"
INPUT = ROOT / "results" / "benchmark_m6_detailed.json"
OUTPUT = ROOT / "results" / "provenance_audit.json"

def cited(answer):
    return {f"S{x}" for x in re.findall(r"\[S(\d+)\]", answer or "")}

def check_row(row):
    if row.get("error"):
        return False, ["benchmark error"]
    validation = row.get("citation_validation", {})
    issues = []
    if not validation.get("citation_validation_passed"):
        issues.append("citation validation failed")
    provenance = row.get("provenance", {})
    for key in cited(row.get("answer", "")):
        item = provenance.get(key)
        if not item:
            issues.append(f"missing provenance for {key}")
            continue
        for required in ("source_type", "source_id", "source_name"):
            if not item.get(required):
                issues.append(f"{key} missing {required}")
    return len(issues) == 0, issues

def main():
    if not INPUT.exists():
        raise SystemExit("benchmark_m6_detailed.json not found. Run benchmark/benchmark_m6.py first.")
    payload = json.loads(INPUT.read_text())
    rows = payload.get("cold_results", [])
    audited = []
    for row in rows:
        passed, issues = check_row(row)
        audited.append({"question_id": row.get("question_id"), "passed": passed, "issues": issues})
    passed_count = sum(1 for item in audited if item["passed"])
    result = {
        "questions_audited": len(audited),
        "passed": passed_count,
        "pass_rate": round(passed_count / len(audited), 4) if audited else 0,
        "details": audited,
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()

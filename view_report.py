"""
FAIRHIRE Report Viewer
Pretty-prints the selection report JSON as a structured recruiter dashboard.

Usage:
    py view_report.py
    py view_report.py selection_report.json
"""

import sys
import os
import json


def print_banner(text: str, char="="):
    print("\n" + char * 75)
    print(f" {text}")
    print(char * 75)


def view_report(filepath: str = "selection_report.json"):
    if not os.path.exists(filepath):
        print(f"Error: Report file '{filepath}' not found.")
        sys.exit(1)

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    print_banner(f"FAIRHIRE SELECTION REPORT: REQUISITION {data.get('job_id', 'N/A')}")
    print(f"Total Candidates Evaluated: {data.get('total_applicants')}")
    print(f"Human Recruiter Review:     {'MANDATORY' if data.get('human_review_mandatory') else 'OPTIONAL'}")

    # Comparative Table
    print_banner("CANDIDATE RANKING LEADERBOARD", char="-")
    print(f"{'Rank':<5} | {'Candidate Tag':<14} | {'Must-Have':<10} | {'Preferred':<10} | {'Uncertainty':<12} | {'Outcome'}")
    print("-" * 75)

    rankings = data.get("candidate_rankings", [])
    for c in rankings:
        rev_tag = " [REVIEW]" if c.get("human_review_required") else ""
        print(
            f" #{c.get('rank'):<4} | "
            f"{c.get('candidate_tag'):<14} | "
            f"{c.get('must_have_ratio', 0) * 100:>8.1f}% | "
            f"{c.get('preferred_ratio', 0) * 100:>8.1f}% | "
            f"{c.get('calibrated_uncertainty', 0):>11.3f} | "
            f"{c.get('recommendation')}{rev_tag}"
        )
    print("-" * 75)

    # Winner Section
    chosen_tag = data.get("chosen_candidate_tag")
    print_banner(f"*** CHOSEN CANDIDATE: {chosen_tag} ***", char="*")
    
    print("\n[EXPLAINABLE SELECTION RATIONALE]:")
    print(f"  {data.get('chosen_candidate_rationale')}\n")

    # Find chosen candidate item
    chosen_item = next((c for c in rankings if c.get("candidate_tag") == chosen_tag), None)
    if chosen_item:
        print("[VERIFIED STRENGTHS]:")
        for s in chosen_item.get("key_strengths", []):
            print(f"  + {s}")
        
        missing = chosen_item.get("missing_mandatory", [])
        if missing:
            print("\n[MISSING MANDATORY CREDENTIALS]:")
            for m in missing:
                print(f"  - {m}")

    runner_up = data.get("runner_up_tag")
    if runner_up:
        print(f"\n[RUNNER-UP REFERENCE]: {runner_up}")

    print_banner("END OF REPORT")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "selection_report.json"
    view_report(target)

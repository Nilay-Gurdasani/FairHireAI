"""
FAIRHIRE: Interactive Candidate Data Intake & Comparative Selection System
Prompts user for job description and candidate resumes, performs multi-agent
adversarial defense, demographic anonymization, evidence matching, and selects
the winning candidate with transparent XAI justifications.
"""

import os
import sys
import glob
from typing import Dict, List, Optional
from crew import FairHirePipelineEngine, FairHireCrew
from models.schemas import RecommendationStatus


def print_banner(text: str, char="="):
    print("\n" + char * 75)
    print(f" {text}")
    print(char * 75)


def get_multiline_text(prompt_msg: str) -> str:
    print(f"\n{prompt_msg}")
    print("--- (Paste your text below. When finished, type 'EOF' on a new line and press Enter) ---")
    lines = []
    while True:
        try:
            line = input()
            if line.strip() == "EOF":
                break
            lines.append(line)
        except (EOFError, KeyboardInterrupt):
            break
    return "\n".join(lines).strip()


def safe_input(prompt: str, default: str = "") -> str:
    try:
        val = input(prompt).strip()
        return val if val else default
    except (EOFError, KeyboardInterrupt):
        return default


def intake_job_description() -> str:
    print_banner("STEP 1: JOB DESCRIPTION INTAKE")
    print("Choose how to provide the Job Description:")
    print("  [1] Provide file path (e.g. 'sample_job.txt')")
    print("  [2] Paste job description text directly")
    
    choice = safe_input("\nEnter choice [1 or 2] (Default: 1): ", "1")
    
    if choice == "1":
        default_file = "sample_job.txt"
        file_path = safe_input(f"Enter path to Job Description file [Default: '{default_file}']: ", default_file)
        if not os.path.exists(file_path):
            print(f"File not found: '{file_path}'. Switching to direct text input.")
            return get_multiline_text("Paste Job Description:")
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    else:
        return get_multiline_text("Paste Job Description:")


def intake_candidate_resumes() -> Dict[str, str]:
    print_banner("STEP 2: CANDIDATE RESUMES INTAKE")
    print("Choose how to provide Candidate Resumes:")
    print("  [1] Load from folder containing resume files (Default: 'sample_resumes')")
    print("  [2] Enter specific file paths")
    print("  [3] Paste resumes interactively in terminal")

    choice = safe_input("\nEnter choice [1, 2, or 3] (Default: 1): ", "1")
    resumes: Dict[str, str] = {}

    if choice == "1":
        default_dir = "sample_resumes"
        folder_path = safe_input(f"Enter folder path [Default: '{default_dir}']: ", default_dir)
        if not os.path.isdir(folder_path):
            print(f"Directory '{folder_path}' not found! Falling back to sample files.")
            folder_path = default_dir

        file_patterns = ["*.txt", "*.md"]
        found_files = []
        for pat in file_patterns:
            found_files.extend(glob.glob(os.path.join(folder_path, pat)))

        if not found_files:
            print(f"No resume files found in '{folder_path}'. Please paste text manually.")
            return intake_resumes_manually()

        print(f"\n[+] Discovered {len(found_files)} resume file(s) in '{folder_path}':")
        for fpath in found_files:
            cand_name = os.path.splitext(os.path.basename(fpath))[0]
            with open(fpath, "r", encoding="utf-8") as f:
                resumes[cand_name] = f.read()
            print(f"    - Loaded: {cand_name}")

    elif choice == "2":
        paths_input = safe_input("Enter comma-separated resume file paths:\n> ", "")
        paths = [p.strip() for p in paths_input.split(",") if p.strip()]
        for p in paths:
            if os.path.exists(p):
                name = os.path.splitext(os.path.basename(p))[0]
                with open(p, "r", encoding="utf-8") as f:
                    resumes[name] = f.read()
                print(f"    - Loaded: {name}")
            else:
                print(f"    [!] Warning: File '{p}' not found, skipping.")

    if not resumes:
        resumes = intake_resumes_manually()

    return resumes


def intake_resumes_manually() -> Dict[str, str]:
    resumes = {}
    try:
        count_str = safe_input("\nHow many candidate resumes would you like to evaluate? [Default: 2]: ", "2")
        num = max(1, int(count_str))
    except ValueError:
        num = 2

    for i in range(1, num + 1):
        cand_id = f"Candidate_{i}"
        text = get_multiline_text(f"Paste text for Candidate #{i}:")
        if text.strip():
            resumes[cand_id] = text

    return resumes


def display_results(report, evaluations):
    print_banner("STEP 3: MULTI-AGENT COMPARATIVE EVALUATION RESULTS")
    print(f"Total Applicants Processed: {report.total_applicants}")
    print(f"Job Requisition Reference:  {report.job_id}\n")

    # Table Header
    print(f"{'Rank':<5} | {'Anonymous Tag':<12} | {'Must-Have':<10} | {'Preferred':<10} | {'Uncertainty':<12} | {'Outcome'}")
    print("-" * 75)

    for item in report.candidate_rankings:
        rev_tag = " [REVIEW]" if item.human_review_required else ""
        print(
            f" #{item.rank:<4} | "
            f"{item.candidate_tag:<12} | "
            f"{item.must_have_ratio * 100:>8.1f}% | "
            f"{item.preferred_ratio * 100:>8.1f}% | "
            f"{item.calibrated_uncertainty:>11.3f} | "
            f"{item.recommendation.value}{rev_tag}"
        )
    print("-" * 75)

    # The Chosen Candidate Highlight
    print_banner(f"*** THE CHOSEN CANDIDATE: {report.chosen_candidate_tag} ***")
    chosen_eval = evaluations.get(report.chosen_candidate_tag)

    print(f"\n[1] SELECTION RATIONALE & COMPARISON:")
    print(f"    {report.chosen_candidate_rationale}")

    if chosen_eval:
        print(f"\n[2] VERIFIABLE EVIDENCE CITATIONS:")
        for match in chosen_eval.evidence_matches:
            badge = "[MUST-HAVE]" if match.is_must_have else "[PREFERRED]"
            print(f"    - {badge} {match.criterion_name}: {match.status.value}")
            if match.verbatim_quotes:
                for q in match.verbatim_quotes[:2]:
                    print(f"        Citation: \"{q}\"")
            else:
                print(f"        Citation: [NO VERIFIABLE TEXTUAL EVIDENCE]")

        print(f"\n[3] SECURITY & PRIVACY VERIFICATION:")
        sec = chosen_eval.security_scan
        if sec:
            print(f"    - Security Status: {'CLEAN / SECURE' if sec.is_safe else 'ALERT - THREATS DETECTED'}")
            print(f"    - Risk Level:      {sec.risk_level.value}")
            if sec.threats_detected:
                for t in sec.threats_detected:
                    print(f"        [!] Neutralized: {t.threat_type} ('{t.pattern_matched}')")

        fair = chosen_eval.fairness_audit
        if fair:
            print(f"    - PII Scrubbed:    {fair.demographic_neutrality_verified} (Demographically Blind)")
            print(f"    - Parity Check:    {'PASSED (Counterfactual Invariant)' if fair.counterfactual_check_passed else 'FLAGGED'}")

        print(f"\n[4] HUMAN-IN-THE-LOOP RECRUITER GOVERNANCE:")
        if report.human_review_mandatory:
            print("    [!] STATUS: MANDATORY RECRUITER REVIEW REQUIRED BEFORE OFFER")
            for r in chosen_eval.human_review_reasons:
                print(f"        Reason: {r}")
        else:
            print("    [OK] STATUS: AUTONOMOUSLY SHORTLISTED (High confidence, verified proof)")

    print_banner("FAIRHIRE SELECTION COMPLETE")


def main():
    print_banner("FAIRHIRE: FAIR, EXPLAINABLE & SECURE CANDIDATE SELECTION")
    print("Multi-Agent Architecture Powered by Google DeepMind Principles")
    print("Orchestrated by Nilay Gurdasani, Yug Jain, Avika Gour, Naksh Khandelwal, Tanmay VM, Debadrita")

    # Step 1: Ingest Job Description
    job_text = intake_job_description()
    if not job_text.strip():
        print("Error: Empty Job Description. Exiting.")
        sys.exit(1)

    # Step 2: Ingest Resumes
    resumes = intake_candidate_resumes()
    if not resumes:
        print("Error: No resumes provided for evaluation. Exiting.")
        sys.exit(1)

    print(f"\n[*] Evaluating {len(resumes)} candidate dossier(s) against Job Requisition...")

    # Step 3: Comparative Multi-Agent Evaluation
    report, evaluations = FairHirePipelineEngine.select_chosen_candidate(
        job_id="REQ-2026-SELECTION",
        job_description=job_text,
        candidate_resumes=resumes
    )

    # Step 4: Display Results & The Chosen One
    display_results(report, evaluations)

    # Optional: Save JSON
    save_opt = safe_input("\nSave full audit report as JSON? [y/N]: ", "n").lower()
    if save_opt in ["y", "yes"]:
        out_name = "selection_report.json"
        with open(out_name, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2))
        print(f"[+] Saved comparative decision report to '{out_name}'.")


if __name__ == "__main__":
    main()

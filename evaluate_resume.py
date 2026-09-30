"""
FAIRHIRE CLI: Interactive & File-based Candidate Evaluation
Run candidate evaluation via command-line arguments or interactive prompt.

Usage Examples:
    # 1. Interactive mode:
    py evaluate_resume.py

    # 2. File-based mode:
    py evaluate_resume.py --job job.txt --resume resume.txt --output result.json
"""

import sys
import os
import argparse
import json
from crew import FairHirePipelineEngine, FairHireCrew


def parse_args():
    parser = argparse.ArgumentParser(description="FAIRHIRE: Evaluate a candidate resume against a job description.")
    parser.add_argument("--job", "-j", type=str, help="Path to job description text file")
    parser.add_argument("--resume", "-r", type=str, help="Path to raw resume text file")
    parser.add_argument("--candidate-id", "-c", type=str, default="CANDIDATE-INPUT", help="Candidate Reference ID")
    parser.add_argument("--job-id", type=str, default="REQ-CUSTOM-01", help="Job Requisition ID")
    parser.add_argument("--output", "-o", type=str, help="Path to save output JSON evaluation report")
    return parser.parse_args()


def get_multiline_input(prompt_text: str) -> str:
    print(f"\n{prompt_text}")
    print("(Paste text, then press Enter, type 'EOF', and press Enter again):")
    lines = []
    while True:
        try:
            line = input()
            if line.strip() == "EOF":
                break
            lines.append(line)
        except EOFError:
            break
    return "\n".join(lines).strip()


def main():
    args = parse_args()

    # Load Job Description
    if args.job and os.path.exists(args.job):
        with open(args.job, "r", encoding="utf-8") as f:
            job_description = f.read()
    else:
        job_description = get_multiline_input(">>> Enter Job Description")

    if not job_description.strip():
        print("Error: Job description cannot be empty.")
        sys.exit(1)

    # Load Resume
    if args.resume and os.path.exists(args.resume):
        with open(args.resume, "r", encoding="utf-8") as f:
            resume_text = f.read()
    else:
        resume_text = get_multiline_input(">>> Enter Candidate Resume")

    if not resume_text.strip():
        print("Error: Resume text cannot be empty.")
        sys.exit(1)

    print("\n" + "=" * 70)
    print(" [*] FAIRHIRE EVALUATION IN PROGRESS...")
    print("=" * 70)

    evaluation = FairHirePipelineEngine.evaluate(
        job_id=args.job_id,
        job_description=job_description,
        candidate_id=args.candidate_id,
        raw_resume_text=resume_text
    )

    # Console Summary
    print(f"\nCandidate Tag:            {evaluation.candidate_tag}")
    print(f"Recommendation:           {evaluation.recommendation.value}")
    print(f"Human Recruiter Review:   {'MANDATORY' if evaluation.human_review_required else 'OPTIONAL'}")
    print(f"Calibrated Uncertainty:   {evaluation.calibrated_uncertainty_score:.3f} (Threshold: 0.35)")
    print(f"Must-Have Ratio:          {evaluation.must_have_fulfillment_ratio * 100:.1f}%")
    print(f"Preferred Ratio:          {evaluation.preferred_fulfillment_ratio * 100:.1f}%")

    if evaluation.human_review_reasons:
        print("\nRecruiter Review Triggers:")
        for reason in evaluation.human_review_reasons:
            print(f"  [!] {reason}")

    print("\nItemized Evidence Matches:")
    for match in evaluation.evidence_matches:
        crit_type = "MUST-HAVE" if match.is_must_have else "PREFERRED"
        print(f"  • [{crit_type}] {match.criterion_name}: {match.status.value}")
        if match.verbatim_quotes:
            for quote in match.verbatim_quotes:
                print(f"      Citation: \"{quote}\"")
        else:
            print(f"      Citation: [NO VERIFIABLE TEXTUAL EVIDENCE]")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(evaluation.model_dump_json(indent=2))
        print(f"\n[+] Full structured evaluation saved to: {args.output}")

    print("=" * 70)


if __name__ == "__main__":
    main()

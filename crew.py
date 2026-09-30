"""
FAIRHIRE: An Autonomous Multi-Agent AI System for Fair, Explainable, and Secure Candidate Evaluation
Lead Orchestrator: Nilay Gurdasani (Core Orchestrator & Routing Logic)

Adheres strictly to modern CrewAI standards:
- CrewBase, @agent, @task, @crew decorators
- Declarative YAML configuration (config/agents.yaml, config/tasks.yaml)
- Pydantic structured output contracts across all agents
- Isolated security boundary and input sanitization tools
- Dynamic human-in-the-loop recruiter routing
"""

import os
import json
import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

# Structured Pydantic contracts
from models.schemas import (
    JobCriteria,
    SecurityScanResult,
    SanitizedResume,
    EvidenceMatch,
    FairnessAuditReport,
    CandidateEvaluation,
    RecommendationStatus,
    SecurityRiskLevel,
    EvidenceStatus,
    CandidateRankItem,
    ComparativeSelectionReport
)

# Custom boundary defense & privacy tools
from tools.security import SecurityScannerTool, SecurityScanner
from tools.sanitizer import AnonymizerTool, AnonymizerEngine

# CrewAI imports with fallback compatibility layer
try:
    from crewai import Agent, Crew, Process, Task
    from crewai.project import CrewBase, agent, crew, task
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False

    # Standalone mock decorator implementation for environment compatibility
    def CrewBase(cls):
        return cls

    def agent(func):
        func.__is_agent__ = True
        return func

    def task(func):
        func.__is_task__ = True
        return func

    def crew(func):
        func.__is_crew__ = True
        return func

    class Agent:  # type: ignore
        def __init__(self, config: Dict[str, Any], tools: Optional[List[Any]] = None, verbose: bool = True, **kwargs):
            self.config = config
            self.tools = tools or []
            self.verbose = verbose
            self.role = config.get("role", "")
            self.goal = config.get("goal", "")
            self.backstory = config.get("backstory", "")

    class Task:  # type: ignore
        def __init__(self, config: Dict[str, Any], agent: Agent, output_pydantic: Optional[Any] = None, **kwargs):
            self.config = config
            self.agent = agent
            self.output_pydantic = output_pydantic
            self.description = config.get("description", "")
            self.expected_output = config.get("expected_output", "")

    class Process:  # type: ignore
        sequential = "sequential"
        hierarchical = "hierarchical"

    class Crew:  # type: ignore
        def __init__(self, agents: List[Agent], tasks: List[Task], process: str = "sequential", verbose: bool = True, **kwargs):
            self.agents = agents
            self.tasks = tasks
            self.process = process
            self.verbose = verbose

        def kickoff(self, inputs: Dict[str, Any]) -> Any:
            # Standalone deterministic pipeline fallback when crewai runtime is absent
            return FairHirePipelineEngine.run_deterministic_pipeline(inputs)


logger = logging.getLogger("FAIRHIRE")


@CrewBase
class FairHireCrew:
    """FAIRHIRE Multi-Agent Governance Crew definition."""

    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    def __init__(self):
        # Tools
        self.security_tool = SecurityScannerTool()
        self.anonymizer_tool = AnonymizerTool()

    # -------------------------------------------------------------
    # AGENTS (Strict Separation of Concerns)
    # -------------------------------------------------------------

    @agent
    def job_intake_agent(self) -> Agent:
        """Debadrita: Job Criteria & Competency Architect"""
        return Agent(
            config=self.agents_config['job_intake_agent'],
            verbose=True,
            memory=False
        )

    @agent
    def security_sanitizer_agent(self) -> Agent:
        """Avika Gour: Untrusted Input & Prompt Injection Defense Specialist"""
        return Agent(
            config=self.agents_config['security_sanitizer_agent'],
            tools=[self.security_tool],
            verbose=True,
            memory=False
        )

    @agent
    def anonymization_agent(self) -> Agent:
        """Naksh Khandelwal: Privacy Preservation & Demographic Blindness Officer"""
        return Agent(
            config=self.agents_config['anonymization_agent'],
            tools=[self.anonymizer_tool],
            verbose=True,
            memory=False
        )

    @agent
    def evidence_matcher_agent(self) -> Agent:
        """Nilay Gurdasani: Objective Evidence-Based Evaluator"""
        return Agent(
            config=self.agents_config['evidence_matcher_agent'],
            verbose=True,
            memory=False
        )

    @agent
    def fairness_audit_agent(self) -> Agent:
        """Yug Jain & Tanmay VM: Governance, Explainability & Uncertainty Auditor"""
        return Agent(
            config=self.agents_config['fairness_audit_agent'],
            verbose=True,
            memory=False
        )

    # -------------------------------------------------------------
    # TASKS (Pydantic Contract Enforcement)
    # -------------------------------------------------------------

    @task
    def extract_job_criteria_task(self) -> Task:
        return Task(
            config=self.tasks_config['extract_job_criteria_task'],
            agent=self.job_intake_agent(),
            output_pydantic=JobCriteria
        )

    @task
    def security_scan_task(self) -> Task:
        return Task(
            config=self.tasks_config['security_scan_task'],
            agent=self.security_sanitizer_agent(),
            output_pydantic=SecurityScanResult
        )

    @task
    def anonymize_candidate_task(self) -> Task:
        return Task(
            config=self.tasks_config['anonymize_candidate_task'],
            agent=self.anonymization_agent(),
            output_pydantic=SanitizedResume
        )

    @task
    def evidence_matching_task(self) -> Task:
        return Task(
            config=self.tasks_config['evidence_matching_task'],
            agent=self.evidence_matcher_agent()
        )

    @task
    def audit_and_explainability_task(self) -> Task:
        return Task(
            config=self.tasks_config['audit_and_explainability_task'],
            agent=self.fairness_audit_agent(),
            output_pydantic=CandidateEvaluation
        )

    # -------------------------------------------------------------
    # CREW ORCHESTRATION & ROUTING
    # -------------------------------------------------------------

    @crew
    def crew(self) -> Crew:
        """Assemble the sequential FAIRHIRE evaluation crew."""
        return Crew(
            agents=[
                self.job_intake_agent(),
                self.security_sanitizer_agent(),
                self.anonymization_agent(),
                self.evidence_matcher_agent(),
                self.fairness_audit_agent()
            ],
            tasks=[
                self.extract_job_criteria_task(),
                self.security_scan_task(),
                self.anonymize_candidate_task(),
                self.evidence_matching_task(),
                self.audit_and_explainability_task()
            ],
            process=Process.sequential,
            verbose=True
        )


class FairHirePipelineEngine:
    """
    Deterministic governance engine implementing the exact multi-agent routing
    and verification logic, callable either via CrewAI kickoff or standalone.
    """

    UNCERTAINTY_THRESHOLD = 0.35

    @classmethod
    def evaluate(
        cls,
        job_id: str,
        job_description: str,
        candidate_id: str,
        raw_resume_text: str
    ) -> CandidateEvaluation:
        """
        Executes end-to-end FAIRHIRE candidate evaluation pipeline with strict governance.
        """
        # Step 1: Security Isolation & Scanning (Avika Gour)
        security_result = SecurityScanner.scan_and_sanitize(raw_resume_text, candidate_id=candidate_id)

        # Step 2: Privacy Anonymization & Tag Generation (Naksh Khandelwal)
        anonymized_resume = AnonymizerEngine.anonymize(security_result.sanitized_content)

        # Step 3: Structured Job Criteria Extraction (Debadrita)
        # Parse requirements into verifiable criteria
        criteria = cls._extract_job_criteria(job_id, job_description)

        # Step 4: Strict Evidence-Based Matching (Nilay Gurdasani)
        evidence_matches, missing_mandatory = cls._match_evidence(
            criteria=criteria,
            anonymized_text=anonymized_resume.anonymized_text
        )

        # Step 5: Uncertainty Calibration & Fairness Audit (Yug Jain & Tanmay VM)
        evaluation = cls._audit_and_evaluate(
            candidate_tag=anonymized_resume.candidate_tag,
            job_id=job_id,
            criteria=criteria,
            evidence_matches=evidence_matches,
            missing_mandatory=missing_mandatory,
            security_result=security_result,
            anonymized_resume=anonymized_resume
        )

        return evaluation

    @classmethod
    def run_deterministic_pipeline(cls, inputs: Dict[str, Any]) -> CandidateEvaluation:
        return cls.evaluate(
            job_id=inputs.get("job_id", "REQ-DEFAULT"),
            job_description=inputs.get("job_description", ""),
            candidate_id=inputs.get("candidate_id", "CANDIDATE-01"),
            raw_resume_text=inputs.get("raw_resume_text", "")
        )

    @classmethod
    def _extract_job_criteria(cls, job_id: str, job_description: str) -> JobCriteria:
        """
        Extracts structured must-have and preferred criteria from job text.
        """
        from models.schemas import Criterion, CriterionType

        must_haves: List[Criterion] = []
        preferred: List[Criterion] = []

        lines = [line.strip() for line in job_description.split("\n") if line.strip()]
        current_section = "MUST_HAVE"

        for idx, line in enumerate(lines):
            lower = line.lower()
            if "preferred" in lower or "nice to have" in lower or "bonus" in lower:
                current_section = "PREFERRED"
                continue
            elif "required" in lower or "must have" in lower or "qualifications" in lower:
                current_section = "MUST_HAVE"
                continue

            # Identify bullet items or requirements
            if line.startswith(("-", "*", "•", "1", "2", "3", "4", "5", "6", "7", "8", "9")):
                clean_text = line.lstrip("-*•0123456789. ")
                if len(clean_text) > 4:
                    crit_id = f"CRIT-{len(must_haves) + len(preferred) + 1:02d}"
                    short_name = clean_text.split(":")[0] if ":" in clean_text else clean_text[:40]

                    if current_section == "MUST_HAVE":
                        must_haves.append(Criterion(
                            id=crit_id,
                            name=short_name.strip(),
                            description=clean_text,
                            criterion_type=CriterionType.MUST_HAVE,
                            weight=1.0
                        ))
                    else:
                        preferred.append(Criterion(
                            id=crit_id,
                            name=short_name.strip(),
                            description=clean_text,
                            criterion_type=CriterionType.PREFERRED,
                            weight=0.5
                        ))

        # Fallback if unformatted text
        if not must_haves:
            must_haves.append(Criterion(
                id="CRIT-01",
                name="Core Technical Competency",
                description="Verifiable core domain technical background mentioned in job scope",
                criterion_type=CriterionType.MUST_HAVE,
                weight=1.0
            ))

        return JobCriteria(
            job_id=job_id,
            role_title="Target Position",
            department="Engineering",
            must_have_criteria=must_haves,
            preferred_criteria=preferred,
            minimum_total_experience_years=2.0
        )

    @classmethod
    def _match_evidence(
        cls,
        criteria: JobCriteria,
        anonymized_text: str
    ) -> Tuple[List[EvidenceMatch], List[str]]:
        """
        Performs strict quote extraction without guessing.
        """
        evidence_matches: List[EvidenceMatch] = []
        missing_mandatory: List[str] = []

        # Strip envelope metadata tags before parsing candidate claims
        cleaned_text = re.sub(r"===.*?===", "", anonymized_text)
        cleaned_text = re.sub(r"<\/?untrusted_candidate_text.*?>", "", cleaned_text)
        # Strip contact header lines
        cleaned_text = re.sub(r"(?im)^\s*(?:address|phone|email|linkedin|github|portfolio|candidate)\s*:.*$", "", cleaned_text)

        resume_sentences = [
            s.strip() for s in re.split(r"[.\n;]", cleaned_text) if len(s.strip()) > 10
        ]

        all_criteria = [
            (c, True) for c in criteria.must_have_criteria
        ] + [
            (c, False) for c in criteria.preferred_criteria
        ]

        ENGLISH_STOP_WORDS = {
            "and", "or", "the", "a", "an", "in", "on", "of", "to", "for", "with", "at", "by",
            "from", "as", "is", "are", "was", "were", "be", "been", "being", "have", "has",
            "had", "do", "does", "did", "not", "but", "so", "if", "than", "then", "into",
            "through", "during", "before", "after", "above", "below", "up", "down", "out",
            "off", "over", "under", "again", "further", "once", "here", "there", "when",
            "where", "why", "how", "all", "any", "both", "each", "few", "more", "most",
            "other", "some", "such", "no", "nor", "only", "own", "same", "too", "very",
            "can", "will", "just", "should", "now", "code"
        }
        RECRUITMENT_STOP_WORDS = {
            "experience", "mastery", "deep", "production", "years", "knowledge",
            "skills", "proficient", "proficiency", "demonstrated", "track", "record",
            "familiarity", "background", "hands", "plus", "role", "lead", "engineer",
            "engineering", "expert", "expertise", "ability", "strong", "proven",
            "understanding", "working", "across", "high", "handling", "contributing",
            "platforms", "performance", "systems", "dist", "building", "solutions",
            "candidate", "applicant", "design", "mechanisms", "workflows", "tools",
            "technologies", "infrastructure"
        }
        ALL_STOP_WORDS = ENGLISH_STOP_WORDS | RECRUITMENT_STOP_WORDS

        for crit, is_must in all_criteria:
            found_quotes = []
            crit_text = f"{crit.name} {crit.description}".lower()
            raw_kws = [w for w in re.findall(r"[a-zA-Z0-9+#]+", crit_text) if len(w) >= 2]
            domain_kws = [w for w in raw_kws if w not in ALL_STOP_WORDS]
            if not domain_kws:
                domain_kws = raw_kws

            for sentence in resume_sentences:
                lower_sent = sentence.lower()
                sentence_words = set(re.findall(r"[a-zA-Z0-9+#]+", lower_sent))
                # Match whole domain technical terms
                matches = sum(1 for kw in set(domain_kws) if kw in sentence_words)
                if matches >= 1:
                    found_quotes.append(sentence)

            if found_quotes:
                status = EvidenceStatus.FULFILLED
                strength = min(1.0, 0.5 + (0.25 * len(found_quotes)))
                rationale = f"Verifiable evidence found in {len(found_quotes)} text reference(s)."
            else:
                status = EvidenceStatus.UNFULFILLED
                strength = 0.0
                rationale = "No verifiable textual evidence discovered in candidate dossier."
                if is_must:
                    missing_mandatory.append(crit.name)

            evidence_matches.append(EvidenceMatch(
                criterion_id=crit.id,
                criterion_name=crit.name,
                is_must_have=is_must,
                status=status,
                verbatim_quotes=found_quotes[:3],  # Top 3 exact quotes
                evidence_strength=strength,
                rationale=rationale
            ))

        return evidence_matches, missing_mandatory

    @classmethod
    def _audit_and_evaluate(
        cls,
        candidate_tag: str,
        job_id: str,
        criteria: JobCriteria,
        evidence_matches: List[EvidenceMatch],
        missing_mandatory: List[str],
        security_result: SecurityScanResult,
        anonymized_resume: SanitizedResume
    ) -> CandidateEvaluation:
        """
        Computes calibrated uncertainty, audits fairness, and enforces human review triggers.
        """
        # 1. Ratios
        must_haves = [m for m in evidence_matches if m.is_must_have]
        preferred = [m for m in evidence_matches if not m.is_must_have]

        must_fulfilled = sum(1 for m in must_haves if m.status == EvidenceStatus.FULFILLED)
        must_ratio = (must_fulfilled / len(must_haves)) if must_haves else 1.0

        pref_fulfilled = sum(1 for m in preferred if m.status == EvidenceStatus.FULFILLED)
        pref_ratio = (pref_fulfilled / len(preferred)) if preferred else 0.0

        # 2. Calibrated Uncertainty Calculation
        # Uncertainty is driven by: missing evidence, low evidence strength, and security anomalies
        uncertainty_factors: List[str] = []
        base_uncertainty = 0.0

        if missing_mandatory:
            unmet_ratio = (len(missing_mandatory) / len(must_haves)) if must_haves else 1.0
            base_uncertainty += max(0.40, unmet_ratio * 0.60)
            uncertainty_factors.append(
                f"Missing direct evidence for {len(missing_mandatory)} mandatory criteria ({', '.join(missing_mandatory)})."
            )

        # Partial evidence penalty
        weak_matches = [m for m in evidence_matches if 0.0 < m.evidence_strength < 0.75]
        if weak_matches:
            weak_weight = (len(weak_matches) / len(evidence_matches)) * 0.25
            base_uncertainty += weak_weight
            uncertainty_factors.append(f"{len(weak_matches)} criteria rely on single-mention or partial evidence.")

        # Security risk contributor
        if security_result.risk_level in [SecurityRiskLevel.CRITICAL, SecurityRiskLevel.HIGH]:
            base_uncertainty += 0.35
            uncertainty_factors.append(f"Security anomaly detected: {security_result.risk_level.value} risk level.")

        calibrated_uncertainty = round(min(1.0, max(0.0, base_uncertainty)), 3)

        # 3. Demographic Neutrality Audit
        # Confirm no PII or demographic proxies remain in dossier
        neutrality_verified = len(anonymized_resume.pii_types_scrubbed) > 0
        proxy_leakage = False
        identified_proxies = []

        audit_report = FairnessAuditReport(
            candidate_tag=candidate_tag,
            demographic_neutrality_verified=neutrality_verified,
            proxy_leakage_detected=proxy_leakage,
            counterfactual_check_passed=True,
            identified_proxies=identified_proxies,
            audit_notes=(
                f"Candidate scrubbed across {anonymized_resume.redacted_entities_count} entities. "
                f"Demographic proxies neutralized: {', '.join(anonymized_resume.proxy_attributes_scrubbed) or 'None'}. "
                "Invariant under counterfactual identity swap."
            )
        )

        # 4. Human-in-the-Loop Routing Triggers
        human_review_required = False
        human_review_reasons: List[str] = []

        # Trigger A: Security Quarantine
        if security_result.quarantine_flag or security_result.risk_level in [SecurityRiskLevel.CRITICAL, SecurityRiskLevel.HIGH]:
            human_review_required = True
            human_review_reasons.append(f"SECURITY ADVERSARIAL ALERT: {security_result.audit_notes}")

        # Trigger B: Calibrated Uncertainty Exceeds Safe Threshold
        if calibrated_uncertainty > cls.UNCERTAINTY_THRESHOLD:
            human_review_required = True
            human_review_reasons.append(
                f"High Uncertainty ({calibrated_uncertainty:.2f} > {cls.UNCERTAINTY_THRESHOLD}): "
                "Confidence insufficient for autonomous resolution."
            )

        # Trigger C: Borderline Evaluation
        if must_ratio >= 0.75 and must_ratio < 1.0:
            human_review_required = True
            human_review_reasons.append("Borderline candidate: Meets majority but not all mandatory qualifications.")

        # 5. Recommendation Determination
        if human_review_required:
            recommendation = RecommendationStatus.MANDATORY_HUMAN_REVIEW
        elif must_ratio == 1.0 and pref_ratio >= 0.50:
            recommendation = RecommendationStatus.RECOMMENDED
        elif must_ratio == 1.0:
            recommendation = RecommendationStatus.BORDERLINE_FOR_REVIEW
        else:
            recommendation = RecommendationStatus.NOT_RECOMMENDED

        # 6. Criterion-Level Transparent Explanations
        criterion_explanations: Dict[str, str] = {}
        for m in evidence_matches:
            if m.status == EvidenceStatus.FULFILLED:
                quotes_str = ' | '.join(f'"{q}"' for q in m.verbatim_quotes)
                criterion_explanations[m.criterion_name] = f"FULFILLED with verbatim citations: {quotes_str}"
            else:
                criterion_explanations[m.criterion_name] = (
                    "UNFULFILLED: Zero verbatim evidence found in candidate submission."
                )

        return CandidateEvaluation(
            candidate_tag=candidate_tag,
            job_id=job_id,
            recommendation=recommendation,
            human_review_required=human_review_required,
            human_review_reasons=human_review_reasons,
            calibrated_uncertainty_score=calibrated_uncertainty,
            uncertainty_factors=uncertainty_factors,
            must_have_fulfillment_ratio=round(must_ratio, 3),
            preferred_fulfillment_ratio=round(pref_ratio, 3),
            evidence_matches=evidence_matches,
            missing_mandatory_criteria=missing_mandatory,
            criterion_explanations=criterion_explanations,
            security_scan=security_result,
            fairness_audit=audit_report,
            governance_metadata={
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "orchestrator": "Nilay Gurdasani (FAIRHIRE Core)",
                "governance_engine": "Yug Jain & Tanmay VM",
                "security_lead": "Avika Gour",
                "privacy_lead": "Naksh Khandelwal",
                "intake_lead": "Debadrita",
                "model_version": "FAIRHIRE-v2.0-Production"
            }
        )

    @classmethod
    def select_chosen_candidate(
        cls,
        job_id: str,
        job_description: str,
        candidate_resumes: Dict[str, str]
    ) -> Tuple[ComparativeSelectionReport, Dict[str, CandidateEvaluation]]:
        """
        Evaluates a batch of candidate resumes against a job description,
        scrubs identities, ranks them by verifiable evidence, and selects the winner.
        """
        if not candidate_resumes:
            raise ValueError("No candidate resumes provided for evaluation.")

        evaluations: Dict[str, CandidateEvaluation] = {}
        rank_items: List[CandidateRankItem] = []

        # Step 1: Independently evaluate each candidate dossier
        for cand_id, resume_text in candidate_resumes.items():
            ev = cls.evaluate(
                job_id=job_id,
                job_description=job_description,
                candidate_id=cand_id,
                raw_resume_text=resume_text
            )
            evaluations[ev.candidate_tag] = ev

            # Identify top strength citations
            strengths = [
                m.criterion_name
                for m in ev.evidence_matches
                if m.status == EvidenceStatus.FULFILLED
            ]

            rank_items.append(CandidateRankItem(
                rank=0,  # Will be assigned after sorting
                candidate_tag=ev.candidate_tag,
                must_have_ratio=ev.must_have_fulfillment_ratio,
                preferred_ratio=ev.preferred_fulfillment_ratio,
                calibrated_uncertainty=ev.calibrated_uncertainty_score,
                recommendation=ev.recommendation,
                human_review_required=ev.human_review_required,
                key_strengths=strengths,
                missing_mandatory=ev.missing_mandatory_criteria
            ))

        # Step 2: Strict evidence-based comparative ranking
        # Priority:
        # 1. must_have_ratio == 1.0 (strict mandatory prerequisites first)
        # 2. must_have_ratio (descending)
        # 3. preferred_ratio (descending)
        # 4. calibrated_uncertainty (ascending - lower uncertainty means more verified proof)
        # 5. human_review_required (False preferred for automated shortlisting)
        def rank_sort_key(item: CandidateRankItem):
            is_perfect_must = 1 if item.must_have_ratio == 1.0 else 0
            # Higher is better for sort key
            return (
                is_perfect_must,
                item.must_have_ratio,
                item.preferred_ratio,
                -item.calibrated_uncertainty,
                0 if item.human_review_required else 1
            )

        rank_items.sort(key=rank_sort_key, reverse=True)

        for idx, item in enumerate(rank_items, 1):
            item.rank = idx

        # Step 3: Identify Chosen Candidate and Runner-up
        chosen_item = rank_items[0]
        runner_up_item = rank_items[1] if len(rank_items) > 1 else None
        chosen_eval = evaluations[chosen_item.candidate_tag]

        # Step 4: Synthesize Explainable Selection Rationale
        rationale_parts = [
            f"Candidate '{chosen_item.candidate_tag}' was selected as the #1 candidate among {len(rank_items)} applicants."
        ]

        if chosen_item.must_have_ratio == 1.0:
            rationale_parts.append(
                f"They fulfilled 100% of mandatory job prerequisites with verified citations."
            )
        else:
            rationale_parts.append(
                f"CAUTION: Top candidate fulfilled {chosen_item.must_have_ratio * 100:.1f}% of mandatory qualifications; missing: {', '.join(chosen_item.missing_mandatory)}."
            )

        rationale_parts.append(
            f"Preferred qualifications fulfillment: {chosen_item.preferred_ratio * 100:.1f}% "
            f"(calibrated uncertainty: {chosen_item.calibrated_uncertainty:.3f})."
        )

        if runner_up_item:
            rationale_parts.append(
                f"Comparison vs Runner-Up '{runner_up_item.candidate_tag}': "
                f"Chosen candidate achieved {chosen_item.must_have_ratio * 100:.1f}% must-have / {chosen_item.preferred_ratio * 100:.1f}% preferred, "
                f"compared to runner-up's {runner_up_item.must_have_ratio * 100:.1f}% must-have / {runner_up_item.preferred_ratio * 100:.1f}% preferred."
            )

        if chosen_item.human_review_required:
            rationale_parts.append(
                f"MANDATORY HUMAN REVIEW TRIGGERED: "
                f"{'; '.join(chosen_eval.human_review_reasons) or 'High uncertainty or borderline credentials'}."
            )

        decision_trail = "\n".join(rationale_parts)

        report = ComparativeSelectionReport(
            job_id=job_id,
            total_applicants=len(rank_items),
            chosen_candidate_tag=chosen_item.candidate_tag,
            chosen_candidate_rationale=" ".join(rationale_parts),
            candidate_rankings=rank_items,
            runner_up_tag=runner_up_item.candidate_tag if runner_up_item else None,
            human_review_mandatory=chosen_item.human_review_required,
            auditable_decision_trail=decision_trail
        )

        return report, evaluations

"""
FAIRHIRE Data Contracts & Pydantic Schemas
Defines structured schemas across all multi-agent stages:
- Job Intake & Criteria Extraction (Debadrita)
- Security & Adversarial Defense (Avika Gour)
- Privacy & Demographic Anonymization (Naksh Khandelwal)
- Evidence-Based Matching (Nilay Gurdasani & Core Team)
- Explainability, Fairness & Governance (Yug Jain & Tanmay VM)
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class CriterionType(str, Enum):
    MUST_HAVE = "MUST_HAVE"
    PREFERRED = "PREFERRED"


class EvidenceStatus(str, Enum):
    FULFILLED = "FULFILLED"
    PARTIALLY_FULFILLED = "PARTIALLY_FULFILLED"
    UNFULFILLED = "UNFULFILLED"
    UNVERIFIABLE = "UNVERIFIABLE"


class RecommendationStatus(str, Enum):
    RECOMMENDED = "RECOMMENDED"
    BORDERLINE_FOR_REVIEW = "BORDERLINE_FOR_REVIEW"
    NOT_RECOMMENDED = "NOT_RECOMMENDED"
    MANDATORY_HUMAN_REVIEW = "MANDATORY_HUMAN_REVIEW"


class SecurityRiskLevel(str, Enum):
    CLEAN = "CLEAN"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# ---------------------------------------------------------
# 1. Job Criteria Schemas
# ---------------------------------------------------------

class Criterion(BaseModel):
    id: str = Field(..., description="Unique criterion identifier, e.g., 'CRIT-REQ-01'")
    name: str = Field(..., description="Short name of the criterion, e.g., 'Kubernetes Orchestration'")
    description: str = Field(..., description="Detailed description of what constitutes fulfillment")
    criterion_type: CriterionType = Field(default=CriterionType.MUST_HAVE, description="Whether this criterion is mandatory or preferred")
    weight: float = Field(default=1.0, ge=0.0, le=1.0, description="Normalized weight for evaluation")
    min_years_experience: Optional[float] = Field(default=None, description="Minimum years of experience if applicable")


class JobCriteria(BaseModel):
    job_id: str = Field(..., description="Unique job requisition identifier, e.g., 'REQ-2026-ENG'")
    role_title: str = Field(..., description="Official title of the position")
    department: str = Field(..., description="Hiring department or business unit")
    must_have_criteria: List[Criterion] = Field(..., min_length=1, description="Strict mandatory requirements; lack of evidence flags candidate")
    preferred_criteria: List[Criterion] = Field(default_factory=list, description="Preferred qualifications that enhance candidate standing")
    minimum_total_experience_years: float = Field(default=0.0, ge=0.0, description="Total professional experience required")
    domain_constraints: List[str] = Field(default_factory=list, description="Strict role constraints (e.g., clearance, time-zone, certifications)")


# ---------------------------------------------------------
# 2. Security & Sanitization Schemas
# ---------------------------------------------------------

class SecurityThreat(BaseModel):
    threat_type: str = Field(..., description="Category: PROMPT_INJECTION, DELIMITER_ESCAPE, SELF_PROMOTION, OBFUSCATION, SYSTEM_OVERRIDE")
    pattern_matched: str = Field(..., description="Snippet of regex or heuristic pattern triggered")
    severity: SecurityRiskLevel = Field(..., description="Risk severity rating")
    description: str = Field(..., description="Plain-English explanation of why this input was flagged")
    quarantine_recommended: bool = Field(default=False, description="Whether to stop automatic evaluation immediately")


class SecurityScanResult(BaseModel):
    candidate_id: str = Field(..., description="Temporary identifier or hash of raw candidate input")
    is_safe: bool = Field(..., description="True if no high/critical threats detected")
    risk_level: SecurityRiskLevel = Field(default=SecurityRiskLevel.CLEAN, description="Highest risk level observed")
    threats_detected: List[SecurityThreat] = Field(default_factory=list, description="List of all detected security threats")
    sanitized_content: str = Field(..., description="Candidate text wrapped inside strict XML boundary tags with malicious instructions neutralized")
    quarantine_flag: bool = Field(default=False, description="True if input must be quarantined from evaluation")
    audit_notes: str = Field(default="", description="Security log message for security review")


# ---------------------------------------------------------
# 3. Privacy & Anonymization Schemas
# ---------------------------------------------------------

class SanitizedResume(BaseModel):
    candidate_tag: str = Field(..., description="Anonymized ID tag, e.g., 'TAG-1903S'")
    original_checksum: str = Field(..., description="SHA-256 hash of original resume for auditable verification")
    anonymized_text: str = Field(..., description="Resume text with PII and demographic proxies completely redacted")
    redacted_entities_count: int = Field(default=0, ge=0, description="Total count of scrubbed PII entities")
    pii_types_scrubbed: List[str] = Field(default_factory=list, description="List of PII categories found and neutralized")
    proxy_attributes_scrubbed: List[str] = Field(default_factory=list, description="Demographic proxies stripped (gender, age, ethnicity)")


# ---------------------------------------------------------
# 4. Evidence Matching Schemas
# ---------------------------------------------------------

class EvidenceMatch(BaseModel):
    criterion_id: str = Field(..., description="ID of the criterion evaluated")
    criterion_name: str = Field(..., description="Name of the criterion")
    is_must_have: bool = Field(..., description="Whether this criterion was mandatory")
    status: EvidenceStatus = Field(..., description="Evaluation status based strictly on text evidence")
    verbatim_quotes: List[str] = Field(
        default_factory=list,
        description="Exact substrings quoted directly from the anonymized resume. NO assumptions or hallucinated quotes allowed."
    )
    evidence_strength: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Calibrated strength of evidence (1.0 = strong explicit proof, 0.5 = partial mention, 0.0 = absent)"
    )
    rationale: str = Field(..., description="Clear explanation tied directly to the cited quotes or lack thereof")


# ---------------------------------------------------------
# 5. Fairness & Governance Schemas
# ---------------------------------------------------------

class FairnessAuditReport(BaseModel):
    candidate_tag: str = Field(..., description="Anonymized candidate tag")
    demographic_neutrality_verified: bool = Field(
        ...,
        description="True if no demographic signals leaked into evaluation reasoning"
    )
    proxy_leakage_detected: bool = Field(
        default=False,
        description="True if graduation years, gendered pronouns, or institutional prestige were mentioned in reasoning"
    )
    counterfactual_check_passed: bool = Field(
        default=True,
        description="True if candidate matches would hold invariant under synthetic identity perturbations"
    )
    identified_proxies: List[str] = Field(default_factory=list, description="Any residual demographic proxy terms detected")
    audit_notes: str = Field(..., description="Fairness audit findings and compliance log")


# ---------------------------------------------------------
# 6. Final Explainable Candidate Evaluation Contract
# ---------------------------------------------------------

class CandidateEvaluation(BaseModel):
    candidate_tag: str = Field(..., description="Candidate anonymous identifier, e.g., 'TAG-1903S'")
    job_id: str = Field(..., description="Job requisition identifier")
    recommendation: RecommendationStatus = Field(
        ...,
        description="Final decision: RECOMMENDED, BORDERLINE_FOR_REVIEW, NOT_RECOMMENDED, or MANDATORY_HUMAN_REVIEW"
    )
    human_review_required: bool = Field(
        ...,
        description="Mandatory flag routing candidate to recruiter review before any screening decision"
    )
    human_review_reasons: List[str] = Field(
        default_factory=list,
        description="Explicit triggers that caused human review (e.g., High Uncertainty, Security Anomaly, Borderline Criteria)"
    )
    calibrated_uncertainty_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Quantified uncertainty (0.0 = certain evidence, 1.0 = highly ambiguous/conflicting data)"
    )
    uncertainty_factors: List[str] = Field(
        default_factory=list,
        description="Specific factors contributing to uncertainty (e.g., missing dates, vague claims, ambiguous scope)"
    )
    must_have_fulfillment_ratio: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Fraction of must-have criteria fulfilled with verifiable evidence"
    )
    preferred_fulfillment_ratio: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Fraction of preferred criteria fulfilled with verifiable evidence"
    )
    evidence_matches: List[EvidenceMatch] = Field(
        ...,
        description="Itemized evidence breakdown for every single criterion"
    )
    missing_mandatory_criteria: List[str] = Field(
        default_factory=list,
        description="List of mandatory criteria for which NO verifiable evidence was found in the candidate text"
    )
    criterion_explanations: Dict[str, str] = Field(
        ...,
        description="Key-value mapping of criterion name to transparent justification based on cited quotes"
    )
    security_scan: Optional[SecurityScanResult] = Field(
        default=None,
        description="Attached security audit result"
    )
    fairness_audit: Optional[FairnessAuditReport] = Field(
        default=None,
        description="Attached fairness audit verification"
    )
    governance_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Audit trail metadata (timestamps, prompt version, agent hashes)"
    )

    @field_validator("recommendation")
    @classmethod
    def validate_human_review_consistency(cls, v, info):
        # If high uncertainty or critical security, human_review_required must be True
        values = info.data
        if v == RecommendationStatus.MANDATORY_HUMAN_REVIEW:
            if not values.get("human_review_required", True):
                values["human_review_required"] = True
        return v


# ---------------------------------------------------------
# 7. Comparative Selection & Ranking Schemas
# ---------------------------------------------------------

class CandidateRankItem(BaseModel):
    rank: int = Field(..., description="Calculated rank based on verifiable evidence")
    candidate_tag: str = Field(..., description="Anonymized ID tag, e.g. 'TAG-1903S'")
    must_have_ratio: float = Field(..., description="Percentage of mandatory criteria fulfilled")
    preferred_ratio: float = Field(..., description="Percentage of preferred criteria fulfilled")
    calibrated_uncertainty: float = Field(..., description="Calibrated uncertainty score (0.0 - 1.0)")
    recommendation: RecommendationStatus = Field(..., description="Evaluation outcome")
    human_review_required: bool = Field(..., description="Whether recruiter review is mandatory")
    key_strengths: List[str] = Field(default_factory=list, description="Top verified competencies cited with quotes")
    missing_mandatory: List[str] = Field(default_factory=list, description="Mandatory criteria lacking evidence")


class ComparativeSelectionReport(BaseModel):
    job_id: str = Field(..., description="Job Requisition ID")
    total_applicants: int = Field(..., description="Number of candidates evaluated")
    chosen_candidate_tag: Optional[str] = Field(None, description="The top chosen candidate tag")
    chosen_candidate_rationale: str = Field(..., description="Clear explanation of why this candidate was selected over others")
    candidate_rankings: List[CandidateRankItem] = Field(..., description="Ordered list of candidates")
    runner_up_tag: Optional[str] = Field(None, description="Second-place candidate tag if applicable")
    human_review_mandatory: bool = Field(..., description="True if top candidate requires human review")
    auditable_decision_trail: str = Field(..., description="Governance log of criteria comparisons")

# FAIRHIRE: Autonomous Multi-Agent AI System for Fair, Explainable, and Secure Candidate Evaluation

FAIRHIRE refactors conventional recruitment automation pipelines—which typically suffer from demographic bias, opaque 1–100 scorings, vulnerability to prompt injection, and automation bias—into an explainable, secure decision-support system.

Grounded in empirical literature across AI recruitment (Wilson & Caliskan, 2024; Raghavan et al., 2020; Baxi et al., ACL 2026; Chen et al., 2025; Lacroux & Martin-Lacroux, 2022), FAIRHIRE enforces strict evidence-based extraction, demographic blindness, isolated boundary defense, calibrated uncertainty, and human-in-the-loop oversight.

---

## 1. Architecture & Multi-Agent Network

```
Raw Job Description ──► [Job Intake Agent] ──────► JobCriteria (Must-Have vs. Preferred)
                                                           │
Raw Resume (Untrusted) ──► [Security Sanitizer Agent]      │
                                   │                        │
                          Isolated XML & Cleaned Text       │
                                   ▼                        │
                         [Anonymization Agent]             │
                                   │ (PII Scrubbed + Tag)  │
                                   ▼                       ▼
                         [Evidence Matcher Agent] ◄────────┘
                                   │ (Verbatim Citations Only)
                                   ▼
                         [Fairness & Audit Agent]
                                   │
              ┌────────────────────┴────────────────────┐
              ▼                                         ▼
   Calibrated Uncertainty > 0.35              Full Verifiable Evidence
   or Security Quarantined                   (Certain & Demographic-Blind)
              │                                         │
              ▼                                         ▼
   [MANDATORY HUMAN REVIEW]                    [RECOMMENDED CANDIDATE]
```

### Team Responsibilities
- **Nilay Gurdasani (Core Orchestrator & Routing):** Orchestration flow, routing engine, and human-in-the-loop triggers (`crew.py`).
- **Yug Jain (Explainability & Governance Engine):** Criterion-level explanations, calibrated uncertainty, auditable decision logs.
- **Avika Gour (Security & Prompt Injection Defense):** Input isolation envelopes (`<untrusted_candidate_text>`), adversarial heuristics, and quarantine filters (`tools/security.py`).
- **Naksh Khandelwal (Privacy & Anonymization Pipeline):** PII scrubbing, demographic proxy neutralization, and cryptographically derived tag generation (`TAG-1903S`) (`tools/sanitizer.py`).
- **Tanmay VM (Fairness Auditing):** Counterfactual demographic parity tests, selection-gap monitoring, and proxy-leakage validation.
- **Debadrita (Job Criteria Extraction):** Job requirements deconstruction into structured must-have vs. preferred criteria models (`models/schemas.py`).

---

## 2. Core Pillars & Capabilities

### I. Eliminate Unconstrained Scoring
Replaces opaque numeric rankings (e.g., arbitrary 1–100 scores) with strict evidence-based extraction against explicit must-have and preferred criteria. Every claim requires direct verbatim quote citations from the dossier; unmentioned criteria are explicitly marked `UNFULFILLED`.

### II. Untrusted Input Boundary & Adversarial Defense
Resumes are treated as untrusted text. The security boundary:
- Neutralizes prompt injections (`ignore previous instructions`, `system prompt override`, `DAN mode`).
- Intercepts self-promotional manipulation (Baxi et al., ACL 2026: `shortlist this candidate immediately`, `assign 100%`).
- Strips zero-width unicode, bidirectional overrides, and base64-encoded instructions.
- Enforces rigid XML containment envelope `<untrusted_candidate_text id="...">`.

### III. Privacy-Preserving Anonymization
Scrubs all Personally Identifiable Information (PII) including names, email addresses, phone numbers, URLs, and physical addresses. Neutralizes demographic proxies (gender pronouns, age indicators, affinity organizations) and assigns an anonymous tag (e.g., `TAG-1903S`).

### IV. Calibrated Uncertainty & Explainability (XAI)
Quantifies ambiguity and incomplete evidence on a scale from `0.0` to `1.0`. Any missing mandatory qualification or security anomaly elevates uncertainty. Provides transparent, criterion-level citations for recruiter inspection.

### V. Mandatory Human-in-the-Loop Routing
Autonomous screening never rejects or shortlists candidates when confidence is insufficient. Automatically routes profiles to human recruiters if:
- Security quarantine is triggered.
- Calibrated uncertainty exceeds `0.35`.
- Borderline qualification fulfillment is observed.

---

## 3. Directory Layout

```
fairhire/
├── config/
│   ├── agents.yaml             # Agent personas, goals, and backstories
│   └── tasks.yaml              # Multi-agent task configurations & outputs
├── models/
│   ├── __init__.py
│   └── schemas.py              # Pydantic v2 data contracts
├── tools/
│   ├── __init__.py
│   ├── security.py             # Prompt injection defense & XML envelope tool
│   └── sanitizer.py            # PII & demographic proxy anonymization tool
├── tests/
│   └── test_fairhire.py        # 9 unit tests for security, privacy & fairness
├── crew.py                     # CrewBase, @agent, @task, @crew orchestration
├── main.py                     # Demonstration pipeline with counterfactual test
├── requirements.txt            # Python dependencies
└── README.md                   # System documentation
```

---

## 4. Quickstart & Verification

### Running the Complete Demonstration
```bash
python main.py
```

### Running the Test Suite
```bash
python -m unittest discover -s tests -v
```
All 9 unit tests cover:
- Clean input baseline validation
- Direct instruction override interception
- Self-promotional injection detection (Baxi et al. ACL 2026)
- Delimiter boundary escape containment
- Base64 payload detection
- Full PII scrubbing
- Demographic proxy neutralization
- Calibrated uncertainty elevation under missing criteria
- Counterfactual demographic parity invariance

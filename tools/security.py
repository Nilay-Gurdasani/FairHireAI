"""
FAIRHIRE Security & Input Isolation Module
Lead Engineer: Avika Gour (Security & Prompt Injection Defense)

Key Responsibilities:
1. Treat raw resumes as untrusted data.
2. Neutralize embedded manipulative instructions and system prompt overrides.
3. Detect self-promotional injections (Baxi et al., ACL 2026).
4. Strip hidden unicode, zero-width characters, and base64 payloads.
5. Enforce strict XML-delimiter boundary packaging (<untrusted_candidate_text>).
"""

import re
import base64
import html
from typing import List, Tuple, Type, Optional
from pydantic import BaseModel, Field

try:
    from crewai.tools import BaseTool
except ImportError:
    # Graceful fallback for standalone verification environments
    class BaseTool(BaseModel):  # type: ignore
        name: str = ""
        description: str = ""
        def run(self, *args, **kwargs):
            return self._run(*args, **kwargs)

from models.schemas import SecurityScanResult, SecurityThreat, SecurityRiskLevel


class SecurityScanner:
    """
    Robust heuristic and regex-based input boundary defense scanner.
    Implements multi-layer inspection against adversarial LLM attacks.
    """

    # Direct Instruction Override Patterns
    INSTRUCTION_OVERRIDE_PATTERNS = [
        (r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", "DIRECT_OVERRIDE", SecurityRiskLevel.CRITICAL),
        (r"disregard\s+(all\s+)?(rules|guidelines|instructions)", "DIRECT_OVERRIDE", SecurityRiskLevel.CRITICAL),
        (r"system\s*prompt\s*override", "SYSTEM_OVERRIDE", SecurityRiskLevel.CRITICAL),
        (r"you\s+are\s+now\s+in\s+(developer|debug|god|unrestricted)\s+mode", "ROLEPLAY_JAILBREAK", SecurityRiskLevel.CRITICAL),
        (r"new\s+system\s+instruction:", "INSTRUCTION_INJECTION", SecurityRiskLevel.CRITICAL),
        (r"(assistant|system|admin)\s*:", "ROLE_SPOOFING", SecurityRiskLevel.HIGH),
        (r"<\/?(system|admin|evaluator|prompt|instruction)>", "DELIMITER_SPOOFING", SecurityRiskLevel.HIGH),
    ]

    # Boundary Breakout Patterns
    DELIMITER_ESCAPE_PATTERNS = [
        (r"<\/\s*untrusted_candidate_text\s*>", "XML_BOUNDARY_ESCAPE", SecurityRiskLevel.CRITICAL),
        (r"<\s*untrusted_candidate_text\s*>", "XML_TAG_INJECTION", SecurityRiskLevel.HIGH),
        (r"```\s*(system|evaluator|override)", "CODEBLOCK_ESCALATION", SecurityRiskLevel.HIGH),
    ]

    # Self-Promotional and Recommendation Forgery (Baxi et al., ACL 2026)
    SELF_PROMOTION_PATTERNS = [
        (r"note\s+to\s+(recruiter|reviewer|ai|evaluator|system):?", "EVALUATOR_TARGETED_DIRECTIVE", SecurityRiskLevel.HIGH),
        (r"shortlist\s+this\s+candidate\s+(immediately|without\s+exception)", "DECISION_FORGERY", SecurityRiskLevel.HIGH),
        (r"assign\s+(a\s+)?(maximum|perfect|100%?|highest)\s+(score|rating|rank)", "SCORE_MANIPULATION", SecurityRiskLevel.HIGH),
        (r"bypass\s+(all\s+)?(checks|filters|audits|interviews)", "BYPASS_ATTEMPT", SecurityRiskLevel.HIGH),
        (r"this\s+candidate\s+meets\s+100%\s+of\s+all\s+requirements", "UNVERIFIED_ASSERTION_INJECTION", SecurityRiskLevel.MEDIUM),
    ]

    # Hidden text and CSS injection patterns
    HIDDEN_PAYLOAD_PATTERNS = [
        (r"<[^>]+style=[\"'][^\"']*(display:\s*none|font-size:\s*0|color:\s*(white|transparent|rgba\(0,0,0,0\)))[^\"']*>", "HIDDEN_CSS_TEXT", SecurityRiskLevel.HIGH),
        (r"<!--\s*(system|instruction|prompt|evaluator).*?-->", "HIDDEN_HTML_COMMENT", SecurityRiskLevel.HIGH),
    ]

    # Zero-width and non-printable unicode control characters
    ZERO_WIDTH_CHARS = [
        '\u200b',  # Zero-width space
        '\u200c',  # Zero-width non-joiner
        '\u200d',  # Zero-width joiner
        '\ufeff',  # Zero-width no-break space (BOM)
        '\u202a', '\u202b', '\u202c', '\u202d', '\u202e',  # BiDi overrides
    ]

    @classmethod
    def detect_zero_width_and_control_chars(cls, text: str) -> List[SecurityThreat]:
        threats = []
        found_chars = [char for char in cls.ZERO_WIDTH_CHARS if char in text]
        if found_chars:
            threats.append(SecurityThreat(
                threat_type="OBFUSCATION_UNICODE",
                pattern_matched=f"{len(found_chars)} hidden/bidi unicode characters",
                severity=SecurityRiskLevel.MEDIUM,
                description="Detected invisible zero-width or bidirectional control characters used to conceal prompt injection.",
                quarantine_recommended=False
            ))
        return threats

    @classmethod
    def detect_base64_payloads(cls, text: str) -> List[SecurityThreat]:
        threats = []
        # Find potential base64 strings (minimum 24 chars to avoid false positives on random words)
        matches = re.findall(r"(?:[A-Za-z0-9+/]{4}){6,}(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?", text)
        for b64 in matches:
            try:
                decoded = base64.b64decode(b64).decode("utf-8", errors="ignore")
                lower_decoded = decoded.lower()
                if any(keyword in lower_decoded for keyword in ["system", "ignore", "prompt", "shortlist", "score", "override"]):
                    threats.append(SecurityThreat(
                        threat_type="BASE64_INSTRUCTION_ENCODING",
                        pattern_matched=b64[:30] + "...",
                        severity=SecurityRiskLevel.CRITICAL,
                        description=f"Base64-encoded instruction payload detected: '{decoded[:50]}...'",
                        quarantine_recommended=True
                    ))
            except Exception:
                continue
        return threats

    @classmethod
    def scan_and_sanitize(cls, raw_text: str, candidate_id: str = "RAW_INPUT") -> SecurityScanResult:
        threats: List[SecurityThreat] = []

        # 1. Check Unicode control and zero-width characters
        threats.extend(cls.detect_zero_width_and_control_chars(raw_text))

        # 2. Check Base64 encoded attack vectors
        threats.extend(cls.detect_base64_payloads(raw_text))

        # 3. Check Regex Patterns
        all_pattern_groups = [
            cls.INSTRUCTION_OVERRIDE_PATTERNS,
            cls.DELIMITER_ESCAPE_PATTERNS,
            cls.SELF_PROMOTION_PATTERNS,
            cls.HIDDEN_PAYLOAD_PATTERNS
        ]

        for pattern_group in all_pattern_groups:
            for pattern, threat_type, severity in pattern_group:
                match = re.search(pattern, raw_text, re.IGNORECASE)
                if match:
                    quarantine = severity in [SecurityRiskLevel.CRITICAL, SecurityRiskLevel.HIGH]
                    threats.append(SecurityThreat(
                        threat_type=threat_type,
                        pattern_matched=match.group(0),
                        severity=severity,
                        description=f"Pattern '{pattern}' flagged potential prompt manipulation.",
                        quarantine_recommended=quarantine
                    ))

        # Determine overall risk
        highest_severity = SecurityRiskLevel.CLEAN
        severities = [t.severity for t in threats]
        if SecurityRiskLevel.CRITICAL in severities:
            highest_severity = SecurityRiskLevel.CRITICAL
        elif SecurityRiskLevel.HIGH in severities:
            highest_severity = SecurityRiskLevel.HIGH
        elif SecurityRiskLevel.MEDIUM in severities:
            highest_severity = SecurityRiskLevel.MEDIUM
        elif SecurityRiskLevel.LOW in severities:
            highest_severity = SecurityRiskLevel.LOW

        # 4. Perform Sanitization & Boundary Isolation
        cleaned_text = raw_text

        # Strip zero-width characters
        for char in cls.ZERO_WIDTH_CHARS:
            cleaned_text = cleaned_text.replace(char, "")

        # Escape existing XML boundary delimiters to prevent tag closure breakouts
        cleaned_text = cleaned_text.replace("<untrusted_candidate_text>", "&lt;untrusted_candidate_text&gt;")
        cleaned_text = cleaned_text.replace("</untrusted_candidate_text>", "&lt;/untrusted_candidate_text&gt;")

        # Redact active high-severity injection sentences from the text body
        for threat in threats:
            if threat.severity in [SecurityRiskLevel.CRITICAL, SecurityRiskLevel.HIGH]:
                cleaned_text = re.sub(
                    re.escape(threat.pattern_matched),
                    f"[REDACTED_SECURITY_THREAT: {threat.threat_type}]",
                    cleaned_text,
                    flags=re.IGNORECASE
                )

        # Enforce rigorous XML containment envelope
        safe_isolated_text = (
            f"<untrusted_candidate_text id=\"{candidate_id}\">\n"
            f"{cleaned_text.strip()}\n"
            f"</untrusted_candidate_text>"
        )

        quarantine_flag = highest_severity == SecurityRiskLevel.CRITICAL or any(t.quarantine_recommended for t in threats)
        is_safe = highest_severity in [SecurityRiskLevel.CLEAN, SecurityRiskLevel.LOW]

        audit_msg = f"Security Scan Completed. Detected {len(threats)} anomalies. Max Severity: {highest_severity.value}."
        if quarantine_flag:
            audit_msg += " QUARANTINE TRIGGERED: Mandatory recruiter security review required."

        return SecurityScanResult(
            candidate_id=candidate_id,
            is_safe=is_safe,
            risk_level=highest_severity,
            threats_detected=threats,
            sanitized_content=safe_isolated_text,
            quarantine_flag=quarantine_flag,
            audit_notes=audit_msg
        )


class SecurityScannerInput(BaseModel):
    raw_resume_text: str = Field(..., description="The raw unvalidated resume text provided by the candidate")
    candidate_id: Optional[str] = Field(default="UNVERIFIED_CANDIDATE", description="Reference ID for tracking")


class SecurityScannerTool(BaseTool):
    """
    CrewAI Tool wrapper for input boundary defense and prompt-injection neutralization.
    Equipped to the Security Sanitizer Agent (Avika Gour).
    """
    name: str = "security_scanner_tool"
    description: str = (
        "Scans raw applicant text for adversarial prompt injections, hidden instructions, "
        "and boundary breakouts. Neutralizes malicious payloads and wraps text in safe XML isolation."
    )
    args_schema: Type[BaseModel] = SecurityScannerInput

    def _run(self, raw_resume_text: str, candidate_id: str = "UNVERIFIED_CANDIDATE") -> str:
        scan_result = SecurityScanner.scan_and_sanitize(raw_resume_text, candidate_id)
        return scan_result.model_dump_json(indent=2)

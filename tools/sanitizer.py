"""
FAIRHIRE Privacy & Anonymization Pipeline
Lead Engineer: Naksh Khandelwal (Privacy & Anonymization Pipeline)

Key Responsibilities:
1. Scrub Personally Identifiable Information (PII) including names, emails, phones, and links.
2. Neutralize demographic proxies (gender pronouns, age indicators, affinity organizations).
3. Assign deterministic or cryptographic candidate tags (e.g., 'TAG-1903S').
4. Retain SHA-256 hash for secure recruiter verification while preventing demographic bias.
"""

import re
import hashlib
import random
from typing import List, Tuple, Type, Optional, Set
from pydantic import BaseModel, Field

try:
    from crewai.tools import BaseTool
except ImportError:
    class BaseTool(BaseModel):  # type: ignore
        name: str = ""
        description: str = ""
        def run(self, *args, **kwargs):
            return self._run(*args, **kwargs)

from models.schemas import SanitizedResume


class AnonymizerEngine:
    """
    Regex and heuristic engine for scrubbing PII and demographic proxies
    to enforce demographic neutrality (Wilson & Caliskan, 2024; Raghavan et al., 2020).
    """

    # Email pattern
    EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")

    # Phone number patterns (various international and domestic formats)
    PHONE_REGEX = re.compile(
        r"(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}\b"
    )

    # URL, Social profiles and repositories
    URL_REGEX = re.compile(
        r"\b(?:https?:\/\/|www\.)\S+\b|"
        r"\b(?:linkedin\.com|github\.com|gitlab\.com|twitter\.com|x\.com)\/[\w\-./]+\b",
        re.IGNORECASE
    )

    # Physical address / postal patterns
    ZIP_REGEX = re.compile(r"\b\d{5}(?:-\d{4})?\b")
    STREET_REGEX = re.compile(
        r"\b\d{1,5}\s+[\w\s]{1,25}(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Court|Ct)\b",
        re.IGNORECASE
    )

    # Gender pronouns (replaced with neutral tokens or singular 'they')
    PRONOUN_MAP = [
        (re.compile(r"\bhe\b", re.IGNORECASE), "[PRONOUN]"),
        (re.compile(r"\bshe\b", re.IGNORECASE), "[PRONOUN]"),
        (re.compile(r"\bhim\b", re.IGNORECASE), "[PRONOUN]"),
        (re.compile(r"\bher\b", re.IGNORECASE), "[PRONOUN]"),
        (re.compile(r"\bhis\b", re.IGNORECASE), "[PRONOUN]"),
        (re.compile(r"\bhers\b", re.IGNORECASE), "[PRONOUN]"),
        (re.compile(r"\bhimself\b", re.IGNORECASE), "[THEMSELF]"),
        (re.compile(r"\bherself\b", re.IGNORECASE), "[THEMSELF]"),
    ]

    # Demographic affinity proxies (fraternities, demographic identity clubs, ethnic societies)
    DEMOGRAPHIC_AFFINITY_PATTERNS = [
        (re.compile(r"\b(society\s+of\s+women\s+engineers|swe)\b", re.IGNORECASE), "[PROFESSIONAL_DIVERSITY_ASSOCIATION]"),
        (re.compile(r"\b(national\s+society\s+of\s+black\s+engineers|nsbe)\b", re.IGNORECASE), "[PROFESSIONAL_DIVERSITY_ASSOCIATION]"),
        (re.compile(r"\b(society\s+of\s+hispanic\s+professional\s+engineers|shpe)\b", re.IGNORECASE), "[PROFESSIONAL_DIVERSITY_ASSOCIATION]"),
        (re.compile(r"\b(women\s+in\s+(tech|engineering|stem|cs|computing))\b", re.IGNORECASE), "[PROFESSIONAL_DIVERSITY_ASSOCIATION]"),
        (re.compile(r"\b(black\s+girls\s+code|out\s+in\s+tech|o-stem|ostem)\b", re.IGNORECASE), "[PROFESSIONAL_DIVERSITY_ASSOCIATION]"),
        (re.compile(r"\b(fraternity|sorority|alpha\s+phi\s+alpha|delta\s+sigma\s+theta)\b", re.IGNORECASE), "[STUDENT_ORGANIZATION]"),
    ]

    # Age indicators (specific birth years, graduation dates prior to 2012)
    AGE_INDICATOR_PATTERNS = [
        (re.compile(r"\b(?:born\s+in|dob:?|birth\s*date:?)\s*(?:19|20)\d{2}\b", re.IGNORECASE), "[DOB_REDACTED]"),
        (re.compile(r"\b(?:high\s+school\s+diploma|hs\s+graduated|matriculated\s+in)\s*(?:19|20)\d{2}\b", re.IGNORECASE), "[EARLY_EDUCATION_DATE_REDACTED]"),
        (re.compile(r"\b\d{1,2}\s*[-–]\s*year\s*[-–]\s*old\b", re.IGNORECASE), "[AGE_INDICATOR_REDACTED]"),
    ]

    # Header / Name detection patterns
    NAME_HEADER_PATTERNS = [
        re.compile(r"^\s*(?:Name|Candidate|Full\s+Name)\s*:\s*([A-Za-z\s.'-]+)$", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s*$", re.MULTILINE)  # Top line candidate name
    ]

    @classmethod
    def generate_candidate_tag(cls, text: str) -> str:
        """
        Generates a consistent anonymized tag in the format TAG-1903S
        derived from the SHA-256 hash of the content.
        """
        hasher = hashlib.sha256(text.encode("utf-8")).hexdigest()
        # Format: TAG- + first 4 hex converted to int modulo 10000 + capital letter
        num_part = int(hasher[:6], 16) % 9000 + 1000
        letter_part = chr(ord('A') + (int(hasher[6:8], 16) % 26))
        return f"TAG-{num_part}{letter_part}"

    @classmethod
    def anonymize(cls, raw_text: str, candidate_tag: Optional[str] = None) -> SanitizedResume:
        """
        Processes candidate text through multi-pass PII and demographic scrubbing.
        """
        checksum = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        if not candidate_tag:
            candidate_tag = cls.generate_candidate_tag(raw_text)

        cleaned_text = raw_text
        pii_types_found: Set[str] = set()
        proxy_types_found: Set[str] = set()
        redaction_count = 0

        # 1. Scrub Emails
        email_matches = cls.EMAIL_REGEX.findall(cleaned_text)
        if email_matches:
            redaction_count += len(email_matches)
            pii_types_found.add("EMAIL_ADDRESS")
            cleaned_text = cls.EMAIL_REGEX.sub("[EMAIL_REDACTED]", cleaned_text)

        # 2. Scrub Phone Numbers
        phone_matches = cls.PHONE_REGEX.findall(cleaned_text)
        # Filter false positive short strings
        real_phones = [p for p in phone_matches if len(re.sub(r"\D", "", p)) >= 10]
        if real_phones:
            redaction_count += len(real_phones)
            pii_types_found.add("PHONE_NUMBER")
            for phone in real_phones:
                cleaned_text = cleaned_text.replace(phone, "[PHONE_REDACTED]")

        # 3. Scrub URLs and Repository links
        url_matches = cls.URL_REGEX.findall(cleaned_text)
        if url_matches:
            redaction_count += len(url_matches)
            pii_types_found.add("URL_OR_SOCIAL_PROFILE")
            cleaned_text = cls.URL_REGEX.sub("[PROFILE_URL_REDACTED]", cleaned_text)

        # 4. Scrub Street Addresses & Postal Codes
        street_matches = cls.STREET_REGEX.findall(cleaned_text)
        if street_matches:
            redaction_count += len(street_matches)
            pii_types_found.add("PHYSICAL_ADDRESS")
            cleaned_text = cls.STREET_REGEX.sub("[ADDRESS_REDACTED]", cleaned_text)

        zip_matches = cls.ZIP_REGEX.findall(cleaned_text)
        if zip_matches:
            redaction_count += len(zip_matches)
            pii_types_found.add("POSTAL_CODE")
            cleaned_text = cls.ZIP_REGEX.sub("[POSTAL_CODE_REDACTED]", cleaned_text)

        # 5. Scrub Gender Pronouns
        for pattern, replacement in cls.PRONOUN_MAP:
            matches = pattern.findall(cleaned_text)
            if matches:
                redaction_count += len(matches)
                proxy_types_found.add("GENDER_PRONOUN")
                cleaned_text = pattern.sub(replacement, cleaned_text)

        # 6. Scrub Demographic Affinity Proxies
        for pattern, replacement in cls.DEMOGRAPHIC_AFFINITY_PATTERNS:
            matches = pattern.findall(cleaned_text)
            if matches:
                redaction_count += len(matches)
                proxy_types_found.add("DEMOGRAPHIC_AFFINITY")
                cleaned_text = pattern.sub(replacement, cleaned_text)

        # 7. Scrub Age Indicators & Birthdates
        for pattern, replacement in cls.AGE_INDICATOR_PATTERNS:
            matches = pattern.findall(cleaned_text)
            if matches:
                redaction_count += len(matches)
                proxy_types_found.add("AGE_INDICATOR")
                cleaned_text = pattern.sub(replacement, cleaned_text)

        # 8. Scrub Candidate Name from Header
        for pattern in cls.NAME_HEADER_PATTERNS:
            if pattern.search(cleaned_text):
                cleaned_text = pattern.sub(f"Candidate: {candidate_tag}", cleaned_text)
                pii_types_found.add("CANDIDATE_NAME")
                redaction_count += 1
                break

        # Header tag prefix
        final_anonymized_text = f"=== ANONYMIZED CANDIDATE DOSSIER: {candidate_tag} ===\n{cleaned_text.strip()}"

        return SanitizedResume(
            candidate_tag=candidate_tag,
            original_checksum=checksum,
            anonymized_text=final_anonymized_text,
            redacted_entities_count=redaction_count,
            pii_types_scrubbed=sorted(list(pii_types_found)),
            proxy_attributes_scrubbed=sorted(list(proxy_types_found))
        )


class AnonymizerInput(BaseModel):
    resume_text: str = Field(..., description="The candidate resume or sanitized text to be scrubbed")
    candidate_tag: Optional[str] = Field(default=None, description="Optional override candidate tag (e.g. 'TAG-1903S')")


class AnonymizerTool(BaseTool):
    """
    CrewAI Tool wrapper for privacy-preserving anonymization.
    Equipped to the Anonymization Agent (Naksh Khandelwal).
    """
    name: str = "anonymizer_tool"
    description: str = (
        "Scrubs all Personally Identifiable Information (names, emails, phones, URLs, addresses) "
        "and demographic proxies (pronouns, age indicators, affinity organizations), assigning a neutral tag (e.g., 'TAG-1903S')."
    )
    args_schema: Type[BaseModel] = AnonymizerInput

    def _run(self, resume_text: str, candidate_tag: Optional[str] = None) -> str:
        sanitized = AnonymizerEngine.anonymize(resume_text, candidate_tag)
        return sanitized.model_dump_json(indent=2)

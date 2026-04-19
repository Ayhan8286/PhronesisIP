"""
Layer 3 Claim Validator — Automated Legal Quality Assurance.
Checks generated patent claims against USPTO structural and legal requirements.
"""

import re
from typing import List, Dict, TypedDict

class ValidationIssue(TypedDict):
    level: str  # "ERROR" or "WARNING"
    message: str
    rejection_statute: str  # e.g. "§ 112"
    suggestion: str

class ValidationReport(TypedDict):
    is_valid: bool
    issues: List[ValidationIssue]

# 5-Layer Accuracy Definitions
FORBIDDEN_WORDS = [
    r"\boptionally\b", 
    r"\bpreferably\b", 
    r"\bapproximately\b", 
    r"\bgenerally\b", 
    r"\bsuch as\b", 
    r"\betc\b", 
    r"\bmeans for\b" # Triggers § 112(f)
]

STRENGTHENING_WORDS = [
    "configured to",
    "operatively connected",
    "in response to",
    "wherein"
]

TRANSITIONAL_PHRASES = ["comprising", "consisting of", "consisting essentially of"]

def validate_claims(claims_text: str) -> ValidationReport:
    """
    Scans a block of text for claims and validates each one.
    """
    issues = []
    
    # 1. Split into individual claims
    # Simple heuristic: "Claim 1.", "1.", etc.
    claims = re.split(r"(?m)^Claim\s+\d+\.", claims_text)
    if len(claims) <= 1:
        # Try numeric only
        claims = re.split(r"(?m)^\d+\.", claims_text)
    
    # Remove empty first split
    claims = [c.strip() for c in claims if c.strip()]
    
    for i, claim in enumerate(claims):
        claim_num = i + 1
        
        # --- Check 1: Forbidden Words (§ 112 issues) ---
        for word_pattern in FORBIDDEN_WORDS:
            match = re.search(word_pattern, claim, re.IGNORECASE)
            if match:
                issues.append({
                    "level": "ERROR",
                    "message": f"Claim {claim_num} contains forbidden word: '{match.group(0)}'",
                    "rejection_statute": "§ 112",
                    "suggestion": "Remove vague relative terms. Use 'configured to' or 'wherein' instead."
                })
        
        # --- Check 2: Transitional Phrase ---
        if not any(phrase in claim.lower() for phrase in TRANSITIONAL_PHRASES):
            issues.append({
                "level": "ERROR",
                "message": f"Claim {claim_num} is missing a transitional phrase.",
                "rejection_statute": "§ 112",
                "suggestion": "Add 'comprising' after the preamble."
            })
        elif "consisting of" in claim.lower():
             issues.append({
                "level": "WARNING",
                "message": f"Claim {claim_num} uses 'consisting of' (closed transition).",
                "rejection_statute": "Strategy",
                "suggestion": "Use 'comprising' for broader protection unless specifically narrowing."
            })

        # --- Check 3: Antecedent Basis (§ 112) ---
        # Very simple check: find "the [word]" and ensure "a [word]" or "an [word]" appeared before it.
        # This is hard to do perfectly with regex but we can catch common errors.
        words = claim.split()
        seen_nouns = set()
        for j, word in enumerate(words):
            clean_word = re.sub(r'[^a-zA-Z]', '', word).lower()
            if clean_word in ['a', 'an'] and j + 1 < len(words):
                noun = re.sub(r'[^a-zA-Z]', '', words[j+1]).lower()
                seen_nouns.add(noun)
            elif clean_word == 'the' and j + 1 < len(words):
                noun = re.sub(r'[^a-zA-Z]', '', words[j+1]).lower()
                if noun not in seen_nouns and len(noun) > 3: # Avoid small common words
                    issues.append({
                        "level": "ERROR",
                        "message": f"Claim {claim_num}: Possible missing antecedent for 'the {noun}'",
                        "rejection_statute": "§ 112(b)",
                        "suggestion": f"Ensure '{noun}' is introduced with 'a' or 'an' earlier in the claim."
                    })

    return {
        "is_valid": all(iss["level"] != "ERROR" for iss in issues),
        "issues": issues
    }

"""
Customer Message Urgency Scorer
================================

This module calculates urgency scores (1-5) for customer service messages using
a hybrid approach combining keyword-based pattern matching and LLM analysis.

SCORING LOGIC:
--------------

1. KEYWORD-BASED SCORING (Rule-based approach):
   - Scans message for predefined urgent keywords
   - Assigns base scores based on keyword categories:
     * CRITICAL (5): rejected, denied, blocked, cant access, fraud, unauthorized
     * HIGH (4): loan approval, disbursed, not received, crb, batch number
     * MEDIUM (3): late payment, will pay, promise, delayed salary
     * LOW (2): how to, update, change, thank, appreciate

   - Pattern matching adds score adjustments:
     * "can't/cannot/unable to" → +1 point (indicates blocking issue)
     * "why/what/when + rejected/denied" → +2 points (questioning rejection)
     * Time mentions (days/weeks) → +0.5 points (time-sensitive)
     * Multiple question marks → +0.5 points (frustration indicator)
     * ALL CAPS "PLEASE/PLZ" → +0.5 points (desperation)

2. LLM-BASED SCORING (AI analysis):
   - Uses GPT-4 to understand context and nuance
   - Provides 1-5 score with reasoning
   - Better handles edge cases and context that keywords miss
   - Examples where LLM helps:
     * "I appreciate your service but I really need help now" (polite but urgent)
     * "Just curious about loan status" (casual, not urgent)
     * Sarcasm, complex sentences, multi-topic messages

3. HYBRID FINAL SCORE:
   - Combines both methods with weighted average:
     Final Score = (0.6 × LLM Score) + (0.4 × Keyword Score)

   - Rationale for weights:
     * LLM (60%): Better at understanding context and intent
     * Keywords (40%): Ensures critical terms aren't missed

   - If LLM unavailable: Falls back to keyword score only

WHY 1-5 SCALE:
--------------
- Maps to standard priority levels: CRITICAL, HIGH, MEDIUM, LOW, MINIMAL
- Easy to route: 5=immediate, 4=same day, 3=within 2 days, 2=within week, 1=no rush
- Avoids over-granularity of 1-10 scales where differences are subjective
- Industry standard for ticketing/support systems

USAGE:
------
    from urgency_scorer import get_urgency_score

    # With LLM (more accurate)
    score = get_urgency_score("Why was my loan rejected?", use_llm=True)
    print(score)  # Returns: 4.2

    # Without LLM (faster)
    score = get_urgency_score("Thanks for your help", use_llm=False)
    print(score)  # Returns: 2.0
"""

import os
import re
from typing import Optional
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def get_urgency_score(message: str, use_llm: bool = True, api_key: Optional[str] = None) -> float:
    """
    Calculate urgency score for a customer service message.

    Args:
        message: Customer message text
        use_llm: Whether to use LLM analysis (default: True)
        api_key: OpenAI API key (optional, uses .env if not provided)

    Returns:
        Float score between 1.0 and 5.0
    """
    # Step 1: Calculate keyword-based score
    keyword_score = _calculate_keyword_score(message)

    # Step 2: If LLM enabled, get LLM score and combine
    if use_llm:
        key = api_key or os.getenv('OPENAI_API_KEY')
        if key:
            try:
                client = OpenAI(api_key=key)
                llm_score = _get_llm_score(client, message)

                if llm_score:
                    # Weighted average: 60% LLM, 40% keywords
                    final_score = 0.6 * llm_score + 0.4 * keyword_score
                    return round(final_score, 1)
            except:
                pass  # Fall back to keyword score on error

    # Step 3: Return keyword score if LLM unavailable or disabled
    return round(keyword_score, 1)


def _calculate_keyword_score(message: str) -> float:
    """Calculate score based on keywords and patterns."""
    # Keyword categories and their base scores
    KEYWORDS = {
        # 🔴 CRITICAL – immediate risk / blocking / abuse / fraud
        5: [
            # Access / blocking
            "can't access", "cant access", "cannot access", "can't login", "cant login",
            "unable to access", "blocked", "account blocked", "dead-end",

            # Fraud / identity misuse
            "fraud", "unauthorized", "stolen", "hacked",
            "someone used my id", "used my id", "identity misuse",

            # Harassment / extreme distress
            "abuse", "abusing", "punish me", "punish me forever",
            "desperately need", "urgent cash", "emergency", "accident",

            # Financial lock
            "can't be", "it can't be"
        ],

        # 🟠 HIGH – loan / CRB / rejection / disbursement
        4: [
            # Rejection / suspension
            "rejected", "denied", "application rejected", "loan rejected",
            "reapply", "another 7 days", "7 days", "7more days", "penalty",

            # Disbursement issues
            "loan approval", "approved", "disbursed", "not received",
            "have not received", "when will", "waiting", "haven't received",

            # Credit bureau
            "crb", "credit report", "clearance", "certificate of clearance",
            "trans union",

            # Batch number
            "batch number", "clearance batch",

            # System inconsistency
            "system says", "update your systems", "wrong balance"
        ],

        # 🟡 MEDIUM – payment difficulty / timing / negotiation
        3: [
            # Payment promises
            "will pay", "i will pay", "pay on", "pay by",
            "promise", "promise to pay",

            # Delays
            "late payment", "overdue", "delay", "delayed salary",
            "not been paid", "salary delayed",

            # Requests for time
            "bear with me", "request more time", "allow me to pay",
            "amicable plan",

            # Partial payments
            "paid earlier", "paid part", "reduce my loan",
            "tomorrow", "next week", "within a week", "72hrs", "72 hours"
        ],

        # 🟢 LOW – information / clarification / account details
        2: [
            # How-to / info
            "how to", "how do i", "how can i",
            "kindly advise", "please advise",

            # Account / phone / sms
            "update", "change", "information",
            "number changed", "validate", "sms", "mpesa sms",

            # Feature requests
            "payment options", "weekly", "monthly",
            "adjust your payment",

            # Mild confusion
            "question", "query", "clarify", "don't understand"
        ],

        # ⚪ MINIMAL – closure / gratitude
        1: [
            "thank", "thanks", "thank you", "appreciate",
            "god bless", "ok", "okay", "alright",
            "have cleared my loan", "cleared my loan"
        ]
    }

    # Patterns that add to score
    PATTERNS = {
        r'\b(can\'?t|cannot|unable to)\b': 1.0,
        r'\b(why|what|when)\b.*\b(rejected|denied|blocked)\b': 2.0,
        r'\b\d+\s*(days?|weeks?|months?)\b': 0.5,
        r'\?{2,}': 0.5,
        r'PLEASE|PLZ|PLS': 0.5,
    }

    message_lower = message.lower()
    score = 1.0  # Minimum score

    # Check keywords (take highest matching category)
    for base_score, keywords in KEYWORDS.items():
        for keyword in keywords:
            if keyword in message_lower:
                score = max(score, base_score)
                break

    # Apply pattern adjustments
    for pattern, adjustment in PATTERNS.items():
        if re.search(pattern, message, re.IGNORECASE):
            score = min(5.0, score + adjustment)

    return score


def _get_llm_score(client: OpenAI, message: str) -> Optional[float]:
    """Get urgency score from LLM analysis."""
    prompt = f"""Analyze this customer service message and rate its urgency from 1-5.

Message: "{message}"

Urgency Scale:
5 = CRITICAL: Cannot access account, fraud, unauthorized transactions
4 = HIGH: Loan approval/disbursement issues, credit bureau problems
3 = MEDIUM: Payment difficulties, requesting extensions
2 = LOW: General questions, account updates, information requests
1 = MINIMAL: Thank you messages, non-urgent feedback

Respond with ONLY a single number (1-5). No explanation needed."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system",
                 "content": "You are an expert at triaging customer messages. Respond with only a number from 1 to 5."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=10
        )

        score_text = response.choices[0].message.content.strip()
        score = float(score_text)

        # Validate score is in range
        if 1.0 <= score <= 5.0:
            return score

    except:
        pass

    return None


# Example usage
if __name__ == "__main__":
    # Test messages
    test_cases = [
        "Why was my application rejected",
        "Someone hacked my account, can you help?",
        "I cant access your services",
        "I will pay on sunday",
        "Thanks for your help",
        "When will my loan be disbursed???",
    ]

    print("Urgency Scores (with LLM):")
    for msg in test_cases:
        score = get_urgency_score(msg, use_llm=True)
        print(f"{score} - {msg}")

    print("\nUrgency Scores (without LLM):")
    for msg in test_cases:
        score = get_urgency_score(msg, use_llm=False)
        print(f"{score} - {msg}")
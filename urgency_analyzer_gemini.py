import os
import re
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


def get_urgency_score(
    message: str,
    use_llm: bool = True,
    api_key: Optional[str] = None
) -> float:
    keyword_score = _calculate_keyword_score(message)

    if use_llm:
        key = api_key or os.getenv("GEMINI_API_KEY")

        if not key:
            print("⚠️ No Gemini API key found. Using keyword-only scoring.")
            return round(keyword_score, 1)

        try:
            llm_score = _get_llm_score(message, key)

            if llm_score is not None:
                print(f"Gemini score: {llm_score}")
                final_score = 0.6 * llm_score + 0.4 * keyword_score
                return round(final_score, 1)
            else:
                print(f"⚠️ Gemini returned no score for: {message[:50]}...")

        except Exception as e:
            print(f"❌ Gemini Error: {type(e).__name__}: {str(e)}")
            print(f"   Falling back to keyword score for: {message[:50]}...")

    return round(keyword_score, 1)


def _calculate_keyword_score(message: str) -> float:
    """Calculate score based on keywords and patterns."""

    KEYWORDS = {
        5: [
            "can't access", "cant access", "cannot access", "can't login", "cant login",
            "unable to access", "blocked", "account blocked", "dead-end",
            "fraud", "unauthorized", "stolen", "hacked",
            "someone used my id", "identity misuse",
            "abuse", "desperately need", "urgent cash", "emergency", "accident",
            "it can't be"
        ],
        4: [
            "rejected", "denied", "loan rejected",
            "reapply", "7 days", "penalty",
            "loan approval", "approved", "disbursed", "not received",
            "waiting", "haven't received",
            "crb", "credit report", "clearance",
            "batch number",
            "wrong balance"
        ],
        3: [
            "will pay", "promise to pay",
            "late payment", "overdue", "delay",
            "salary delayed",
            "request more time",
            "tomorrow", "next week", "72 hours"
        ],
        2: [
            "how to", "how do i",
            "please advise",
            "update", "change",
            "payment options",
            "question", "clarify"
        ],
        1: [
            "thank", "thanks", "appreciate",
            "ok", "okay"
        ]
    }

    PATTERNS = {
        r'\b(can\'?t|cannot|unable to)\b': 1.0,
        r'\b(why|what|when)\b.*\b(rejected|denied|blocked)\b': 2.0,
        r'\d+\s*(days?|weeks?)': 0.5,
        r'\?{2,}': 0.5,
    }

    message_lower = message.lower()
    score = 1.0

    for base_score, keywords in KEYWORDS.items():
        for keyword in keywords:
            if keyword in message_lower:
                score = max(score, base_score)
                break

    for pattern, adjustment in PATTERNS.items():
        if re.search(pattern, message, re.IGNORECASE):
            score = min(5.0, score + adjustment)

    return score


def _get_llm_score(message: str, api_key: str) -> Optional[float]:
    """Get urgency score from Gemini (new SDK)."""

    try:
        from google import genai
        import re

        client = genai.Client(api_key=api_key)

        prompt = f"""Analyze this customer service message and rate its urgency from 1-5.

Message: "{message}"

Urgency Scale:
5 = CRITICAL: Cannot access account, fraud, unauthorized transactions
4 = HIGH: Loan approval/disbursement issues, credit bureau problems
3 = MEDIUM: Payment difficulties, requesting extensions
2 = LOW: General questions, account updates, information requests
1 = MINIMAL: Thank you messages

Respond with ONLY a single number (1-5)."""

        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",  # you can switch to gemini-3-flash-preview if needed
            contents=prompt
        )

        # ✅ safe extraction
        text = response.text.strip() if response.text else ""

        if not text:
            return None

        # ✅ robust parsing
        match = re.search(r"[1-5]", text)
        if match:
            return float(match.group())

    except Exception as e:
        print(f"❌ Gemini Error: {e}")

    return None

# ----------- TEST -----------
if __name__ == "__main__":
    test_cases = [
        "Why was my application rejected",
        "Someone hacked my account, help!",
        "I cant access your services",
        "I will pay on sunday",
        "Thanks for your help",
        "When will my loan be disbursed???",
    ]

    print("With Gemini:")
    for msg in test_cases:
        print(get_urgency_score(msg, use_llm=True), "-", msg)

    print("\nWithout LLM:")
    for msg in test_cases:
        print(get_urgency_score(msg, use_llm=False), "-", msg)
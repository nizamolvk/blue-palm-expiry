import os


def generate_draft(prompt: str) -> dict[str, str]:
    mode = os.environ.get("LLM_MODE", "mock")
    if mode != "mock":
        raise RuntimeError("only mock LLM mode is supported")
    return {
        "subject": "Expiry reminder",
        "body": f"Please review the upcoming expiry.\n\n{prompt}",
    }

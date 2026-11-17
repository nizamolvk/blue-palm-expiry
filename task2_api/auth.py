from fastapi import Header, HTTPException

from task2_api.config import api_key


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = api_key()
    if not expected or x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")

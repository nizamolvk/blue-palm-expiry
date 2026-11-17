import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    item_id: str
    branch: str
    item_type: str
    item_name: str
    responsible_email: str | None
    expiry_date: date | None
    annual_cost_usd: int | None
    source_row: int | None
    needs_review: str | None
    review_reason: str | None


class ExpiringItemOut(ItemOut):
    status: Literal["expired", "expiring"]
    days_left: int


class ItemCreate(BaseModel):
    item_id: str = Field(min_length=1)
    branch: Literal["Colombo", "Dubai"]
    item_type: str = Field(min_length=1)
    item_name: str = Field(min_length=1)
    responsible_email: str
    expiry_date: date
    annual_cost_usd: int = Field(ge=0)

    @field_validator("responsible_email")
    @classmethod
    def check_email(cls, value: str) -> str:
        if EMAIL_RE.fullmatch(value) is None:
            raise ValueError("invalid email")
        return value

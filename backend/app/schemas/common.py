from typing import Any, Optional
from pydantic import BaseModel, Field  # type: ignore

class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Any] = Field(default_factory=dict)

class ErrorResponse(BaseModel):
    error: ErrorDetail

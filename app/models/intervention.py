from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field

from app.models.anamnesis import AnamnesisInput


class InterventionRequest(BaseModel):
    anamnesis: AnamnesisInput
    analysis_text: str = Field(..., description="Full FBA text from the clinical AI (both parts)")


class InterventionResponse(BaseModel):
    plan: str = Field(..., description="Full LIMA-based intervention plan text (markdown)")
    cache_hit: bool = Field(False, description="Whether the prompt cache was hit")
    input_tokens: int
    output_tokens: int

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class FrequencyEnum(str, Enum):
    none = "none"
    low = "low"
    medium = "medium"
    high = "high"


class LivingEnvironment(str, Enum):
    inside = "inside"
    outside = "outside"
    both = "both"


class AnamnesisInput(BaseModel):
    # Dog profile
    dog_name: str = Field(..., description="Dog's name")
    dog_age: str = Field(..., description="Age (e.g. '3 years', '8 months')")
    breed: str = Field(..., description="Breed or mix")
    weaning_age_weeks: Optional[int] = Field(None, description="Age at weaning / separation from litter (weeks)")

    # Medical
    chronic_disease: bool = Field(False, description="Has chronic disease?")
    chronic_disease_detail: Optional[str] = Field(None, description="Detail if chronic_disease is True")

    # Living situation
    living_environment: LivingEnvironment = Field(LivingEnvironment.inside)
    household_members: int = Field(..., ge=1, description="Number of people in household")
    children_present: bool = Field(False)
    other_dogs: bool = Field(False)
    other_dogs_detail: Optional[str] = None

    # Environment & exercise
    urban_rural: Optional[str] = Field(None, description="'campo', 'periferia' or 'ciudad'")
    daily_walks: bool = Field(False, description="Has daily walks?")
    walks_per_day: Optional[int] = Field(None, description="Number of walks per day")

    # Behavior problem
    problem_description: str = Field(..., description="Owner's description of the problem")
    when_it_happens: str = Field(..., description="When / in what context does it occur?")
    frequency: FrequencyEnum = Field(FrequencyEnum.medium)
    where_it_happens: Optional[str] = Field(None, description="Location / environment where it occurs")
    who_is_present: Optional[str] = Field(None, description="Who is present when it occurs?")

    # Aggression specifics (optional)
    involves_aggression: bool = Field(False)
    aggression_distance_cm: Optional[int] = Field(None, description="Distance at which aggression starts (cm)")

    # History
    previous_attempts: Optional[str] = Field(None, description="What has the owner tried so far?")
    owner_theory: Optional[str] = Field(None, description="Owner's hypothesis about the cause")


class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    source: str          # filename or document title
    page: Optional[int]
    score: float


class AnalysisResponse(BaseModel):
    analysis: str
    sources: list[RetrievedChunk]
    cache_hit: bool = Field(False, description="Whether the prompt cache was hit")
    input_tokens: int
    output_tokens: int

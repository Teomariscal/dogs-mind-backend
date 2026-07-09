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


class FavoriteReward(str, Enum):
    food = "food"
    ball = "ball"
    petting = "petting"
    none = "none"           # "Nada le motiva" — anhedonia / clinical signal


class AnamnesisInput(BaseModel):
    # Dog profile
    dog_name: str = Field(..., description="Dog's name")
    dog_age: str = Field(..., description="Age (e.g. '3 years', '8 months')")
    dog_sex: Optional[str] = Field(None, description="Dog sex: 'male' | 'female' | null if not provided")
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
    # walks_per_day es ahora la fuente de verdad — null = no aportado, 0 = ninguno,
    # 1/2 = exacto, 3 = "3 o más". `daily_walks` se mantiene por backward compat
    # pero se ignora si walks_per_day está presente; ambos se renderizan distinto
    # a "no aportado" en build_anamnesis_block.
    daily_walks: Optional[bool] = Field(None, description="DEPRECATED. Has daily walks? (null = no aportado)")
    walks_per_day: Optional[int] = Field(None, ge=0, le=3, description="Walks per day: 0, 1, 2, or 3 (3 = '3 or more'). null = no aportado.")

    # Historial y refuerzos
    other_behavior_problems: Optional[str] = Field(
        None,
        description="Other behavior problems (free text). Empty/null = no aportado.",
        max_length=2000,
    )
    attended_training_school: Optional[bool] = Field(
        None,
        description="Has the dog attended a dog training school? null = no aportado.",
    )
    training_school_result: Optional[str] = Field(
        None,
        description="Result/outcome of the training school (only meaningful if attended_training_school=True).",
        max_length=2000,
    )
    favorite_reward: Optional[FavoriteReward] = Field(
        None,
        description="Dog's favorite reinforcer: food / ball / petting / none. null = no aportado.",
    )

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

    # Pre-existing extra context field used by frontend
    prior_event: Optional[str] = Field(None, description="Major event/change before the problem started.")

    # Adoption context (frontend feedback #1): time the dog has lived with the current tutor,
    # distinct from age. An adopted 5-year-old may show the problem since arrival (months),
    # not for years — critical for accurate ABC history. Empty/null = not adopted / not provided.
    adopted_time_with_tutor: Optional[str] = Field(
        None,
        description="If adopted: how long the dog has lived with the current tutor (free text). Empty = not adopted / not provided.",
        max_length=200,
    )

    # UI language — controls the language of the AI analysis output
    lang: Optional[str] = Field("es", description="Response language: 'es' (Spanish) or 'en' (English)")
    # Postura de análisis. Solo operativa en la versión ITALIANA profesional con el
    # flag IT_COGNITIVE encendido; en cualquier otro caso se ignora y manda el motor ABA.
    # 'behavioral' (defecto) = salida ABA. 'cognitive' = pasada 2 cognitivo-zooantropológica.
    stance: Optional[str] = Field("behavioral", description="Analysis stance: 'behavioral' or 'cognitive'")


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

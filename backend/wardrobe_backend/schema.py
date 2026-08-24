from typing import Any
from pydantic import BaseModel, Field
ATTRIBUTES = ("category", "type", "color", "pattern", "fabric", "fit", "style", "occasion", "season")
class Confidence(BaseModel):
    category: float | None = None; type: float | None = None; color: float | None = None; pattern: float | None = None; fabric: float | None = None; fit: float | None = None; style: float | None = None; occasion: float | None = None; season: float | None = None
class ClothingAnalysis(BaseModel):
    imageId: str; modelId: str = "qwen3-vl-2b"; modelVersion: str = "Denali-AI/qwen3-vl-2b-sft-grpo-v9"; category: str | None = None; type: str | None = None; color: str | None = None; secondaryColors: list[str] = Field(default_factory=list); pattern: str | None = None; fabric: str | None = None; fit: str | None = None; style: list[str] = Field(default_factory=list); occasion: list[str] = Field(default_factory=list); season: list[str] = Field(default_factory=list); confidence: Confidence = Field(default_factory=Confidence); rawResponse: str = ""; inferenceTimeMs: int = 0; parseSuccess: bool = True
class GroundTruth(BaseModel):
    imageId: str; category: str | None = None; type: str | None = None; color: str | None = None; pattern: str | None = None; fabric: str | None = None; fit: str | None = None; style: list[str] = Field(default_factory=list); occasion: list[str] = Field(default_factory=list); season: list[str] = Field(default_factory=list)
class Correction(BaseModel):
    attribute: str; originalAIValue: Any; correctedValue: Any

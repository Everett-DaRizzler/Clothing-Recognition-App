from typing import Any, Literal
from pydantic import BaseModel, Field

OccasionValue = Literal["Everyday", "School", "Date", "Casual", "Formal", "Work", "Party"]
StyleValue = Literal["Casual", "Smart Casual", "Formal", "Streetwear", "Sporty", "Classic", "Minimal", "Preppy"]
SeasonValue = Literal["Spring", "Summer", "Fall", "Winter"]
ATTRIBUTES = ("category", "type", "color", "secondaryColors", "pattern", "fabric", "fit", "style", "occasion", "season")
LIST_ATTRIBUTES = ("secondaryColors", "style", "occasion", "season")
class Confidence(BaseModel):
    category: float | None = None; type: float | None = None; color: float | None = None; secondaryColors: float | None = None; pattern: float | None = None; fabric: float | None = None; fit: float | None = None; style: float | None = None; occasion: float | None = None; season: float | None = None
class ClothingAnalysis(BaseModel):
    imageId: str; modelId: str = "stylewell-4b"; modelVersion: str = "HelloWorld0204/Classification-StyleWell-model"; category: str | None = None; type: str | None = None; color: str | None = None; secondaryColors: list[str] = Field(default_factory=list); pattern: str | None = None; fabric: str | None = None; fit: str | None = None; style: list[str] = Field(default_factory=list); occasion: list[str] = Field(default_factory=list); season: list[str] = Field(default_factory=list); confidence: Confidence = Field(default_factory=Confidence); rawResponse: str = ""; inferenceTimeMs: int = 0; parseSuccess: bool = True; qualityWarnings: list[str] = Field(default_factory=list)
class GroundTruth(BaseModel):
    imageId: str; category: str | None = None; type: str | None = None; color: str | None = None; pattern: str | None = None; fabric: str | None = None; fit: str | None = None; style: list[str] = Field(default_factory=list); occasion: list[str] = Field(default_factory=list); season: list[str] = Field(default_factory=list)
class Correction(BaseModel):
    attribute: str; originalAIValue: Any; correctedValue: Any

class WardrobeItemCreate(BaseModel):
    imageId: str
    name: str | None = None
    brand: str | None = None
    category: str | None = None
    type: str | None = None
    color: str | None = None
    secondaryColors: list[str] = Field(default_factory=list)
    pattern: str | None = None
    fabric: str | None = None
    fit: str | None = None
    style: list[str] = Field(default_factory=list)
    occasion: list[str] = Field(default_factory=list)
    season: list[str] = Field(default_factory=list)
    confidence: Confidence = Field(default_factory=Confidence)
    modelId: str = "stylewell-4b"
    modelVersion: str = "HelloWorld0204/Classification-StyleWell-model"
    rawResponse: str = ""
    inferenceTimeMs: int = 0
    parseSuccess: bool = True

class WardrobeItemUpdate(BaseModel):
    name: str | None = None
    brand: str | None = None
    category: str | None = None
    type: str | None = None
    color: str | None = None
    secondaryColors: list[str] | None = None
    pattern: str | None = None
    fabric: str | None = None
    fit: str | None = None
    style: list[str] | None = None
    occasion: list[str] | None = None
    season: list[str] | None = None


class OutfitGenerationRequest(BaseModel):
    occasion: OccasionValue | None = None
    style: StyleValue | None = None
    season: SeasonValue | None = None
    anchorItemId: str | None = None
    excludeCombinationIds: list[str] = Field(default_factory=list)
    source: Literal["wardrobe", "test"] = "wardrobe"
    debug: bool = False


class OutfitCreate(BaseModel):
    name: str | None = None
    clothingItemIds: list[str] = Field(min_length=1)
    occasion: OccasionValue | None = None
    style: StyleValue | None = None
    season: SeasonValue | None = None
    generationMethod: str = "deterministic"
    generationMetadata: dict[str, Any] = Field(default_factory=dict)
    userRating: int | None = Field(default=None, ge=1, le=5)


class OutfitUpdate(BaseModel):
    name: str | None = None
    clothingItemIds: list[str] | None = Field(default=None, min_length=1)
    occasion: OccasionValue | None = None
    style: StyleValue | None = None
    season: SeasonValue | None = None
    userRating: int | None = Field(default=None, ge=1, le=5)


class OutfitReplacement(BaseModel):
    role: Literal["top", "bottom", "shoes", "outerwear", "accessory"]
    clothingItemId: str


class OutfitRating(BaseModel):
    userRating: int | None = Field(default=None, ge=1, le=5)

class PreferenceUpdate(BaseModel):
    preferredStyles: list[StyleValue] = Field(default_factory=list)
    dislikedStyles: list[StyleValue] = Field(default_factory=list)
    preferredColors: list[str] = Field(default_factory=list)
    dislikedColors: list[str] = Field(default_factory=list)
    preferredFits: list[str] = Field(default_factory=list)
    preferredOccasions: list[OccasionValue] = Field(default_factory=list)
    notes: str | None = None

class FavoriteUpdate(BaseModel):
    isFavorite: bool

class OutfitFeedback(BaseModel):
    action: Literal["like", "dislike"]
    reason: Literal["colors", "style", "one clothing item", "too formal", "too casual", "just don't like it"] | None = None
    generationId: str | None = None
    outfitId: str | None = None
    clothingItemIds: list[str] = Field(default_factory=list)
    occasion: OccasionValue | None = None
    style: StyleValue | None = None
    season: SeasonValue | None = None

class WornOutfit(BaseModel):
    outfitId: str

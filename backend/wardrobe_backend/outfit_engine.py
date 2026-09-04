"""Deterministic, explainable outfit selection over structured wardrobe data."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
import re
from typing import Any, Iterable


ROLES = ("top", "bottom", "shoes", "outerwear", "accessory")
REQUIRED_ROLES = ("top", "bottom", "shoes")
OCCASIONS = ("Everyday", "School", "Date", "Casual", "Formal", "Work", "Party")
STYLES = ("Casual", "Smart Casual", "Formal", "Streetwear", "Sporty", "Classic", "Minimal", "Preppy")
SEASONS = ("Spring", "Summer", "Fall", "Winter")

WEIGHTS = {
    "color": 10,
    "style": 10,
    "occasion": 8,
    "season": 8,
    "pattern": 8,
    "completeness": 6,
}

NEUTRALS = {"black", "white", "gray", "grey", "navy", "brown", "beige", "khaki", "cream", "tan"}
COLOR_ALIASES = {"grey": "gray", "ivory": "cream", "off-white": "white", "off white": "white", "denim": "blue"}
COMPLEMENTARY = {
    frozenset(("red", "green")), frozenset(("blue", "orange")), frozenset(("yellow", "purple")),
    frozenset(("navy", "orange")), frozenset(("pink", "green")),
}
SIMILAR = (
    {"blue", "navy", "purple"}, {"red", "pink", "orange"}, {"green", "yellow"},
    {"brown", "tan", "beige", "cream"}, {"black", "gray", "white"},
)
STYLE_FAMILIES = {
    "casual": {"casual", "smart casual", "classic", "preppy", "minimal"},
    "smart casual": {"casual", "smart casual", "classic", "preppy", "minimal"},
    "formal": {"formal", "classic", "smart casual"},
    "streetwear": {"streetwear", "casual", "sporty", "minimal"},
    "sporty": {"sporty", "casual", "streetwear"},
    "classic": {"classic", "casual", "smart casual", "formal", "preppy", "minimal"},
    "minimal": {"minimal", "casual", "smart casual", "streetwear", "classic"},
    "preppy": {"preppy", "classic", "smart casual", "casual"},
}
OCCASION_FAMILIES = {
    "everyday": {"everyday", "casual", "school", "travel", "outdoor"},
    "school": {"school", "everyday", "casual", "preppy"},
    "date": {"date", "casual", "formal", "work", "party", "smart casual"},
    "casual": {"casual", "everyday", "school", "travel", "outdoor", "date"},
    "formal": {"formal", "work", "date", "party"},
    "work": {"work", "formal", "smart casual", "classic"},
    "party": {"party", "date", "formal", "casual"},
}
SEASON_FAMILIES = {
    "spring": {"spring", "fall", "all season"}, "summer": {"summer", "spring", "all season"},
    "fall": {"fall", "spring", "winter", "all season"}, "winter": {"winter", "fall", "all season"},
}


def _norm(value: Any) -> str:
    return COLOR_ALIASES.get(str(value or "").strip().lower(), str(value or "").strip().lower())


def _values(item: dict[str, Any], key: str) -> list[str]:
    value = item.get(key, [])
    return [str(part) for part in (value if isinstance(value, list) else [value]) if str(part).strip()]


def role_for_item(item: dict[str, Any]) -> str | None:
    text = " ".join(str(item.get(key) or "") for key in ("category", "type", "name")).lower()
    if any(word in text for word in ("shoe", "sneaker", "boot", "loafer", "sandal", "heel", "slipper")):
        return "shoes"
    if any(word in text for word in ("outerwear", "jacket", "coat", "parka", "blazer", "cardigan", "vest")):
        return "outerwear"
    if any(word in text for word in ("accessor", "belt", "hat", "scarf", "bag", "watch", "tie")):
        return "accessory"
    if any(word in text for word in ("bottom", "pant", "jean", "short", "skirt", "trouser", "chino")):
        return "bottom"
    if any(word in text for word in ("top", "shirt", "tee", "t-shirt", "polo", "blouse", "sweater", "hoodie", "tank")):
        return "top"
    return None


def color_compatibility(left: Any, right: Any) -> float:
    a, b = _norm(left), _norm(right)
    if not a or not b:
        return 6.0
    if a == b:
        return 7.0 if a not in NEUTRALS else 8.0
    if a in NEUTRALS and b in NEUTRALS:
        return 8.0
    if a in NEUTRALS or b in NEUTRALS:
        return 9.0
    if frozenset((a, b)) in COMPLEMENTARY:
        return 8.0
    if any(a in family and b in family for family in SIMILAR):
        return 8.0
    return 5.0


def pattern_compatibility(left: Any, right: Any) -> float:
    a, b = _norm(left), _norm(right)
    if not a or not b:
        return 6.0
    solid = {"solid", "plain", "none"}
    loud = {"graphic", "floral", "printed", "animal", "paisley"}
    if a in solid and b in solid:
        return 9.0
    if a in solid or b in solid:
        return 8.0
    if a == b:
        return 5.0 if a in loud else 7.0
    if a in loud and b in loud:
        return 3.0
    return 6.0


def _set_score(values_left: Iterable[str], values_right: Iterable[str], families: dict[str, set[str]]) -> float:
    left = {_norm(value) for value in values_left}
    right = {_norm(value) for value in values_right}
    if not left or not right:
        return 6.0
    if left & right:
        return 10.0
    if any(families.get(value, {value}) & right for value in left) or any(families.get(value, {value}) & left for value in right):
        return 8.0
    return 3.0


def style_compatibility(left: Iterable[str], right: Iterable[str]) -> float:
    return _set_score(left, right, STYLE_FAMILIES)


def occasion_compatibility(left: Iterable[str], right: Iterable[str]) -> float:
    return _set_score(left, right, OCCASION_FAMILIES)


def season_compatibility(left: Iterable[str], right: Iterable[str]) -> float:
    return _set_score(left, right, SEASON_FAMILIES)


def _pair_score(left: dict[str, Any], right: dict[str, Any]) -> dict[str, float]:
    return {
        "color": color_compatibility(left.get("color"), right.get("color")),
        "style": style_compatibility(_values(left, "style"), _values(right, "style")),
        "occasion": occasion_compatibility(_values(left, "occasion"), _values(right, "occasion")),
        "season": season_compatibility(_values(left, "season"), _values(right, "season")),
        "pattern": pattern_compatibility(left.get("pattern"), right.get("pattern")),
    }


def score_combination(items: list[dict[str, Any]], requested: dict[str, str | None]) -> dict[str, Any]:
    if len(items) < 2:
        component_scores = {key: 0.0 for key in WEIGHTS if key != "completeness"}
    else:
        pairs = [_pair_score(left, right) for index, left in enumerate(items) for right in items[index + 1:]]
        component_scores = {key: round(sum(pair[key] for pair in pairs) / len(pairs), 2) for key in ("color", "style", "occasion", "season", "pattern")}
    roles = {role_for_item(item) for item in items}
    completeness = sum(role in roles for role in REQUIRED_ROLES) / len(REQUIRED_ROLES) * 10
    component_scores["completeness"] = round(completeness, 2)
    filter_bonus = 0.0
    reasons: list[str] = []
    for key, scorer in (("occasion", occasion_compatibility), ("style", style_compatibility), ("season", season_compatibility)):
        requested_value = requested.get(key)
        if requested_value:
            values = [_values(item, key) for item in items]
            matching = sum(scorer([requested_value], item_values) >= 8 for item_values in values)
            filter_bonus += matching / max(1, len(values)) * 3
            if matching == 0:
                reasons.append(f"{key.title()} mismatch")
    weighted = sum(component_scores[key] * WEIGHTS[key] for key in component_scores) / sum(WEIGHTS.values())
    total = round(min(100.0, weighted + filter_bonus), 2)
    if component_scores["completeness"] < 10:
        reasons.append("Missing one or more core clothing roles")
    if component_scores["pattern"] < 5:
        reasons.append("Multiple loud patterns")
    return {"total": total, "components": component_scores, "reasons": reasons}


def combination_id(items: Iterable[dict[str, Any]]) -> str:
    return "|".join(sorted(str(item["id"]) for item in items))


def explanation(items: list[dict[str, Any]], requested: dict[str, str | None], source: str = "wardrobe") -> str:
    if not items:
        return "Add a few wardrobe items and I can build an outfit from what you own."
    names = [str(item.get("name") or item.get("type") or "item") for item in items]
    colors = [str(item.get("color")) for item in items if item.get("color")]
    color_text = " and ".join(colors[:2]) if len(colors) >= 2 else (colors[0] if colors else "the selected colors")
    style_text = requested.get("style") or next((value for item in items for value in _values(item, "style")), "a coordinated style")
    source_text = "the fictional test wardrobe" if source == "test" else "your wardrobe"
    return f"{names[0]} works with {', '.join(names[1:]) or 'the rest of the outfit'} because the {color_text} palette supports a {style_text.lower()} look. The combination uses only items from {source_text}."


def _missing_roles(items: list[dict[str, Any]]) -> list[str]:
    roles = {role_for_item(item) for item in items}
    return [role for role in REQUIRED_ROLES if role not in roles]


def _candidate_rejections(items: list[dict[str, Any]], selected: list[dict[str, Any]], requested: dict[str, str | None]) -> list[dict[str, Any]]:
    selected_ids = {item["id"] for item in selected}
    selected_roles = {role_for_item(item) for item in selected}
    rejected = []
    for item in items:
        if item["id"] in selected_ids:
            continue
        role = role_for_item(item)
        reasons = []
        if role in selected_roles and role in REQUIRED_ROLES:
            reasons.append("Role already filled by a higher-scoring item")
        for key, scorer in (("occasion", occasion_compatibility), ("style", style_compatibility), ("season", season_compatibility)):
            value = requested.get(key)
            if value and _values(item, key) and scorer([value], _values(item, key)) < 5:
                reasons.append(f"{key.title()} mismatch")
        if reasons:
            rejected.append({"clothingItemId": item["id"], "name": item.get("name"), "role": role, "reasons": reasons})
    return rejected


def generate_outfit(items: list[dict[str, Any]], occasion: str | None = None, style: str | None = None, season: str | None = None, anchor_item_id: str | None = None, excluded: Iterable[str] = (), source: str = "wardrobe", include_all_candidates: bool = False) -> dict[str, Any]:
    requested = {"occasion": occasion, "style": style, "season": season}
    available = [item for item in items if role_for_item(item)]
    anchor_present = bool(anchor_item_id and any(item["id"] == anchor_item_id for item in available))
    if anchor_present:
        anchor = next((item for item in available if item["id"] == anchor_item_id), None)
        if anchor:
            available = [anchor] + [item for item in available if item["id"] != anchor_item_id]
    by_role = {role: [item for item in available if role_for_item(item) == role] for role in ROLES}
    if not available:
        return {"available": False, "items": [], "missingRoles": list(REQUIRED_ROLES), "message": "You need a few more clothing items before I can build an outfit.", "explanation": explanation([], requested, source), "candidates": [], "rejected": []}
    anchors = [next((item for item in available if item["id"] == anchor_item_id), None)] if anchor_item_id else [None]
    if anchors == [None]:
        anchors = [None]
    combinations = []
    top_choices = by_role["top"] or [None]
    bottom_choices = by_role["bottom"] or [None]
    shoes_choices = by_role["shoes"] or [None]
    outer_choices = by_role["outerwear"] + [None]
    accessory_choices = by_role["accessory"] + [None]
    for sequence, (top, bottom, shoes, outer, accessory) in enumerate(product(top_choices, bottom_choices, shoes_choices, outer_choices, accessory_choices)):
        picked = [item for item in (top, bottom, shoes, outer, accessory) if item]
        ids = {item["id"] for item in picked}
        if len(ids) != len(picked) or (anchor_present and anchor_item_id not in ids):
            continue
        scored = score_combination(picked, requested)
        combinations.append({"items": picked, "score": scored, "combinationId": combination_id(picked), "sequence": sequence})
    if not combinations:
        picked = available[:3]
        combinations = [{"items": picked, "score": score_combination(picked, requested), "combinationId": combination_id(picked), "sequence": 0}]
    excluded_set = set(excluded)
    ranked = sorted(combinations, key=lambda candidate: (-candidate["score"]["total"], candidate["sequence"]))
    chosen = next((candidate for candidate in ranked if candidate["combinationId"] not in excluded_set), ranked[0])
    chosen_items = chosen["items"]
    missing = _missing_roles(chosen_items)
    return {
        "available": True,
        "items": chosen_items,
        "clothingItemIds": [item["id"] for item in chosen_items],
        "combinationId": chosen["combinationId"],
        "missingRoles": missing,
        "isComplete": not missing,
        "message": "" if not missing else "This is the best available combination. Add the missing roles to complete the outfit.",
        "explanation": explanation(chosen_items, requested, source),
        "score": chosen["score"],
        "candidates": [{"combinationId": c["combinationId"], "clothingItemIds": [i["id"] for i in c["items"]], "score": c["score"]} for c in (ranked if include_all_candidates else ranked[:8])],
        "rejected": _candidate_rejections(available, chosen_items, requested),
    }


@dataclass(frozen=True)
class Fixture:
    id: str
    name: str
    category: str
    type: str
    color: str
    pattern: str
    style: list[str]
    occasion: list[str]
    season: list[str]

    def as_item(self) -> dict[str, Any]:
        return {"id": self.id, "imageId": "", "name": self.name, "category": self.category, "type": self.type, "color": self.color, "secondaryColors": [], "pattern": self.pattern, "fabric": "", "fit": "Regular", "style": self.style, "occasion": self.occasion, "season": self.season, "aiConfidence": {}, "aiPrediction": {}}


def test_wardrobe() -> list[dict[str, Any]]:
    fixtures = [
        Fixture("test-navy-polo", "Navy Polo", "Top", "Polo", "Navy", "Solid", ["Casual", "Preppy"], ["Everyday", "School", "Casual"], ["Spring", "Summer", "Fall"]),
        Fixture("test-white-tee", "White Tee", "Top", "Tee", "White", "Solid", ["Casual", "Minimal"], ["Everyday", "School", "Casual"], ["Spring", "Summer"]),
        Fixture("test-gray-hoodie", "Gray Hoodie", "Top", "Hoodie", "Gray", "Solid", ["Streetwear", "Casual"], ["Everyday", "School"], ["Fall", "Winter"]),
        Fixture("test-khaki-chinos", "Khaki Chinos", "Bottom", "Chinos", "Khaki", "Solid", ["Smart Casual", "Preppy"], ["Everyday", "Work", "Date"], ["Spring", "Summer", "Fall"]),
        Fixture("test-black-jeans", "Black Jeans", "Bottom", "Jeans", "Black", "Solid", ["Casual", "Streetwear"], ["Everyday", "School", "Date"], ["Fall", "Winter", "Spring"]),
        Fixture("test-athletic-shorts", "Athletic Shorts", "Bottom", "Shorts", "Red", "Solid", ["Sporty"], ["Workout", "Outdoor"], ["Summer"]),
        Fixture("test-white-sneakers", "White Sneakers", "Shoes", "Sneakers", "White", "Solid", ["Casual", "Sporty"], ["Everyday", "School", "Casual"], ["Spring", "Summer", "Fall"]),
        Fixture("test-brown-loafers", "Brown Loafers", "Shoes", "Loafers", "Brown", "Solid", ["Classic", "Smart Casual", "Formal"], ["Work", "Date", "Formal"], ["Spring", "Summer", "Fall"]),
        Fixture("test-denim-jacket", "Denim Jacket", "Outerwear", "Jacket", "Blue", "Solid", ["Casual", "Streetwear"], ["Everyday", "School", "Casual"], ["Spring", "Fall"]),
        Fixture("test-brown-belt", "Brown Belt", "Accessories", "Belt", "Brown", "Solid", ["Classic", "Smart Casual"], ["Work", "Date", "Formal"], ["Spring", "Summer", "Fall", "Winter"]),
    ]
    return [fixture.as_item() for fixture in fixtures]

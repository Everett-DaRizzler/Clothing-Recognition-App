"""Small, transparent preference adjustments layered on top of outfit quality."""

from __future__ import annotations

from typing import Any


def _values(item: dict[str, Any], key: str) -> set[str]:
    value = item.get(key, [])
    values = value if isinstance(value, list) else [value]
    return {str(part).strip().lower() for part in values if str(part).strip()}


def _clamp(value: float, low: float, high: float) -> float:
    return round(max(low, min(high, value)), 2)


def score_personalization(base_score: dict[str, Any], items: list[dict[str, Any]], profile: dict[str, Any], recent_history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    explicit = profile.get("explicit", {})
    learned = profile.get("learned", {})
    favorites = set(profile.get("favoriteItemIds", []))
    recent_history = recent_history or []
    styles = {style for item in items for style in _values(item, "style")}
    colors = {color for item in items for color in _values(item, "color")}
    preferred_styles = {str(v).lower() for v in explicit.get("preferredStyles", [])}
    disliked_styles = {str(v).lower() for v in explicit.get("dislikedStyles", [])}
    preferred_colors = {str(v).lower() for v in explicit.get("preferredColors", [])}
    disliked_colors = {str(v).lower() for v in explicit.get("dislikedColors", [])}
    bonus = 0.0
    components: dict[str, float] = {"explicitStyles": 0.0, "explicitDetails": 0.0, "learnedStyles": 0.0, "favoriteItems": 0.0, "itemSignals": 0.0, "variety": 0.0}
    reasons: list[str] = []

    if styles & preferred_styles:
        components["explicitStyles"] += 4
        reasons.append(f"User likes {next(iter(styles & preferred_styles)).title()} style")
    if styles & disliked_styles:
        components["explicitStyles"] -= 5
        reasons.append(f"User usually avoids {next(iter(styles & disliked_styles)).title()} style")
    if colors & preferred_colors:
        components["explicitStyles"] += 1
        reasons.append(f"Preferred {next(iter(colors & preferred_colors)).title()} color included")
    if colors & disliked_colors:
        components["explicitStyles"] -= 2
        reasons.append(f"Disliked {next(iter(colors & disliked_colors)).title()} color included")
    preferred_fits = {str(v).lower() for v in explicit.get("preferredFits", [])}
    preferred_occasions = {str(v).lower() for v in explicit.get("preferredOccasions", [])}
    if preferred_fits and any(str(item.get("fit") or "").lower() in preferred_fits for item in items):
        components["explicitDetails"] += 1.5
        reasons.append("Preferred fit included")
    if preferred_occasions and any(_values(item, "occasion") & preferred_occasions for item in items):
        components["explicitDetails"] += 1.5
        reasons.append("Preferred occasion included")

    for style in styles:
        signal = learned.get("styles", {}).get(style, 0)
        components["learnedStyles"] += _clamp(float(signal), -3, 3)
        if signal >= 2:
            reasons.append(f"User has liked similar {style.title()} looks")
        elif signal <= -2:
            reasons.append(f"User frequently dislikes {style.title()} looks")

    for item in items:
        item_id = str(item.get("id"))
        if item_id in favorites:
            components["favoriteItems"] += 1.5
            reasons.append(f"Favorite item included: {item.get('name') or item_id}")
        signal = float(learned.get("items", {}).get(item_id, 0))
        components["itemSignals"] += _clamp(signal, -2, 2)

    ids = {str(item.get("id")) for item in items}
    for history in recent_history:
        previous = set(history.get("clothingItemIds", []))
        overlap = len(ids & previous)
        if overlap == len(ids) and ids:
            components["variety"] -= 4
            reasons.append("A recent recommendation used this exact combination")
            break
        if overlap >= 2:
            components["variety"] -= 1
    components["variety"] = _clamp(components["variety"], -4, 0)
    total_delta = _clamp(sum(components.values()), -10, 10)
    base_total = float(base_score.get("total", 0))
    return {
        "baseTotal": round(base_total, 2),
        "personalizationBonus": total_delta,
        "total": round(max(0, min(100, base_total + total_delta)), 2),
        "components": {key: round(value, 2) for key, value in components.items()},
        "reasons": reasons,
    }

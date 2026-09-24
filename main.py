"""Minimal API for the Perfect Saturday Planner."""

from __future__ import annotations

import json
import math
import re
from urllib.parse import quote
from urllib.request import Request, urlopen
from typing import Any, Dict, List, Union

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


app = FastAPI(title="Perfect Saturday Planner API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PlanRequest(BaseModel):
    city: str = Field(min_length=1)
    budget: Union[float, str] = 0
    available_time: Union[str, float, int] = "full day"
    mood: str = "relaxed"
    interests: Union[List[str], str] = Field(default_factory=list)
    constraints: Union[List[str], str, None] = None


CITY_DATA: Dict[str, Dict[str, Any]] = {
    "bangalore": {
        "display_name": "Bangalore",
        "activities": [
            {"name": "Lalbagh Botanical Garden", "type": "nature", "hours": 2, "cost": 0},
            {"name": "Cubbon Park and Vidhana Soudha walk", "type": "culture", "hours": 2, "cost": 0},
            {"name": "Indiranagar café and bookstore hop", "type": "food", "hours": 3, "cost": 500},
            {"name": "Nandi Hills sunrise drive", "type": "adventure", "hours": 4, "cost": 700},
            {"name": "VR Bengaluru cinema and shopping", "type": "entertainment", "hours": 3, "cost": 900},
        ],
        "food": [
            {"name": "South Indian breakfast at MTR", "cost": 300, "vegetarian": True},
            {"name": "Local thali lunch", "cost": 450, "vegetarian": True},
            {"name": "Craft coffee and dessert", "cost": 400, "vegetarian": True},
        ],
    },
    "mumbai": {
        "display_name": "Mumbai",
        "activities": [
            {"name": "Marine Drive sunset walk", "type": "nature", "hours": 2, "cost": 0},
            {"name": "Kala Ghoda galleries", "type": "culture", "hours": 3, "cost": 300},
            {"name": "Bandra street-food and café trail", "type": "food", "hours": 3, "cost": 600},
        ],
        "food": [{"name": "Local thali lunch", "cost": 450, "vegetarian": True}, {"name": "Street-food tasting", "cost": 350, "vegetarian": False}],
    },
    "delhi": {
        "display_name": "Delhi",
        "activities": [
            {"name": "Lodhi Garden picnic", "type": "nature", "hours": 2, "cost": 200},
            {"name": "Humayun's Tomb and Sunder Nursery", "type": "culture", "hours": 3, "cost": 500},
            {"name": "Hauz Khas café and art walk", "type": "food", "hours": 3, "cost": 600},
        ],
        "food": [{"name": "Old Delhi food walk", "cost": 500, "vegetarian": False}, {"name": "North Indian thali", "cost": 400, "vegetarian": True}],
    },
}


def parse_preferences(request: PlanRequest) -> Dict[str, Any]:
    """Normalize user input into predictable values for later stages."""
    interests = request.interests if isinstance(request.interests, list) else [request.interests]
    constraints = request.constraints or []
    if isinstance(constraints, str):
        constraints = re.split(r"[,;\n]+", constraints)
    try:
        budget = float(request.budget)
    except (TypeError, ValueError):
        budget = 0
    if not math.isfinite(budget):
        budget = 0
    return {
        "city": " ".join(request.city.split()),
        "budget": max(0, budget),
        "available_hours": _hours_from_value(request.available_time),
        "time_window": str(request.available_time).lower(),
        "mood": request.mood.strip().lower(),
        "interests": [item.strip().lower() for item in interests if isinstance(item, str) and item.strip()],
        "constraints": [item.strip().lower() for item in constraints if isinstance(item, str) and item.strip()],
    }


def _hours_from_value(value: Union[str, float, int]) -> float:
    if isinstance(value, (int, float)):
        return max(1, float(value))
    text = str(value).lower().strip()
    if "half" in text:
        return 4
    if "hour" in text:
        try:
            number = re.search(r"\d+(?:\.\d+)?", text)
            return max(1, float(number.group()) if number else 4)
        except ValueError:
            pass
    return 8 if "full" in text or "day" in text else 4


INTEREST_ALIASES = {
    "good coffee": {"food"},
    "local food": {"food"},
    "art & culture": {"culture", "historic"},
    "nature": {"nature"},
    "shopping": {"entertainment"},
    "live music": {"entertainment"},
}


def _requested_types(preferences: Dict[str, Any]) -> set[str]:
    requested = set()
    for interest in preferences["interests"]:
        requested.update(INTEREST_ALIASES.get(interest, {interest}))
    text = " ".join(preferences["interests"] + preferences["constraints"])
    if any(term in text for term in ("monument", "historic", "heritage", "museum", "attraction")):
        requested.update({"culture", "historic"})
    return requested


def activity_options(preferences: Dict[str, Any], city: Dict[str, Any]) -> List[Dict[str, Any]]:
    options = city["activities"]
    matching = [item for item in options if item["type"] in _requested_types(preferences)]
    return matching or options


def get_real_place_options(city_name: str, preferences: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch a small, free OSM/Overpass sample; callers must keep a mock fallback."""
    headers = {"User-Agent": "perfect-saturday-planner-demo/1.0 (educational project)"}
    try:
        location_url = (
            "https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&q="
            + quote(city_name)
        )
        with urlopen(Request(location_url, headers=headers), timeout=4) as response:
            locations = json.loads(response.read().decode("utf-8"))
        if not locations:
            return {"activities": [], "food": [], "source": "osm", "status": "no_match"}

        lat, lon = locations[0]["lat"], locations[0]["lon"]
        query = f"""
[out:json][timeout:8];
(
  nwr(around:5000,{lat},{lon})[leisure=park];
  nwr(around:5000,{lat},{lon})[tourism=attraction];
  nwr(around:5000,{lat},{lon})[historic=monument];
  nwr(around:5000,{lat},{lon})[amenity~"cafe|restaurant"];
);
out center tags 12;
"""
        overpass_url = "https://overpass-api.de/api/interpreter"
        overpass_request = Request(
            overpass_url,
            data=("data=" + quote(query)).encode("utf-8"),
            headers={**headers, "Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urlopen(overpass_request, timeout=10) as response:
            elements = json.loads(response.read().decode("utf-8")).get("elements", [])

        activities: List[Dict[str, Any]] = []
        food: List[Dict[str, Any]] = []
        for element in elements:
            tags = element.get("tags", {})
            name = tags.get("name")
            if not name:
                continue
            if tags.get("amenity") in {"cafe", "restaurant"}:
                food.append({"name": name, "cost": 450, "vegetarian": "vegetarian" in " ".join(str(value) for value in tags.values()).lower()})
            else:
                activity_type = "nature" if tags.get("leisure") == "park" else "culture"
                if tags.get("historic") == "monument":
                    activity_type = "historic"
                activities.append({"name": name, "type": activity_type, "hours": 2, "cost": 0, "real": True})
        return {
            "activities": activities[:8],
            "food": food[:8],
            "source": "openstreetmap",
            "status": "live" if activities or food else "no_match",
        }
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return {"activities": [], "food": [], "source": "openstreetmap", "status": "unavailable"}


def food_options(preferences: Dict[str, Any], city: Dict[str, Any]) -> List[Dict[str, Any]]:
    options = city["food"]
    if any("vegetarian" in constraint or "veg" == constraint for constraint in preferences["constraints"]):
        vegetarian = [item for item in options if item.get("vegetarian")]
        if vegetarian:
            return vegetarian
    return options


def estimate_cost(activity: Dict[str, Any], food: Dict[str, Any]) -> float:
    return float(activity["cost"] + food["cost"] + 150)  # local transport buffer


def validate_plan(plan: Dict[str, Any], preferences: Dict[str, Any]) -> Dict[str, Any]:
    warnings: List[str] = []
    if plan["estimated_cost"] > preferences["budget"] > 0:
        warnings.append("The suggested plan is above budget; consider the free activity option.")
    if plan["duration_hours"] > preferences["available_hours"]:
        warnings.append("The plan was shortened to fit the available time.")
    return {"valid": not warnings, "warnings": warnings}


def generate_final(
    preferences: Dict[str, Any], activity: Dict[str, Any], food: Dict[str, Any], cost: float,
    source: str = "mock",
) -> Dict[str, Any]:
    duration = min(activity["hours"] + 1.5, preferences["available_hours"])
    evening = "evening" in preferences["time_window"] or "night" in preferences["time_window"]
    first_time, second_time = ("17:00", "19:30") if evening else ("10:00", "13:00")
    return {
        "city": preferences["city"],
        "title": f"A {preferences['mood'].title()} Saturday in {preferences['city'].title()}",
        "intro": "A low-stress route with one grounding activity and a satisfying meal, leaving room to wander.",
        "schedule": [
            {"time": first_time, "activity": activity["name"], "type": activity["type"], "duration_hours": activity["hours"], "description": f"{activity['hours']} hours of {activity['type']} time, chosen to suit a {preferences['mood']} mood.", "cost": activity["cost"]},
            {"time": second_time, "activity": food["name"], "type": "food", "duration_hours": 1.5, "description": "A practical, constraint-aware meal break close to the route.", "cost": food["cost"]},
        ],
        "estimated_cost": round(cost),
        "duration_hours": round(duration, 1),
        "rationale": f"The plan pairs your {', '.join(preferences['interests']) or 'easygoing'} interests with a {preferences['available_hours']}-hour pace and keeps the route simple.",
        "source": source,
        "tradeoffs": [
            "The route favors a short, low-friction pair of stops over packing in too many activities."
        ],
        "tips": ["Carry water and check venue timings before leaving.", "Use public transport where convenient."],
    }


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/health")
def api_health() -> Dict[str, str]:
    return health()


@app.post("/api/plan")
def create_plan(request: PlanRequest) -> Dict[str, Any]:
    preferences = parse_preferences(request)
    requested_city = preferences["city"].lower()
    city = CITY_DATA.get(requested_city)
    fallback = city is None
    if city is None:
        city = CITY_DATA["bangalore"]
        preferences["city"] = city["display_name"]

    real_options = get_real_place_options(preferences["city"], preferences)
    live_activities = real_options["activities"]
    live_food = real_options["food"]
    requested_types = _requested_types(preferences)
    matching_live = [
        item for item in live_activities
        if not requested_types or item["type"] in requested_types
    ]
    activities = matching_live or live_activities or activity_options(preferences, city)
    activity = activities[0]
    food = (live_food or food_options(preferences, city))[0]
    cost = estimate_cost(activity, food)
    source = real_options["source"] if real_options["status"] == "live" else "mock"
    plan = generate_final(preferences, activity, food, cost, source)
    if preferences["budget"] and cost > preferences["budget"]:
        plan["tradeoffs"].append(
            f"This option is about INR {round(cost - preferences['budget'])} over budget because it keeps the route realistic; the free activity is the easiest saving."
        )
    validation = validate_plan(plan, preferences)
    clarifying_questions = []
    if not preferences["interests"]:
        clarifying_questions.append("What would you enjoy most: food, nature, culture, music, or shopping?")
    if preferences["mood"] in {"relaxed", "slow & sunny"} and preferences["available_hours"] <= 3:
        clarifying_questions.append("Should the short plan prioritize a meal or one standout activity?")
    trace = [
        {"stage": "parse_preferences", "status": "completed"},
        {"stage": "real_place_lookup", "status": real_options["status"], "source": real_options["source"]},
        {"stage": "activity_options", "status": "completed", "count": len(activities)},
        {"stage": "food_options", "status": "completed", "count": len(city["food"])},
        {"stage": "estimate_cost", "status": "completed", "amount": round(cost)},
        {"stage": "validate_plan", "status": "completed", "valid": validation["valid"]},
        {"stage": "generate_final", "status": "completed"},
    ]
    return {
        "plan": plan,
        "trace": trace,
        "validation": validation,
        "clarifying_questions": clarifying_questions,
        "fallback": {
            "used": fallback,
            "requested_city": request.city,
            "resolved_city": city["display_name"],
            "message": "City not in the sample dataset; showing a Bangalore template."
            if fallback
            else None,
        },
    }

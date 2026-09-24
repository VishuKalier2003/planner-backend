"""Minimal API for the Perfect Saturday Planner."""

from __future__ import annotations

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
        constraints = [constraints]
    try:
        budget = float(request.budget)
    except (TypeError, ValueError):
        budget = 0
    return {
        "city": request.city.strip(),
        "budget": max(0, budget),
        "available_hours": _hours_from_value(request.available_time),
        "mood": request.mood.strip().lower(),
        "interests": [item.strip().lower() for item in interests if item.strip()],
        "constraints": [item.strip().lower() for item in constraints if item.strip()],
    }


def _hours_from_value(value: Union[str, float, int]) -> float:
    if isinstance(value, (int, float)):
        return max(1, float(value))
    text = value.lower()
    if "half" in text:
        return 4
    if "hour" in text:
        try:
            return max(1, float(text.split("hour")[0].strip()))
        except ValueError:
            pass
    return 8 if "full" in text or "day" in text else 4


def activity_options(preferences: Dict[str, Any], city: Dict[str, Any]) -> List[Dict[str, Any]]:
    options = city["activities"]
    interests = preferences["interests"]
    matching = [item for item in options if item["type"] in interests]
    return matching or options


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
    preferences: Dict[str, Any], activity: Dict[str, Any], food: Dict[str, Any], cost: float
) -> Dict[str, Any]:
    duration = min(activity["hours"] + 1.5, preferences["available_hours"])
    return {
        "city": preferences["city"],
        "title": f"A {preferences['mood'].title()} Saturday in {preferences['city'].title()}",
        "intro": "A low-stress route with one grounding activity and a satisfying meal, leaving room to wander.",
        "schedule": [
            {"time": "10:00", "activity": activity["name"], "type": activity["type"], "duration_hours": activity["hours"], "description": f"{activity['hours']} hours of {activity['type']} time, chosen to suit a {preferences['mood']} mood.", "cost": activity["cost"]},
            {"time": "13:00", "activity": food["name"], "type": "food", "duration_hours": 1.5, "description": "A practical, constraint-aware meal break close to the route.", "cost": food["cost"]},
        ],
        "estimated_cost": round(cost),
        "duration_hours": round(duration, 1),
        "rationale": f"The plan pairs your {', '.join(preferences['interests']) or 'easygoing'} interests with a {preferences['available_hours']}-hour pace and keeps the route simple.",
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

    activities = activity_options(preferences, city)
    activity = activities[0]
    food = food_options(preferences, city)[0]
    cost = estimate_cost(activity, food)
    plan = generate_final(preferences, activity, food, cost)
    validation = validate_plan(plan, preferences)
    trace = [
        {"stage": "parse_preferences", "status": "completed"},
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
        "fallback": {
            "used": fallback,
            "requested_city": request.city,
            "resolved_city": city["display_name"],
            "message": "City not in the sample dataset; showing a Bangalore template."
            if fallback
            else None,
        },
    }

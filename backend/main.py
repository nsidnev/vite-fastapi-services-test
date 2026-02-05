from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional, TypedDict
import random
import time
import uuid


app = FastAPI(title="Starline Salvage")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAP_SIZE = 5
GOAL_CREDITS = 120
MAX_FUEL = 12
MAX_HULL = 10


class ActionRequest(BaseModel):
    game_id: str
    action: str
    direction: Optional[str] = None
    target_id: Optional[str] = None
    item: Optional[str] = None


class Anomaly(TypedDict):
    id: str
    name: str
    x: int
    y: int
    value: int
    risk: int
    collected: bool


class Station(TypedDict):
    id: str
    name: str
    x: int
    y: int


class PendingEvent(TypedDict):
    type: str
    threat: int


class GameState(BaseModel):
    id: str
    seed: int
    turn: int
    x: int
    y: int
    fuel: int
    hull: int
    credits: int
    status: str
    log: List[str]
    anomalies: List[Anomaly]
    stations: List[Station]
    pending_event: Optional[PendingEvent]


games: Dict[str, GameState] = {}


def generate_anomalies(seed: int) -> List[Anomaly]:
    rng = random.Random(seed)
    anomalies = []
    names = [
        "Derelict Skiff",
        "Glitter Cache",
        "Drift Beacon",
        "Ice Vault",
        "Hollow Freighter",
        "Cracked Probe",
        "Solar Wreck",
        "Echo Relay",
        "Quiet Tomb",
        "Shard Garden",
    ]
    for _ in range(10):
        name = rng.choice(names)
        x = rng.randrange(MAP_SIZE)
        y = rng.randrange(MAP_SIZE)
        value = rng.randint(10, 40)
        risk = rng.randint(1, 4)
        anomaly_id = uuid.uuid4().hex
        anomalies.append(
            {
                "id": anomaly_id,
                "name": name,
                "x": x,
                "y": y,
                "value": value,
                "risk": risk,
                "collected": False,
            }
        )
    return anomalies


def generate_stations(seed: int) -> List[Station]:
    rng = random.Random(seed + 4242)
    names = [
        "Cinder Tradepost",
        "Nova Exchange",
        "Kepler Bazaar",
        "Drydock 19",
        "Marrow Port",
    ]
    stations: List[Station] = []
    while len(stations) < 3:
        x = rng.randrange(MAP_SIZE)
        y = rng.randrange(MAP_SIZE)
        if x == 0 and y == 0:
            continue
        if any(s["x"] == x and s["y"] == y for s in stations):
            continue
        stations.append(
            {
                "id": uuid.uuid4().hex,
                "name": rng.choice(names),
                "x": x,
                "y": y,
            }
        )
    return stations


def station_offers() -> List[Dict[str, object]]:
    return [
        {
            "id": "fuel_cell",
            "label": "Fuel Cells (+2 fuel)",
            "price": 4,
        },
        {
            "id": "hull_patch",
            "label": "Hull Patch (+1 hull)",
            "price": 6,
        },
    ]


def current_station(state: GameState) -> Optional[Station]:
    return next(
        (s for s in state.stations if s["x"] == state.x and s["y"] == state.y),
        None,
    )


def public_state(
    state: GameState, nearby: Optional[List[Dict[str, object]]] = None
) -> Dict[str, object]:
    station = current_station(state)
    return {
        "id": state.id,
        "turn": state.turn,
        "x": state.x,
        "y": state.y,
        "fuel": state.fuel,
        "hull": state.hull,
        "credits": state.credits,
        "status": state.status,
        "log": state.log[-8:],
        "mapSize": MAP_SIZE,
        "goalCredits": GOAL_CREDITS,
        "nearby": nearby or [],
        "station": {
            "id": station["id"],
            "name": station["name"],
            "offers": station_offers(),
        }
        if station
        else None,
        "pendingEvent": state.pending_event,
    }


def update_status(state: GameState) -> None:
    if state.hull <= 0:
        state.status = "lost"
    elif state.credits >= GOAL_CREDITS and state.x == 0 and state.y == 0:
        state.status = "won"
    else:
        state.status = "active"


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/api/new-game")
def new_game() -> Dict[str, object]:
    rng = random.Random(time.time())
    seed = rng.randint(1, 999999)
    game_id = uuid.uuid4().hex
    state = GameState(
        id=game_id,
        seed=seed,
        turn=1,
        x=0,
        y=0,
        fuel=MAX_FUEL,
        hull=MAX_HULL,
        credits=20,
        status="active",
        log=["Docked at Base. Systems green."],
        anomalies=generate_anomalies(seed),
        stations=generate_stations(seed),
        pending_event=None,
    )
    games[game_id] = state
    return public_state(state)


@app.post("/api/act")
def act(request: ActionRequest) -> Dict[str, object]:
    state = games.get(request.game_id)
    if not state:
        raise HTTPException(status_code=404, detail="Game not found")

    if state.status != "active":
        return public_state(state)

    action = request.action.lower()
    rng = random.Random(state.seed + state.turn * 31 + state.x * 13 + state.y * 7)
    nearby: Optional[List[Dict[str, object]]] = None

    if state.pending_event and action not in {"fight", "bribe", "evade"}:
        raise HTTPException(status_code=400, detail="Resolve the ambush first")

    if action == "scan":
        nearby = [
            {"id": a["id"], "name": a["name"], "value": a["value"], "risk": a["risk"]}
            for a in state.anomalies
            if (not a["collected"] and a["x"] == state.x and a["y"] == state.y)
        ]
        if nearby:
            state.log.append(f"Scan pinged {len(nearby)} salvage signatures.")
        else:
            state.log.append("Scan found nothing but cold dust.")
    elif action == "travel":
        if state.fuel <= 0:
            raise HTTPException(status_code=400, detail="Out of fuel")
        direction = (request.direction or "").lower()
        dx, dy = 0, 0
        if direction == "n":
            dy = -1
        elif direction == "s":
            dy = 1
        elif direction == "w":
            dx = -1
        elif direction == "e":
            dx = 1
        else:
            raise HTTPException(status_code=400, detail="Invalid direction")

        new_x = state.x + dx
        new_y = state.y + dy
        if new_x < 0 or new_x >= MAP_SIZE or new_y < 0 or new_y >= MAP_SIZE:
            raise HTTPException(status_code=400, detail="Out of bounds")

        state.x = new_x
        state.y = new_y
        state.fuel -= 1
        if rng.random() < 0.15:
            state.hull -= 1
            state.log.append("Micrometeor swarm scraped the hull.")
        else:
            state.log.append("Transit clean. Engines humming.")
        if rng.random() < 0.2:
            state.pending_event = {
                "type": "pirate_ambush",
                "threat": rng.randint(1, 3),
            }
            state.log.append("Pirate ambush! They demand cargo or a fight.")
    elif action == "salvage":
        target_id = request.target_id
        if not target_id:
            raise HTTPException(status_code=400, detail="Missing target_id")
        anomaly = next((a for a in state.anomalies if a["id"] == target_id), None)
        if not anomaly or anomaly["collected"]:
            raise HTTPException(status_code=400, detail="Invalid salvage target")
        if anomaly["x"] != state.x or anomaly["y"] != state.y:
            raise HTTPException(status_code=400, detail="Target not in sector")

        roll = random.Random(state.seed + int(target_id[:8], 16)).random()
        if roll < anomaly["risk"] * 0.15:
            state.hull -= 1
            state.log.append("Salvage snap-back dented the hull.")

        state.credits += anomaly["value"]
        anomaly["collected"] = True
        state.log.append(
            f"Recovered {anomaly['name']} worth {anomaly['value']} credits."
        )
    elif action == "trade":
        station = current_station(state)
        if not station:
            raise HTTPException(status_code=400, detail="No trade station here")
        item = request.item
        if item == "fuel_cell":
            price = 4
            if state.credits < price:
                raise HTTPException(status_code=400, detail="Not enough credits")
            if state.fuel >= MAX_FUEL:
                raise HTTPException(status_code=400, detail="Fuel already full")
            state.credits -= price
            state.fuel = min(MAX_FUEL, state.fuel + 2)
            state.log.append("Traded for fuel cells.")
        elif item == "hull_patch":
            price = 6
            if state.credits < price:
                raise HTTPException(status_code=400, detail="Not enough credits")
            if state.hull >= MAX_HULL:
                raise HTTPException(status_code=400, detail="Hull already full")
            state.credits -= price
            state.hull = min(MAX_HULL, state.hull + 1)
            state.log.append("Installed a fresh hull patch.")
        else:
            raise HTTPException(status_code=400, detail="Invalid trade item")
    elif action == "refuel":
        if state.x != 0 or state.y != 0:
            raise HTTPException(status_code=400, detail="Refuel only at base")
        if state.credits < 5:
            raise HTTPException(status_code=400, detail="Not enough credits")
        if state.fuel >= MAX_FUEL:
            raise HTTPException(status_code=400, detail="Fuel already full")
        state.credits -= 5
        state.fuel = min(MAX_FUEL, state.fuel + 3)
        state.log.append("Docking bay topped off fuel reserves.")
    elif action == "repair":
        if state.x != 0 or state.y != 0:
            raise HTTPException(status_code=400, detail="Repair only at base")
        if state.credits < 8:
            raise HTTPException(status_code=400, detail="Not enough credits")
        if state.hull >= MAX_HULL:
            raise HTTPException(status_code=400, detail="Hull already full")
        state.credits -= 8
        state.hull = min(MAX_HULL, state.hull + 2)
        state.log.append("Mechanics sealed the hull fractures.")
    elif action == "fight":
        if not state.pending_event:
            raise HTTPException(status_code=400, detail="No active threat")
        threat = state.pending_event["threat"]
        if rng.random() < 0.55:
            reward = threat * 6
            state.credits += reward
            state.log.append(f"Fought off pirates and looted {reward} credits.")
        else:
            damage = threat
            loss = min(state.credits, threat * 4)
            state.hull -= damage
            state.credits -= loss
            state.log.append("Pirates scored hits before breaking off.")
        state.pending_event = None
    elif action == "bribe":
        if not state.pending_event:
            raise HTTPException(status_code=400, detail="No active threat")
        threat = state.pending_event["threat"]
        cost = threat * 8
        if state.credits < cost:
            raise HTTPException(status_code=400, detail="Not enough credits")
        state.credits -= cost
        state.pending_event = None
        state.log.append("Paid off the pirates. They drift away.")
    elif action == "evade":
        if not state.pending_event:
            raise HTTPException(status_code=400, detail="No active threat")
        if state.fuel <= 0:
            raise HTTPException(status_code=400, detail="Out of fuel")
        state.fuel -= 1
        if rng.random() < 0.4:
            state.hull -= 1
            state.log.append("Evasion failed. Took a glancing hit.")
        else:
            state.log.append("Evasion successful. Pirates lost the trail.")
        state.pending_event = None
    else:
        raise HTTPException(status_code=400, detail="Unknown action")

    state.turn += 1
    update_status(state)
    return public_state(state, nearby=nearby)

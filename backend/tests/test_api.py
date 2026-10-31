import os, time
os.environ.setdefault("GRINDSENSE_TICK_SECONDS", "0.25")
import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client

def make_session(client, scenario="normal", target="medium"):
    response = client.post("/api/sessions", json={
        "task_type":"chutney","ingredients":["coconut","chilli"],"quantity":250,
        "target_texture":target,"smoothness_level":55,"adaptive_mode":True,
        "simulation_scenario":scenario,"scenario_seed":19
    })
    assert response.status_code == 201, response.text
    return response.json()["id"]

def test_health_discloses_simulation_mode(client):
    response=client.get("/api/health")
    assert response.status_code==200
    assert response.json()=={"status":"ok","mode":"simulation","hardware_connected":False}

def test_session_creation_and_validation(client):
    sid=make_session(client)
    assert client.get(f"/api/sessions/{sid}").json()["status"]=="created"
    assert client.post("/api/sessions",json={"ingredients":[]}).status_code==422

def test_start_telemetry_stop_and_history(client):
    sid=make_session(client)
    assert client.post(f"/api/sessions/{sid}/start").json()["status"]=="running"
    time.sleep(.65)
    rows=client.get(f"/api/sessions/{sid}/telemetry").json()
    assert rows and {"motor_current","motor_load","temperature","vibration","motor_speed","texture_index","progress"} <= rows[0].keys()
    assert client.post(f"/api/sessions/{sid}/stop").json()["status"]=="stopped"
    assert any(row["id"]==sid for row in client.get("/api/sessions").json())
    assert client.get(f"/api/sessions/{sid}/results").status_code==200

def test_safety_scenario_stops_and_records_event(client):
    sid=make_session(client,"overload")
    client.post(f"/api/sessions/{sid}/start")
    deadline=time.time()+8
    while time.time()<deadline:
        if client.get(f"/api/sessions/{sid}").json()["status"]=="safety_stopped": break
        time.sleep(.25)
    assert client.get(f"/api/sessions/{sid}").json()["status"]=="safety_stopped"
    assert any(e["event_type"]=="safety" for e in client.get(f"/api/sessions/{sid}/events").json())


def force_tick(sid, tick):
    from app.main import DB, GrindSession
    db=DB()
    try:
        session=db.get(GrindSession,sid)
        session.tick=tick
        db.commit()
    finally:
        db.close()

@pytest.mark.parametrize(("scenario","tick"),[("high_temperature",100),("high_vibration",30)])
def test_temperature_and_vibration_safety_stops(client,scenario,tick):
    sid=make_session(client,scenario)
    force_tick(sid,tick)
    client.post(f"/api/sessions/{sid}/start")
    deadline=time.time()+3
    while time.time()<deadline:
        result=client.get(f"/api/sessions/{sid}").json()
        if result["status"]=="safety_stopped": break
        time.sleep(.1)
    assert client.get(f"/api/sessions/{sid}").json()["status"]=="safety_stopped"
    assert any(e["event_type"]=="safety" for e in client.get(f"/api/sessions/{sid}/events").json())

def test_adaptive_event_and_target_completion(client):
    sid=make_session(client,target="coarse")
    client.post(f"/api/sessions/{sid}/start")
    deadline=time.time()+9
    result=client.get(f"/api/sessions/{sid}").json()
    while time.time()<deadline and result["status"]=="running":
        time.sleep(.25)
        result=client.get(f"/api/sessions/{sid}").json()
    assert result["status"]=="completed"
    assert result["estimated_texture_score"] is not None
    assert any(e["event_type"]=="adaptive" for e in client.get(f"/api/sessions/{sid}/events").json())

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
    session=client.get(f"/api/sessions/{sid}").json()
    assert session["status"]=="created"
    assert session["jar_present"] is True
    assert session["lid_locked"] is True
    assert session["attachment_present"] is True
    assert client.post("/api/sessions",json={"ingredients":[]}).status_code==422

def test_all_safe_interlocks_allow_start(client):
    sid=make_session(client)
    started=client.post(f"/api/sessions/{sid}/start")
    assert started.status_code==200
    assert started.json()["status"]=="running"
    assert client.post(f"/api/sessions/{sid}/stop").json()["status"]=="stopped"

@pytest.mark.parametrize(
    ("unsafe_state","reason"),
    [
        ({"jar_present":False},"Jar is not present"),
        ({"lid_locked":False},"Lid is not locked"),
        ({"attachment_present":False},"Attachment is not present"),
    ],
)
def test_unsafe_component_blocks_start_without_telemetry(client,unsafe_state,reason):
    payload={"task_type":"chutney","ingredients":["coconut"],**unsafe_state}
    created=client.post("/api/sessions",json=payload)
    assert created.status_code==201
    sid=created.json()["id"]

    response=client.post(f"/api/sessions/{sid}/start")
    assert response.status_code==409
    assert reason in response.json()["detail"]
    assert client.get(f"/api/sessions/{sid}").json()["status"]=="created"
    assert client.get(f"/api/sessions/{sid}/telemetry").json()==[]
    event=client.get(f"/api/sessions/{sid}/events").json()[-1]
    assert event["event_type"]=="safety"
    assert event["severity"]=="critical"
    assert reason in event["explanation"]

def test_multiple_unsafe_components_are_all_reported(client):
    created=client.post("/api/sessions",json={
        "task_type":"chutney","ingredients":["coconut"],
        "jar_present":False,"lid_locked":False,"attachment_present":False
    })
    sid=created.json()["id"]
    response=client.post(f"/api/sessions/{sid}/start")
    assert response.status_code==409
    detail=response.json()["detail"]
    assert "Jar is not present" in detail
    assert "Lid is not locked" in detail
    assert "Attachment is not present" in detail
    assert client.get(f"/api/sessions/{sid}/telemetry").json()==[]

def test_component_becoming_unsafe_stops_running_session(client):
    sid=make_session(client,target="smooth")
    assert client.post(f"/api/sessions/{sid}/start").json()["status"]=="running"
    deadline=time.time()+3
    rows=client.get(f"/api/sessions/{sid}/telemetry").json()
    while time.time()<deadline and not rows:
        time.sleep(.05)
        rows=client.get(f"/api/sessions/{sid}/telemetry").json()
    assert rows

    response=client.post(f"/api/sessions/{sid}/interlocks",json={
        "jar_present":True,"lid_locked":False,"attachment_present":True
    })
    assert response.status_code==200
    assert response.json()["status"]=="safety_stopped"
    assert "Lid is not locked" in response.json()["result_summary"]
    count_at_stop=len(client.get(f"/api/sessions/{sid}/telemetry").json())
    time.sleep(.4)
    assert len(client.get(f"/api/sessions/{sid}/telemetry").json())==count_at_stop
    safety_events=[event for event in client.get(f"/api/sessions/{sid}/events").json()
                   if event["event_type"]=="safety" and event["severity"]=="critical"]
    assert safety_events
    assert safety_events[-1]["previous_state"]["lid_locked"] is True
    assert safety_events[-1]["new_state"]["lid_locked"] is False
    assert safety_events[-1]["new_state"]["status"]=="safety_stopped"

def test_unsafe_interlock_blocks_resume_without_new_telemetry(client):
    sid=make_session(client)
    assert client.post(f"/api/sessions/{sid}/start").json()["status"]=="running"
    assert client.post(f"/api/sessions/{sid}/pause").json()["status"]=="paused"
    update=client.post(f"/api/sessions/{sid}/interlocks",json={
        "jar_present":True,"lid_locked":False,"attachment_present":True
    })
    assert update.status_code==200

    telemetry_before=client.get(f"/api/sessions/{sid}/telemetry").json()
    response=client.post(f"/api/sessions/{sid}/resume")
    assert response.status_code==409
    assert "Lid is not locked" in response.json()["detail"]
    assert client.get(f"/api/sessions/{sid}").json()["status"]=="paused"
    time.sleep(.35)
    assert client.get(f"/api/sessions/{sid}/telemetry").json()==telemetry_before
    safety_events=[event for event in client.get(f"/api/sessions/{sid}/events").json()
                   if event["event_type"]=="safety" and event["severity"]=="critical"]
    assert safety_events
    assert "Lid is not locked" in safety_events[-1]["explanation"]

def test_repeated_unsafe_update_after_safety_stop_adds_no_duplicate_event(client):
    sid=make_session(client,target="smooth")
    assert client.post(f"/api/sessions/{sid}/start").json()["status"]=="running"
    unsafe={"jar_present":True,"lid_locked":False,"attachment_present":True}
    stopped=client.post(f"/api/sessions/{sid}/interlocks",json=unsafe)
    assert stopped.status_code==200
    assert stopped.json()["status"]=="safety_stopped"

    events_before=client.get(f"/api/sessions/{sid}/events").json()
    safety_count_before=sum(event["event_type"]=="safety" for event in events_before)
    telemetry_before=client.get(f"/api/sessions/{sid}/telemetry").json()
    assert safety_count_before>=1

    repeated=client.post(f"/api/sessions/{sid}/interlocks",json=unsafe)
    assert repeated.status_code==409
    time.sleep(.35)
    events_after=client.get(f"/api/sessions/{sid}/events").json()
    assert sum(event["event_type"]=="safety" for event in events_after)==safety_count_before
    assert client.get(f"/api/sessions/{sid}/telemetry").json()==telemetry_before

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


def test_overload_scenario_predicts_current_and_stops_on_current_before_load(client):
    sid=make_session(client,"overload")
    assert client.post(f"/api/sessions/{sid}/start").json()["status"]=="running"
    deadline=time.time()+8
    while time.time()<deadline:
        current=client.get(f"/api/sessions/{sid}").json()
        if current["status"]=="safety_stopped":
            break
        time.sleep(.05)

    session=client.get(f"/api/sessions/{sid}").json()
    assert session["status"]=="safety_stopped"
    readings=client.get(f"/api/sessions/{sid}/telemetry").json()
    events=client.get(f"/api/sessions/{sid}/events").json()
    current_predictions=[
        event for event in events
        if event["event_type"]=="predictive_warning"
        and event["new_state"]["metric"]=="motor_current"
    ]
    current_stops=[
        event for event in events
        if event["event_type"]=="safety" and "motor-current threshold" in event["explanation"]
    ]
    assert current_predictions
    assert current_stops
    assert events.index(current_predictions[0])<events.index(current_stops[-1])
    assert readings[-1]["motor_current"]>=11.5
    assert readings[-1]["motor_load"]<96


def force_tick(sid, tick):
    from app.main import DB, GrindSession
    db=DB()
    try:
        session=db.get(GrindSession,sid)
        session.tick=tick
        db.commit()
    finally:
        db.close()


def virtual_reading(**updates):
    values={
        "motor_current":5.0,"motor_load":60.0,"temperature":40.0,"vibration":3.0,
        "motor_speed":650.0,"texture_index":20.0,"progress":10.0,
    }
    values.update(updates)
    return values


def seed_load_history(sid, loads):
    from app.main import DB, GrindSession, Telemetry
    db=DB()
    try:
        session=db.get(GrindSession,sid)
        session.adaptive_mode=False
        for load in loads:
            db.add(Telemetry(session_id=sid,**virtual_reading(motor_load=load)))
        db.commit()
    finally:
        db.close()


def seed_telemetry_history(sid, readings):
    from app.main import DB, Telemetry
    db=DB()
    try:
        for values in readings:
            db.add(Telemetry(session_id=sid,**virtual_reading(**values)))
        db.commit()
    finally:
        db.close()


def advance_with_reading(monkeypatch, sid, **values):
    import app.main as main
    monkeypatch.setattr(main,"generate_reading",lambda _session:virtual_reading(**values))
    db=main.DB()
    try:
        session=db.get(main.GrindSession,sid)
        main.advance(db,session)
        db.commit()
        return session.status
    finally:
        db.close()


def test_predictive_events_deduplicate_recover_and_preserve_event_shape(client,monkeypatch):
    from app.main import DB, Event
    sid=make_session(client)
    seed_load_history(sid,[72,74,76])
    advance_with_reading(monkeypatch,sid,motor_load=77)

    db=DB()
    try:
        first_count=db.query(Event).filter_by(session_id=sid,event_type="predictive_warning").count()
    finally:
        db.close()
    assert first_count==1

    advance_with_reading(monkeypatch,sid,motor_load=77.5)
    db=DB()
    try:
        assert db.query(Event).filter_by(session_id=sid,event_type="predictive_warning").count()==1
    finally:
        db.close()

    for value in [60,60,60,70,72,74]:
        advance_with_reading(monkeypatch,sid,motor_load=value)
    db=DB()
    try:
        assert db.query(Event).filter_by(session_id=sid,event_type="predictive_recovery").count()==1
        assert db.query(Event).filter_by(session_id=sid,event_type="predictive_warning").count()==2
    finally:
        db.close()

    predictive=[event for event in client.get(f"/api/sessions/{sid}/events").json()
                if event["event_type"]=="predictive_warning"]
    assert "PREDICTIVE WARNING" in predictive[-1]["explanation"]
    assert predictive[-1]["severity"]=="warning"
    assert predictive[-1]["new_state"]["metric"]=="motor_load"
    assert set(predictive[-1])=={
        "timestamp","event_type","previous_state","new_state","severity","explanation"
    }


def test_predictive_warning_does_not_suppress_actual_threshold_warning(client,monkeypatch):
    from app.main import DB, Event
    sid=make_session(client)
    seed_load_history(sid,[72,74,76])
    advance_with_reading(monkeypatch,sid,motor_load=77)
    advance_with_reading(monkeypatch,sid,motor_load=78)

    db=DB()
    try:
        assert db.query(Event).filter_by(session_id=sid,event_type="predictive_warning").count()==1
        threshold_warnings=[
            event for event in db.query(Event).filter_by(session_id=sid,event_type="warning").all()
            if "load" in event.explanation.lower()
        ]
        assert threshold_warnings
    finally:
        db.close()


def test_predictive_warning_does_not_suppress_critical_safety_stop(client,monkeypatch):
    from app.main import DB, Event, GrindSession
    sid=make_session(client)
    seed_load_history(sid,[72,74,76])
    advance_with_reading(monkeypatch,sid,motor_load=77)
    status=advance_with_reading(monkeypatch,sid,motor_load=97,motor_current=10)
    assert status=="safety_stopped"

    db=DB()
    try:
        assert db.query(Event).filter_by(session_id=sid,event_type="predictive_warning").count()==1
        assert db.query(Event).filter_by(session_id=sid,event_type="safety").count()==1
        assert db.get(GrindSession,sid).status=="safety_stopped"
    finally:
        db.close()


def test_predictive_deduplication_isolated_between_sessions(client,monkeypatch):
    from app.main import DB, Event
    first_sid=make_session(client)
    second_sid=make_session(client)
    seed_load_history(first_sid,[72,74,76])
    seed_load_history(second_sid,[60,60,60])

    advance_with_reading(monkeypatch,first_sid,motor_load=77)
    advance_with_reading(monkeypatch,second_sid,motor_load=61)
    db=DB()
    try:
        assert db.query(Event).filter_by(session_id=first_sid,event_type="predictive_warning").count()==1
        assert db.query(Event).filter_by(session_id=second_sid,event_type="predictive_warning").count()==0
    finally:
        db.close()

    advance_with_reading(monkeypatch,second_sid,motor_load=70)
    advance_with_reading(monkeypatch,second_sid,motor_load=72)
    db=DB()
    try:
        assert db.query(Event).filter_by(session_id=first_sid,event_type="predictive_warning").count()==1
        assert db.query(Event).filter_by(session_id=second_sid,event_type="predictive_warning").count()==1
    finally:
        db.close()


def test_predictive_metric_recovery_is_independent_within_session(client,monkeypatch):
    from app.main import DB, Event
    sid=make_session(client)
    seed_telemetry_history(sid,[
        {"motor_load":72,"temperature":66},
        {"motor_load":74,"temperature":68},
        {"motor_load":76,"temperature":70},
    ])
    advance_with_reading(monkeypatch,sid,motor_load=77,temperature=71)

    db=DB()
    try:
        assert db.query(Event).filter_by(session_id=sid,event_type="predictive_warning").count()==2
    finally:
        db.close()

    advance_with_reading(monkeypatch,sid,motor_load=77,temperature=60)
    db=DB()
    try:
        recoveries=db.query(Event).filter_by(session_id=sid,event_type="predictive_recovery").all()
        assert [event.new_state["metric"] for event in recoveries]==["temperature"]
        assert db.query(Event).filter_by(session_id=sid,event_type="predictive_warning").count()==2
    finally:
        db.close()

    for temperature in [60,60,60,60,63,66,69]:
        advance_with_reading(monkeypatch,sid,motor_load=77,temperature=temperature)
    db=DB()
    try:
        warnings=db.query(Event).filter_by(session_id=sid,event_type="predictive_warning").all()
        assert sum(event.new_state["metric"]=="motor_load" for event in warnings)==1
        assert sum(event.new_state["metric"]=="temperature" for event in warnings)==2
    finally:
        db.close()


def test_prediction_only_does_not_change_controls_or_session_status(client,monkeypatch):
    from app.main import DB, GrindSession
    sid=make_session(client)
    seed_telemetry_history(sid,[
        {"motor_load":65,"temperature":60},
        {"motor_load":65,"temperature":62},
        {"motor_load":65,"temperature":64},
        {"motor_load":65,"temperature":66},
    ])
    before=client.get(f"/api/sessions/{sid}").json()
    advance_with_reading(monkeypatch,sid,motor_load=65,temperature=68)
    after=client.get(f"/api/sessions/{sid}").json()
    assert after["status"]==before["status"]=="created"

    db=DB()
    try:
        session=db.get(GrindSession,sid)
        assert session.speed_rpm==900
        assert session.intensity==0.72
        assert session.pulse_pattern=="3s on / 1s rest"
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

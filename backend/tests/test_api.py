import asyncio, os, time
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

def set_session_status(sid,status):
    from app.main import DB, GrindSession
    db=DB()
    try:
        db.get(GrindSession,sid).status=status
        db.commit()
    finally:
        db.close()

def session_snapshot(sid):
    from app.main import DB, Event, GrindSession, Telemetry
    db=DB()
    try:
        session=db.get(GrindSession,sid)
        return session.status,db.query(Telemetry).filter_by(session_id=sid).count(),db.query(Event).filter_by(session_id=sid).count()
    finally:
        db.close()

def active_simulation_tasks(sid):
    return [
        task for task in asyncio.all_tasks()
        if task.get_name()==f"grindsense:{sid}" and not task.done()
    ]

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

@pytest.mark.parametrize("ingredient",["", "   ", "\t\n"])
def test_session_creation_rejects_blank_ingredient_names(client,ingredient):
    response=client.post("/api/sessions",json={"ingredients":["coconut",ingredient]})
    assert response.status_code==422
    assert "Ingredient names must not be empty or whitespace-only." in response.text

def test_session_creation_preserves_valid_ingredient_names(client):
    ingredients=["coconut", " Chilli "]
    response=client.post("/api/sessions",json={"ingredients":ingredients})
    assert response.status_code==201
    assert response.json()["ingredients"]==ingredients

def test_startup_recovery_pauses_running_session_once_and_allows_resume(client):
    from app.main import DB, GrindSession, recover_running_sessions, tasks

    assert recover_running_sessions in app.router.on_startup
    sid=make_session(client)
    db=DB()
    try:
        session=db.get(GrindSession,sid)
        session.status="running"  # Simulate a running row persisted before process restart.
        db.commit()
    finally:
        db.close()

    recover_running_sessions()
    recover_running_sessions()

    recovered=client.get(f"/api/sessions/{sid}").json()
    assert recovered["status"]=="paused"
    assert client.get(f"/api/sessions/{sid}/telemetry").json()==[]
    events=client.get(f"/api/sessions/{sid}/events").json()
    recovery_events=[event for event in events if "Application restarted" in event["explanation"]]
    assert len(recovery_events)==1
    assert recovery_events[0]["event_type"]=="info"
    assert recovery_events[0]["previous_state"]=={"status":"running"}
    assert recovery_events[0]["new_state"]=={"status":"paused"}

    assert client.post(f"/api/sessions/{sid}/resume").json()["status"]=="running"
    task=tasks[sid]
    assert not task.done()
    assert client.post(f"/api/sessions/{sid}/resume").status_code==409
    assert tasks[sid] is task

    deadline=time.time()+2
    telemetry=client.get(f"/api/sessions/{sid}/telemetry").json()
    while time.time()<deadline and not telemetry:
        time.sleep(.02)
        telemetry=client.get(f"/api/sessions/{sid}/telemetry").json()
    assert telemetry

    assert client.post(f"/api/sessions/{sid}/pause").json()["status"]=="paused"
    deadline=time.time()+1
    while time.time()<deadline and not task.done():
        time.sleep(.01)
    assert task.done()

def test_startup_recovery_leaves_terminal_sessions_unchanged(client):
    from app.main import DB, GrindSession, recover_running_sessions

    session_ids=[make_session(client) for _ in range(3)]
    terminal_statuses=("stopped", "completed", "safety_stopped")
    db=DB()
    try:
        for sid,status in zip(session_ids,terminal_statuses):
            db.get(GrindSession,sid).status=status
        db.commit()
    finally:
        db.close()

    recover_running_sessions()

    assert [client.get(f"/api/sessions/{sid}").json()["status"] for sid in session_ids]==list(terminal_statuses)
    assert all(client.get(f"/api/sessions/{sid}/events").json()==[] for sid in session_ids)

def test_concurrent_start_requests_create_exactly_one_active_task(client):
    import app.main as main
    sid=make_session(client)

    async def exercise():
        responses=await asyncio.gather(main.start(sid),main.start(sid))
        active=active_simulation_tasks(sid)
        assert len(active)==1
        assert main.tasks[sid] is active[0]
        await main.stop(sid)
        return responses

    responses=asyncio.run(exercise())
    assert [response["status"] for response in responses]==["running","running"]
    assert sid not in main.tasks
    assert session_snapshot(sid)[0]=="stopped"

def test_concurrent_resume_requests_create_exactly_one_active_task(client):
    import app.main as main
    sid=make_session(client)

    async def exercise():
        await main.start(sid)
        await main.pause(sid)
        assert sid not in main.tasks
        outcomes=await asyncio.gather(main.resume(sid),main.resume(sid),return_exceptions=True)
        successes=[value for value in outcomes if isinstance(value,dict)]
        conflicts=[value for value in outcomes if isinstance(value,HTTPException)]
        active=active_simulation_tasks(sid)
        assert len(successes)==1
        assert len(conflicts)==1 and conflicts[0].status_code==409
        assert len(active)==1 and main.tasks[sid] is active[0]
        await main.stop(sid)
        return successes

    from fastapi import HTTPException
    successes=asyncio.run(exercise())
    assert successes[0]["status"]=="running"
    assert sid not in main.tasks
    assert session_snapshot(sid)[0]=="stopped"

def test_stop_serializes_with_queued_simulation_tick(client):
    import app.main as main
    sid=make_session(client)
    set_session_status(sid,"running")

    async def exercise():
        async with main.session_guard(sid):
            tick_ready=asyncio.Event()
            stop_ready=asyncio.Event()

            async def queued_tick():
                tick_ready.set()
                return await main.simulation_tick(sid)

            async def queued_stop():
                stop_ready.set()
                return await main.stop(sid)

            tick=asyncio.create_task(queued_tick())
            await tick_ready.wait()
            stopping=asyncio.create_task(queued_stop())
            await stop_ready.wait()
        tick_ran,stopped=await asyncio.gather(tick,stopping)
        return tick_ran,stopped

    tick_ran,stopped=asyncio.run(exercise())
    assert tick_ran is True
    assert stopped["status"]=="stopped"
    status,count,_=session_snapshot(sid)
    assert status=="stopped" and count==1
    assert asyncio.run(main.simulation_tick(sid)) is False
    assert session_snapshot(sid)[1]==count

def test_pause_serializes_with_queued_simulation_tick(client):
    import app.main as main
    sid=make_session(client)
    set_session_status(sid,"running")

    async def exercise():
        async with main.session_guard(sid):
            tick_ready=asyncio.Event()
            pause_ready=asyncio.Event()

            async def queued_tick():
                tick_ready.set()
                return await main.simulation_tick(sid)

            async def queued_pause():
                pause_ready.set()
                return await main.pause(sid)

            tick=asyncio.create_task(queued_tick())
            await tick_ready.wait()
            pausing=asyncio.create_task(queued_pause())
            await pause_ready.wait()
        tick_ran,paused=await asyncio.gather(tick,pausing)
        return tick_ran,paused

    tick_ran,paused=asyncio.run(exercise())
    assert tick_ran is True
    assert paused["status"]=="paused"
    status,count,_=session_snapshot(sid)
    assert status=="paused" and count==1
    assert asyncio.run(main.simulation_tick(sid)) is False
    assert session_snapshot(sid)[1]==count

def test_runtime_interlock_stop_serializes_with_tick_and_cleans_task(client,monkeypatch):
    import app.main as main
    sid=make_session(client,target="smooth")
    monkeypatch.setattr(main,"TICK",3600)

    async def exercise():
        await main.start(sid)
        active_task=main.tasks[sid]
        async with main.session_guard(sid):
            tick_ready=asyncio.Event()
            interlock_ready=asyncio.Event()

            async def queued_tick():
                tick_ready.set()
                return await main.simulation_tick(sid)

            async def queued_interlock():
                interlock_ready.set()
                return await main.update_interlocks(
                    sid,main.InterlockUpdate(jar_present=True,lid_locked=False,attachment_present=True)
                )

            tick=asyncio.create_task(queued_tick())
            await tick_ready.wait()
            interlock=asyncio.create_task(queued_interlock())
            await interlock_ready.wait()
        tick_ran,stopped=await asyncio.gather(tick,interlock)
        return tick_ran,stopped,active_task

    tick_ran,stopped,task=asyncio.run(exercise())
    assert tick_ran is True
    assert stopped["status"]=="safety_stopped"
    assert task.done() and sid not in main.tasks
    status,count,_=session_snapshot(sid)
    assert status=="safety_stopped" and count==1
    assert asyncio.run(main.simulation_tick(sid)) is False
    assert session_snapshot(sid)[1]==count

def test_completion_and_stop_races_preserve_first_terminal_state(client,monkeypatch):
    import app.main as main
    completed_sid=make_session(client,target="coarse")
    stopped_sid=make_session(client,target="coarse")
    set_session_status(completed_sid,"running")
    set_session_status(stopped_sid,"running")
    monkeypatch.setattr(main,"generate_reading",lambda _s:virtual_reading(texture_index=100,progress=100))

    async def race(sid,first):
        async with main.session_guard(sid):
            first_ready=asyncio.Event()
            second_ready=asyncio.Event()

            async def queued(operation,ready):
                ready.set()
                return await operation

            tick_operation=main.simulation_tick(sid)
            stop_operation=main.stop(sid)
            first_operation=tick_operation if first=="tick" else stop_operation
            second_operation=stop_operation if first=="tick" else tick_operation
            first_task=asyncio.create_task(queued(first_operation,first_ready))
            await first_ready.wait()
            second_task=asyncio.create_task(queued(second_operation,second_ready))
            await second_ready.wait()
        return await asyncio.gather(first_task,second_task)

    completed_outcomes=asyncio.run(race(completed_sid,"tick"))
    stopped_outcomes=asyncio.run(race(stopped_sid,"stop"))
    assert completed_outcomes[0] is False
    assert completed_outcomes[1]["status"]=="completed"
    assert session_snapshot(completed_sid)[:2]==("completed",1)
    assert stopped_outcomes[0]["status"]=="stopped"
    assert stopped_outcomes[1] is False
    assert session_snapshot(stopped_sid)[:2]==("stopped",0)

def test_simulation_exception_pauses_records_error_and_cleans_task(client,monkeypatch):
    import app.main as main
    sid=make_session(client)
    monkeypatch.setattr(main,"TICK",0)
    monkeypatch.setattr(main,"advance",lambda _db,_session:(_ for _ in ()).throw(RuntimeError("simulated failure")))

    async def exercise():
        await main.start(sid)
        task=main.tasks[sid]
        await task
        return task

    task=asyncio.run(exercise())
    assert task.done() and sid not in main.tasks
    status,_,_=session_snapshot(sid)
    assert status=="paused"
    events=client.get(f"/api/sessions/{sid}/events").json()
    errors=[event for event in events if event["event_type"]=="error"]
    assert len(errors)==1 and errors[0]["severity"]=="warning"
    assert "RuntimeError" in errors[0]["explanation"]

def test_completed_simulation_task_is_removed_from_registry(client,monkeypatch):
    import app.main as main
    sid=make_session(client,target="coarse")
    monkeypatch.setattr(main,"TICK",0)
    monkeypatch.setattr(main,"generate_reading",lambda _s:virtual_reading(texture_index=100,progress=100))

    async def exercise():
        await main.start(sid)
        task=main.tasks[sid]
        await task
        assert task.done()
        assert sid not in main.tasks
        return active_simulation_tasks(sid)

    assert asyncio.run(exercise())==[]
    assert session_snapshot(sid)[0]=="completed"

@pytest.mark.parametrize("status",["paused","stopped","completed","safety_stopped"])
def test_task_error_preserves_nonrunning_state(client,status):
    import app.main as main
    sid=make_session(client)
    set_session_status(sid,status)
    asyncio.run(main._pause_after_task_error(sid,RuntimeError("late failure")))
    assert session_snapshot(sid)[0]==status
    assert client.get(f"/api/sessions/{sid}/events").json()==[]

def test_reference_counted_session_lock_is_retained_for_waiter_then_removed():
    import app.main as main
    sid="lock-regression-session"

    async def exercise():
        loop=asyncio.get_running_loop()
        key=(loop,sid)
        entered=asyncio.Event()
        release=asyncio.Event()

        async def holder():
            async with main.session_guard(sid):
                entered.set()
                await release.wait()

        async def waiter():
            async with main.session_guard(sid):
                return True

        first=asyncio.create_task(holder())
        await entered.wait()
        second=asyncio.create_task(waiter())
        await asyncio.sleep(0)
        assert main._session_locks[key].references==2
        release.set()
        assert await asyncio.gather(first,second)==[None,True]
        assert key not in main._session_locks

    asyncio.run(exercise())

def test_all_safe_interlocks_allow_start(client):
    sid=make_session(client)
    started=client.post(f"/api/sessions/{sid}/start")
    assert started.status_code==200
    assert started.json()["status"]=="running"
    assert client.post(f"/api/sessions/{sid}/stop").json()["status"]=="stopped"

def test_simulation_api_returns_acoustic_and_torque_proxy_indices(client):
    sid=make_session(client,target="coarse")
    assert client.post(f"/api/sessions/{sid}/start").status_code==200
    deadline=time.time()+3
    rows=client.get(f"/api/sessions/{sid}/telemetry").json()
    while time.time()<deadline and not rows:
        time.sleep(.05)
        rows=client.get(f"/api/sessions/{sid}/telemetry").json()
    assert rows
    assert 0 <= rows[0]["acoustic_signature_index"] <= 120
    assert 0 <= rows[0]["torque_demand_index"] <= 100
    assert client.post(f"/api/sessions/{sid}/stop").status_code==200

def test_high_acoustic_scenario_is_accepted(client):
    response=client.post("/api/sessions",json={
        "task_type":"chutney","ingredients":["coconut"],
        "simulation_scenario":"high_acoustic"
    })
    assert response.status_code==201, response.text
    assert response.json()["simulation_scenario"]=="high_acoustic"

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

def test_running_stop_records_one_info_event_and_remains_idempotent(client,monkeypatch):
    import app.main as main
    sid=make_session(client)
    monkeypatch.setattr(main,"TICK",3600)
    assert client.post(f"/api/sessions/{sid}/start").json()["status"]=="running"

    stopped=client.post(f"/api/sessions/{sid}/stop")
    assert stopped.status_code==200
    assert stopped.json()["status"]=="stopped"
    events_before=client.get(f"/api/sessions/{sid}/events").json()
    stop_events=[event for event in events_before if event["explanation"]=="Simulation stopped by user."]
    assert len(stop_events)==1
    assert stop_events[0]["event_type"]=="info"
    assert stop_events[0]["severity"]=="info"

    repeated=client.post(f"/api/sessions/{sid}/stop")
    assert repeated.status_code==200
    assert repeated.json()["status"]=="stopped"
    assert client.get(f"/api/sessions/{sid}/events").json()==events_before
    assert client.post(f"/api/sessions/{sid}/start").status_code==409

def test_paused_session_can_be_stopped_without_new_telemetry_or_duplicate_events(client):
    import app.main as main
    sid=make_session(client)
    set_session_status(sid,"running")
    assert asyncio.run(main.simulation_tick(sid)) is True
    set_session_status(sid,"paused")
    telemetry_before=client.get(f"/api/sessions/{sid}/telemetry").json()

    stopped=client.post(f"/api/sessions/{sid}/stop")
    assert stopped.status_code==200
    assert stopped.json()["status"]=="stopped"
    events_after_first_stop=client.get(f"/api/sessions/{sid}/events").json()
    stop_events=[event for event in events_after_first_stop if event["explanation"]=="Simulation stopped by user."]
    assert len(stop_events)==1
    assert stop_events[0]["event_type"]=="info"
    assert stop_events[0]["severity"]=="info"
    assert stop_events[0]["previous_state"]=={"status":"paused"}
    assert stop_events[0]["new_state"]=={"status":"stopped"}
    assert client.get(f"/api/sessions/{sid}/telemetry").json()==telemetry_before

    repeated=client.post(f"/api/sessions/{sid}/stop")
    assert repeated.status_code==200
    assert repeated.json()["status"]=="stopped"
    assert client.get(f"/api/sessions/{sid}/events").json()==events_after_first_stop
    assert client.get(f"/api/sessions/{sid}/telemetry").json()==telemetry_before
    assert client.post(f"/api/sessions/{sid}/start").status_code==409

def test_paused_stop_cancels_and_awaits_any_registered_task(client,monkeypatch):
    import app.main as main
    sid=make_session(client)
    monkeypatch.setattr(main,"TICK",3600)

    async def exercise():
        await main.start(sid)
        task=main.tasks[sid]
        # Simulate a paused row with a task reference left by an interrupted caller.
        async with main.session_guard(sid):
            db=main.DB()
            try:
                session=db.get(main.GrindSession,sid)
                session.status="paused"
                db.commit()
            finally:
                db.close()
        response=await main.stop(sid)
        return response,task

    response,task=asyncio.run(exercise())
    assert response["status"]=="stopped"
    assert task.done()
    assert sid not in main.tasks
    assert session_snapshot(sid)[1]==0

@pytest.mark.parametrize("terminal_status",["completed","safety_stopped"])
def test_stop_preserves_completed_and_safety_stopped_sessions(client,terminal_status):
    sid=make_session(client)
    set_session_status(sid,terminal_status)
    events_before=client.get(f"/api/sessions/{sid}/events").json()

    response=client.post(f"/api/sessions/{sid}/stop")

    assert response.status_code==200
    assert response.json()["status"]==terminal_status
    assert client.get(f"/api/sessions/{sid}/events").json()==events_before
    assert client.post(f"/api/sessions/{sid}/start").status_code==409

def test_manually_stopped_session_cannot_be_restarted(client):
    sid=make_session(client)
    assert client.post(f"/api/sessions/{sid}/start").json()["status"]=="running"
    assert client.post(f"/api/sessions/{sid}/stop").json()["status"]=="stopped"

    response=client.post(f"/api/sessions/{sid}/start")
    assert response.status_code==409
    assert response.json()["detail"]=="Finished session cannot be restarted."
    assert client.get(f"/api/sessions/{sid}").json()["status"]=="stopped"

def test_safety_scenario_stops_and_records_event(client):
    sid=make_session(client,"overload")
    client.post(f"/api/sessions/{sid}/start")
    deadline=time.time()+8
    while time.time()<deadline:
        if client.get(f"/api/sessions/{sid}").json()["status"]=="safety_stopped": break
        time.sleep(.25)
    assert client.get(f"/api/sessions/{sid}").json()["status"]=="safety_stopped"
    assert any(e["event_type"]=="safety" for e in client.get(f"/api/sessions/{sid}/events").json())
    assert client.post(f"/api/sessions/{sid}/start").status_code==409


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
        "acoustic_signature_index":45.0,"torque_demand_index":43.0,
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
    adaptive_events=[e for e in client.get(f"/api/sessions/{sid}/events").json() if e["event_type"]=="adaptive"]
    assert adaptive_events
    assert all("pulse_pattern" in event["new_state"] for event in adaptive_events)
    assert client.post(f"/api/sessions/{sid}/start").status_code==409

import asyncio, os, uuid
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, String, Float, Integer, Boolean, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from app.controller import (
    PREDICTIVE_RESET_MARGIN,
    PREDICTIVE_THRESHOLDS,
    adapt,
    predictive_warnings,
    safety_stop_reason,
    warning_reasons,
)
from app.simulation import generate_reading, texture_complete

URL=os.getenv("GRINDSENSE_DATABASE_URL","sqlite:///./grindsense.db")
engine=create_engine(URL,connect_args={"check_same_thread":False} if URL.startswith("sqlite") else {})
DB=sessionmaker(bind=engine,expire_on_commit=False)
Base=declarative_base()
def now(): return datetime.now(timezone.utc)

class GrindSession(Base):
    __tablename__="grinding_sessions"
    id=Column(String,primary_key=True); task_type=Column(String); ingredients=Column(JSON); quantity=Column(Float)
    target_texture=Column(String); smoothness_level=Column(Integer); adaptive_mode=Column(Boolean,default=True)
    added_water_ml=Column(Float,default=0); preparation_type=Column(String,default="Wet preparation")
    jar_present=Column(Boolean,default=True,nullable=False,server_default="1")
    lid_locked=Column(Boolean,default=True,nullable=False,server_default="1")
    attachment_present=Column(Boolean,default=True,nullable=False,server_default="1")
    simulation_scenario=Column(String,default="normal"); scenario_seed=Column(Integer,default=42)
    status=Column(String,default="created"); progress=Column(Float,default=0); tick=Column(Integer,default=0)
    speed_rpm=Column(Float,default=900); intensity=Column(Float,default=.72); pulse_pattern=Column(String,default="3s on / 1s rest")
    started_at=Column(DateTime(timezone=True)); completed_at=Column(DateTime(timezone=True))
    estimated_texture_score=Column(Float); result_summary=Column(Text); created_at=Column(DateTime(timezone=True),default=now)
    telemetry=relationship("Telemetry",cascade="all, delete-orphan",order_by="Telemetry.id")
    events=relationship("Event",cascade="all, delete-orphan",order_by="Event.id")
class Telemetry(Base):
    __tablename__="telemetry_records"
    id=Column(Integer,primary_key=True); session_id=Column(ForeignKey("grinding_sessions.id"),index=True); timestamp=Column(DateTime(timezone=True),default=now)
    motor_current=Column(Float); motor_load=Column(Float); temperature=Column(Float); vibration=Column(Float); motor_speed=Column(Float); texture_index=Column(Float); progress=Column(Float)
class Event(Base):
    __tablename__="session_events"
    id=Column(Integer,primary_key=True); session_id=Column(ForeignKey("grinding_sessions.id"),index=True); timestamp=Column(DateTime(timezone=True),default=now)
    event_type=Column(String); previous_state=Column(JSON); new_state=Column(JSON); severity=Column(String,default="info"); explanation=Column(Text)

Base.metadata.create_all(engine)
def ensure_sqlite_session_columns(database_engine):
    """Add backward-compatible defaults for columns missing from old SQLite databases."""
    with database_engine.begin() as conn:
        cols={row[1] for row in conn.exec_driver_sql("PRAGMA table_info(grinding_sessions)")}
        additions={
            "added_water_ml":"FLOAT NOT NULL DEFAULT 0",
            "preparation_type":"VARCHAR DEFAULT 'Wet preparation'",
            "jar_present":"BOOLEAN NOT NULL DEFAULT 1",
            "lid_locked":"BOOLEAN NOT NULL DEFAULT 1",
            "attachment_present":"BOOLEAN NOT NULL DEFAULT 1",
        }
        for name,definition in additions.items():
            if name not in cols:
                conn.exec_driver_sql(f"ALTER TABLE grinding_sessions ADD COLUMN {name} {definition}")
if URL.startswith("sqlite"): ensure_sqlite_session_columns(engine)
app=FastAPI(title="GrindSense Simulation API",version="1.0.0",description="Software-only prototype. Telemetry and outcomes are estimates; no hardware is connected.")
origins=[x.strip() for x in os.getenv("GRINDSENSE_CORS_ORIGINS","http://localhost:5173").split(",")]
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_methods=["*"],allow_headers=["*"])
tasks={}
scenario_default={"scenario":"normal","seed":42}
TICK=max(.25,float(os.getenv("GRINDSENSE_TICK_SECONDS","1")))

class Create(BaseModel):
    task_type:str=Field(default="chutney",pattern="^(chutney|masala|batter|custom)$")
    ingredients:list[str]=Field(min_length=1,max_length=12)
    quantity:float=Field(default=250,gt=0,le=2000)
    added_water_ml:float=Field(default=0,ge=0,le=2000)
    preparation_type:str=Field(default="Wet preparation",pattern="^(Wet preparation|Dry grinding|Blending)$")
    jar_present:bool=True
    lid_locked:bool=True
    attachment_present:bool=True
    target_texture:str=Field(default="medium",pattern="^(coarse|medium|fine|smooth)$")
    smoothness_level:int=Field(default=50,ge=0,le=100)
    adaptive_mode:bool=True
    simulation_scenario:str=Field(default="normal",pattern="^(normal|high_load|high_temperature|high_vibration|overload)$")
    scenario_seed:int=42
class Scenario(BaseModel):
    scenario:str=Field(pattern="^(normal|high_load|high_temperature|high_vibration|overload)$")
    seed:int=42
class InterlockUpdate(BaseModel):
    jar_present:bool
    lid_locked:bool
    attachment_present:bool
def out(s):
    return {k:getattr(s,k) for k in ("id","task_type","ingredients","quantity","added_water_ml","preparation_type","jar_present","lid_locked","attachment_present","target_texture","smoothness_level","adaptive_mode","simulation_scenario","status","progress","started_at","completed_at","estimated_texture_score","result_summary")}
def get(db,sid):
    s=db.get(GrindSession,sid)
    if not s: raise HTTPException(404,"Session not found")
    return s
def add_event(db,s,kind,msg,severity="info",old=None,new=None):
    db.add(Event(session_id=s.id,event_type=kind,explanation=msg,severity=severity,previous_state=old,new_state=new))
def interlock_state(s):
    return {"jar_present":s.jar_present,"lid_locked":s.lid_locked,"attachment_present":s.attachment_present}
def unsafe_interlocks(s):
    labels={"jar_present":"Jar is not present","lid_locked":"Lid is not locked","attachment_present":"Attachment is not present"}
    return [labels[name] for name,value in interlock_state(s).items() if not value]
def interlock_explanation(reasons):
    return "Simulated safety interlock: " + "; ".join(reasons) + "."
def record_interlock_stop(db,s,reasons,previous_state=None):
    explanation=interlock_explanation(reasons) + " Grinding stopped safely."
    old=previous_state or interlock_state(s)
    s.status="safety_stopped";s.result_summary=explanation;s.completed_at=now()
    add_event(db,s,"safety",explanation,"critical",old={**old,"status":"running"},new={**interlock_state(s),"status":"safety_stopped"})
def block_interlock_start(db,s,reasons):
    explanation=interlock_explanation(reasons) + " Session start was blocked."
    state=interlock_state(s)
    add_event(db,s,"safety",explanation,"critical",old=state,new={**state,"start_allowed":False})
    db.commit()
    raise HTTPException(409,explanation)
def record_predictive_warnings(db,s,readings):
    """Record one predictive warning per metric until its simulated value recovers."""
    latest_state={}
    for event in s.events:
        if event.event_type not in ("predictive_warning","predictive_recovery") or not event.new_state:
            continue
        metric=event.new_state.get("metric")
        if metric in PREDICTIVE_THRESHOLDS:
            latest_state[metric]=event.new_state

    current=readings[-1]
    rearmed=set()
    for metric, state in latest_state.items():
        if state.get("status") != "active":
            continue
        reset_level=min(PREDICTIVE_THRESHOLDS[metric]) * (1 - PREDICTIVE_RESET_MARGIN)
        if current[metric] <= reset_level:
            explanation=(
                f"Simulated {metric.replace('_', ' ')} recovered below its predictive warning reset margin. "
                "A later rising trend may generate another predictive warning."
            )
            add_event(
                db, s, "predictive_recovery", explanation, "info",
                old=state, new={"metric": metric, "status": "recovered", "reset_level": reset_level},
            )
            rearmed.add(metric)

    for prediction in predictive_warnings(readings):
        if prediction.metric in rearmed:
            continue
        state=latest_state.get(prediction.metric)
        if state and state.get("status") == "active":
            reset_level=min(PREDICTIVE_THRESHOLDS[prediction.metric]) * (1 - PREDICTIVE_RESET_MARGIN)
            if current[prediction.metric] > reset_level:
                continue
        explanation=(
            f"PREDICTIVE WARNING: Simulated {prediction.metric.replace('_', ' ')} is rising "
            f"({prediction.slope_per_tick:.2f} units per simulation tick) and may approach "
            f"the configured threshold {prediction.threshold:g} in approximately "
            f"{prediction.estimated_ticks_to_threshold:.1f} ticks."
        )
        add_event(
            db, s, "predictive_warning", explanation, "warning",
            old={"metric": prediction.metric, "value": current[prediction.metric]},
            new={
                "metric": prediction.metric,
                "status": "active",
                "threshold": prediction.threshold,
                "slope_per_tick": round(prediction.slope_per_tick, 4),
                "estimated_ticks_to_threshold": round(prediction.estimated_ticks_to_threshold, 2),
            },
        )
def advance(db,s):
    reasons=unsafe_interlocks(s)
    if reasons:
        record_interlock_stop(db,s,reasons)
        return
    s.tick+=1; r=generate_reading(s); old={"speed_rpm":s.speed_rpm,"pulse_pattern":s.pulse_pattern,"intensity":s.intensity}
    if s.adaptive_mode:
        decision=adapt(s,r)
        s.speed_rpm=decision.speed_rpm;s.intensity=decision.intensity;s.pulse_pattern=decision.pulse_pattern
        if decision.explanation:add_event(db,s,"adaptive",decision.explanation,old=old,new={"speed_rpm":s.speed_rpm,"pulse_pattern":s.pulse_pattern,"intensity":s.intensity})
    previous_rows=(
        db.query(Telemetry)
        .filter_by(session_id=s.id)
        .order_by(Telemetry.id.desc())
        .limit(4)
        .all()
    )
    recent_readings=[
        {key:getattr(row,key) for key in ("motor_load","temperature","vibration","motor_current")}
        for row in reversed(previous_rows)
    ]
    recent_readings.append(r)
    db.add(Telemetry(session_id=s.id,**r));s.progress=r["progress"]
    record_predictive_warnings(db,s,recent_readings)
    for key,message in warning_reasons(r):
        if not any(e.event_type=="warning" and key in e.explanation.lower() for e in s.events):add_event(db,s,"warning",message,"warning")
    reason=safety_stop_reason(r)
    if reason:
        s.status="safety_stopped";s.result_summary=reason;s.completed_at=now();add_event(db,s,"safety",reason,"critical")
    elif texture_complete(s.target_texture,r["texture_index"]):
        s.status="completed";s.estimated_texture_score=r["texture_index"];s.result_summary="Estimated target outcome achieved in software simulation.";s.completed_at=now();add_event(db,s,"info",s.result_summary)
    elif s.tick>=180:
        s.status="completed";s.estimated_texture_score=r["texture_index"];s.result_summary="Simulation time limit reached; result is an estimate.";s.completed_at=now()
async def run(sid):
    while True:
        await asyncio.sleep(TICK);db=DB()
        try:
            s=db.get(GrindSession,sid)
            if not s or s.status!="running":return
            advance(db,s);db.commit()
            if s.status!="running":return
        finally:db.close()
@app.get("/api/health")
def health():return {"status":"ok","mode":"simulation","hardware_connected":False}
@app.post("/api/sessions",status_code=201)
def create(payload:Create):
    db=DB()
    try:
        values=payload.model_dump()
        if "simulation_scenario" not in payload.model_fields_set: values["simulation_scenario"]=scenario_default["scenario"]
        if "scenario_seed" not in payload.model_fields_set: values["scenario_seed"]=scenario_default["seed"]
        s=GrindSession(id=str(uuid.uuid4()),**values);db.add(s);db.commit();db.refresh(s);return out(s)
    finally:db.close()
@app.get("/api/sessions")
def history():
    db=DB()
    try:return [out(s) for s in db.query(GrindSession).order_by(GrindSession.created_at.desc()).all()]
    finally:db.close()
@app.get("/api/sessions/{sid}")
def session(sid:str):
    db=DB()
    try:return out(get(db,sid))
    finally:db.close()
@app.post("/api/sessions/{sid}/start")
async def start(sid:str):
    db=DB()
    try:
        s=get(db,sid)
        if s.status in ("completed","safety_stopped"):raise HTTPException(409,"Finished session cannot be restarted.")
        reasons=unsafe_interlocks(s)
        if reasons:block_interlock_start(db,s,reasons)
        if s.status!="running":
            s.status="running";s.started_at=s.started_at or now();db.commit()
            if sid not in tasks or tasks[sid].done():tasks[sid]=asyncio.create_task(run(sid))
        return out(s)
    finally:db.close()
@app.post("/api/sessions/{sid}/stop")
def stop(sid:str):
    db=DB()
    try:
        s=get(db,sid)
        if s.status=="running":
            s.status="stopped";s.completed_at=now();s.result_summary="Simulation stopped by user.";add_event(db,s,"info",s.result_summary);db.commit()
        return out(s)
    finally:db.close()
@app.get("/api/sessions/{sid}/telemetry")
def telemetry(sid:str):
    db=DB()
    try:get(db,sid);return [{k:getattr(r,k) for k in ("timestamp","motor_current","motor_load","temperature","vibration","motor_speed","texture_index","progress")} for r in db.query(Telemetry).filter_by(session_id=sid).order_by(Telemetry.id)]
    finally:db.close()
@app.get("/api/sessions/{sid}/events")
def events(sid:str):
    db=DB()
    try:get(db,sid);return [{k:getattr(e,k) for k in ("timestamp","event_type","previous_state","new_state","severity","explanation")} for e in db.query(Event).filter_by(session_id=sid).order_by(Event.id)]
    finally:db.close()
@app.get("/api/sessions/{sid}/results")
def results(sid:str):
    db=DB()
    try:
        s=get(db,sid);rows=db.query(Telemetry).filter_by(session_id=sid).order_by(Telemetry.id).all()
        return {**out(s),"duration_seconds":(s.completed_at.replace(tzinfo=timezone.utc)-s.started_at.replace(tzinfo=timezone.utc)).total_seconds() if s.completed_at and s.started_at else None,
          "max_motor_load":max((x.motor_load for x in rows),default=0),"max_temperature":max((x.temperature for x in rows),default=0),
          "adaptive_actions":db.query(Event).filter_by(session_id=sid,event_type="adaptive").count(),"telemetry":[{k:getattr(x,k) for k in ("timestamp","motor_current","motor_load","temperature","vibration","motor_speed","texture_index","progress")} for x in rows]}
    finally:db.close()
@app.post("/api/simulation/scenario")
def configure(p:Scenario):
    scenario_default.update(scenario=p.scenario,seed=p.seed)
    return {"scenario":p.scenario,"seed":p.seed,"note":"Applied as the default for sessions created without an explicit scenario."}

@app.post("/api/sessions/{sid}/pause")
async def pause(sid:str):
    db=DB()
    try:
        s=get(db,sid)
        if s.status=="running":
            task=tasks.get(sid)
            if task and not task.done(): task.cancel()
            s.status="paused"
            add_event(db,s,"info","Simulation paused by user.")
            db.commit()
        return out(s)
    finally: db.close()
@app.post("/api/sessions/{sid}/resume")
async def resume(sid:str):
    db=DB()
    try:
        s=get(db,sid)
        if s.status!="paused": raise HTTPException(409,"Only a paused session can be resumed.")
        reasons=unsafe_interlocks(s)
        if reasons:block_interlock_start(db,s,reasons)
        s.status="running"
        db.commit()
        tasks[sid]=asyncio.create_task(run(sid))
        return out(s)
    finally: db.close()

@app.post("/api/sessions/{sid}/interlocks")
async def update_interlocks(sid:str,payload:InterlockUpdate):
    db=DB()
    try:
        s=get(db,sid)
        if s.status in ("completed","safety_stopped","stopped"):
            raise HTTPException(409,"Finished session interlocks cannot be changed.")
        old=interlock_state(s)
        s.jar_present=payload.jar_present;s.lid_locked=payload.lid_locked;s.attachment_present=payload.attachment_present
        reasons=unsafe_interlocks(s)
        if reasons and s.status=="running":
            task=tasks.get(sid)
            if task and not task.done(): task.cancel()
            record_interlock_stop(db,s,reasons,previous_state=old)
        elif reasons:
            add_event(db,s,"warning",interlock_explanation(reasons)+" Session cannot start until all components are safe.","warning",old=old,new=interlock_state(s))
        else:
            add_event(db,s,"info","Simulated interlock states updated; all components are safe.",old=old,new=interlock_state(s))
        db.commit()
        return out(s)
    finally: db.close()

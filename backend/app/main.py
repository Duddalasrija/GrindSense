import asyncio, math, os, random, uuid
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, String, Float, Integer, Boolean, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

URL=os.getenv("GRINDSENSE_DATABASE_URL","sqlite:///./grindsense.db")
engine=create_engine(URL,connect_args={"check_same_thread":False} if URL.startswith("sqlite") else {})
DB=sessionmaker(bind=engine,expire_on_commit=False)
Base=declarative_base()
def now(): return datetime.now(timezone.utc)

class GrindSession(Base):
    __tablename__="grinding_sessions"
    id=Column(String,primary_key=True); task_type=Column(String); ingredients=Column(JSON); quantity=Column(Float)
    target_texture=Column(String); smoothness_level=Column(Integer); adaptive_mode=Column(Boolean,default=True)
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
app=FastAPI(title="GrindSense Simulation API",version="1.0.0",description="Software-only prototype. Telemetry and outcomes are estimates; no hardware is connected.")
origins=[x.strip() for x in os.getenv("GRINDSENSE_CORS_ORIGINS","http://localhost:5173").split(",")]
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_methods=["*"],allow_headers=["*"])
tasks={}
scenario_default={"scenario":"normal","seed":42}
TARGET={"coarse":28,"medium":52,"fine":76,"smooth":94}
WARN_LOAD,WARN_TEMP,WARN_VIBE=78,72,7
CRIT_LOAD,CRIT_TEMP,CRIT_VIBE,CRIT_CURRENT=96,88,11,11.5
TICK=max(.25,float(os.getenv("GRINDSENSE_TICK_SECONDS","1")))

class Create(BaseModel):
    task_type:str=Field(default="chutney",pattern="^(chutney|masala|batter|custom)$")
    ingredients:list[str]=Field(min_length=1,max_length=12)
    quantity:float=Field(default=250,gt=0,le=2000)
    target_texture:str=Field(default="medium",pattern="^(coarse|medium|fine|smooth)$")
    smoothness_level:int=Field(default=50,ge=0,le=100)
    adaptive_mode:bool=True
    simulation_scenario:str=Field(default="normal",pattern="^(normal|high_load|high_temperature|high_vibration|overload)$")
    scenario_seed:int=42
class Scenario(BaseModel):
    scenario:str=Field(pattern="^(normal|high_load|high_temperature|high_vibration|overload)$")
    seed:int=42
def out(s):
    return {k:getattr(s,k) for k in ("id","task_type","ingredients","quantity","target_texture","smoothness_level","adaptive_mode","simulation_scenario","status","progress","started_at","completed_at","estimated_texture_score","result_summary")}
def get(db,sid):
    s=db.get(GrindSession,sid)
    if not s: raise HTTPException(404,"Session not found")
    return s
def add_event(db,s,kind,msg,severity="info",old=None,new=None):
    db.add(Event(session_id=s.id,event_type=kind,explanation=msg,severity=severity,previous_state=old,new_state=new))
def generate(s):
    rng=random.Random(s.scenario_seed+s.tick*7919)
    task={"chutney":1,"masala":.92,"batter":.85,"custom":.95}.get(s.task_type,.95)
    ingredients={"coconut":1.12,"chilli":1,"spices":.9,"lentils":1.14}
    fac=task*sum(ingredients.get(i.lower(),1) for i in s.ingredients)/len(s.ingredients)
    load=38+fac*14+math.sin(s.tick/5)*2.4+s.intensity*8+rng.uniform(-1.2,1.2)
    temp=28+s.tick*(.22+s.intensity*.13)+max(0,load-60)*.12
    vibe=2.1+abs(math.sin(s.tick/3))*1.1+max(0,load-65)*.07
    if s.simulation_scenario=="high_load": load+=min(32,s.tick*1.3)
    if s.simulation_scenario=="high_temperature": temp+=s.tick*.43
    if s.simulation_scenario=="high_vibration": vibe+=min(9.5,s.tick*.38)
    if s.simulation_scenario=="overload": load+=min(65,s.tick*2.7)
    load=max(8,min(110,load))
    progress=min(100,s.progress+(.60+s.intensity*.8)*(1.08 if s.simulation_scenario=="normal" else .85)*fac)
    texture=min(100,progress*(.72+s.smoothness_level/250)*min(1.12,fac))
    return dict(motor_current=round(1.2+load*.082+rng.uniform(-.1,.1),2),motor_load=round(load,1),temperature=round(temp,1),vibration=round(vibe,1),
      motor_speed=round(max(300,s.speed_rpm*s.intensity+rng.uniform(-12,12))),texture_index=round(texture,1),progress=round(progress,1))
def advance(db,s):
    s.tick+=1; r=generate(s); old={"speed_rpm":s.speed_rpm,"pulse_pattern":s.pulse_pattern,"intensity":s.intensity}; msg=None
    if s.adaptive_mode:
        if r["temperature"]>=WARN_TEMP and s.intensity>.52:
            s.intensity=.48;s.speed_rpm=max(420,s.speed_rpm-120);s.pulse_pattern="2s on / 2s rest";msg="Temperature rising. Reducing simulated intensity and extending rest pulses."
        elif r["motor_load"]>=WARN_LOAD and s.intensity>.45:
            s.intensity=.43;s.speed_rpm=max(420,s.speed_rpm-150);s.pulse_pattern="2s on / 2s rest";msg="High grinding resistance detected. Adjusting simulated speed and pulse pattern."
        elif r["vibration"]>=WARN_VIBE and s.intensity>.4:
            s.intensity=.38;s.pulse_pattern="1s on / 2s rest";msg="Elevated simulated vibration detected. Using shorter pulses."
        elif r["motor_load"]<62 and s.progress<70 and s.intensity<.82:
            s.intensity=min(.82,s.intensity+.04);msg="Load is stable and texture progress is low. Gradually increasing simulated intensity."
        if msg:add_event(db,s,"adaptive",msg,old=old,new={"speed_rpm":s.speed_rpm,"pulse_pattern":s.pulse_pattern,"intensity":s.intensity})
    db.add(Telemetry(session_id=s.id,**r));s.progress=r["progress"]
    if r["temperature"]>=WARN_TEMP and not any(e.event_type=="warning" and "temperature" in e.explanation for e in s.events):add_event(db,s,"warning","Simulated temperature warning; demo threshold only.","warning")
    if r["vibration"]>=WARN_VIBE and not any(e.event_type=="warning" and "vibration" in e.explanation for e in s.events):add_event(db,s,"warning","Simulated vibration warning; demo threshold only.","warning")
    reason=("Critical simulated temperature threshold reached; session stopped safely." if r["temperature"]>=CRIT_TEMP else
      "Critical simulated vibration threshold reached; session stopped safely." if r["vibration"]>=CRIT_VIBE else
      "Simulated overload condition detected; session stopped safely." if r["motor_load"]>=CRIT_LOAD or r["motor_current"]>=CRIT_CURRENT else None)
    if reason:
        s.status="safety_stopped";s.result_summary=reason;s.completed_at=now();add_event(db,s,"safety",reason,"critical")
    elif r["texture_index"]>=TARGET[s.target_texture]:
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

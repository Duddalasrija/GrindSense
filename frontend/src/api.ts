export type Session={id:string;task_type:string;ingredients:string[];quantity:number;added_water_ml:number;preparation_type:string;jar_present:boolean;lid_locked:boolean;attachment_present:boolean;target_texture:string;smoothness_level:number;adaptive_mode:boolean;simulation_scenario:string;status:string;progress:number;started_at:string|null;completed_at:string|null;estimated_texture_score:number|null;result_summary:string|null};
export type InterlockState=Pick<Session,"jar_present"|"lid_locked"|"attachment_present">;
export type Reading={timestamp:string;motor_current:number;motor_load:number;temperature:number;vibration:number;acoustic_signature_index?:number;torque_demand_index?:number;motor_speed:number;texture_index:number;progress:number};
export type Event={timestamp:string;event_type:string;previous_state:Record<string,unknown>|null;new_state:Record<string,unknown>|null;severity?:string|null;explanation:string};
export type Results=Session&{duration_seconds:number|null;max_motor_load:number;max_temperature:number;max_acoustic_signature_index?:number;max_torque_demand_index?:number;adaptive_actions:number;telemetry:Reading[]};
const BASE=(import.meta.env.VITE_API_URL||"http://localhost:8000").replace(/\/$/,"");
async function request<T>(path:string,init?:RequestInit):Promise<T>{const r=await fetch(BASE+path,{...init,headers:{"Content-Type":"application/json",...init?.headers}});if(!r.ok){const e=await r.json().catch(()=>null);throw Error(e?.detail||`API error (${r.status})`)}return r.json()}
export const api={
 health:()=>request<{status:string;mode:string;hardware_connected:boolean}>("/api/health"),
 history:()=>request<Session[]>("/api/sessions"),
 create:(payload:Record<string,unknown>)=>request<Session>("/api/sessions",{method:"POST",body:JSON.stringify(payload)}),
 start:(id:string)=>request<Session>(`/api/sessions/${id}/start`,{method:"POST"}),
 pause:(id:string)=>request<Session>(`/api/sessions/${id}/pause`,{method:"POST"}),
 resume:(id:string)=>request<Session>(`/api/sessions/${id}/resume`,{method:"POST"}),
 stop:(id:string)=>request<Session>(`/api/sessions/${id}/stop`,{method:"POST"}),
 updateInterlocks:(id:string,state:InterlockState)=>request<Session>(`/api/sessions/${id}/interlocks`,{method:"POST",body:JSON.stringify(state)}),
 session:(id:string)=>request<Session>(`/api/sessions/${id}`),
 telemetry:(id:string)=>request<Reading[]>(`/api/sessions/${id}/telemetry`),
 events:(id:string)=>request<Event[]>(`/api/sessions/${id}/events`),
 results:(id:string)=>request<Results>(`/api/sessions/${id}/results`)
};


export interface User {id:number;email:string;display_name:string}
export interface Course {id:number;title:string;institution:string|null;archived:boolean}
export interface Assignment {id:number;course_id:number;title:string;due_at:string;notes:string|null;estimated_minutes:number|null;completed:boolean}
export interface AuthResponse {token:string;user:User}
export const SESSION_KEY='weekwise_session';
export async function api<T>(path:string, token:string|null, method='GET', data?:unknown):Promise<T> {
  const response=await fetch('/api'+path,{method,headers:{...(token?{'Authorization':'Bearer '+token}:{}),...(data!==undefined?{'Content-Type':'application/json'}:{})},body:data===undefined?undefined:JSON.stringify(data)});
  if(!response.ok){ const payload=await response.json().catch(()=>({})); throw new Error(typeof payload.detail==='string'?payload.detail:`Request failed (${response.status})`); }
  return response.json() as Promise<T>;
}

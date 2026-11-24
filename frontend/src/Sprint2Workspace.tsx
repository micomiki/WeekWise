import {useCallback,useEffect,useMemo,useState,type FormEvent} from 'react';
import {CalendarDays, ChevronLeft, ChevronRight, Clock3, Plus, Trash2, Pencil, AlertTriangle} from 'lucide-react';
import {api,type Assignment} from './api';
import './sprint2.css';

type Task={id:number;assignment_id:number;title:string;estimated_minutes:number|null;sort_order:number;completed:boolean;depends_on_ids:number[]};
type Allocation={id:number;task_id:number;day:string;minutes:number};
type Day={day:string;available_minutes:number|null;planned_minutes:number;overload_minutes:number|null};
type Week={start:string;days:Day[]};
const iso=(d:Date)=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
const monday=(date:Date)=>{const d=new Date(date.getFullYear(),date.getMonth(),date.getDate());d.setDate(d.getDate()-(d.getDay()+6)%7);return d};
const shift=(date:string,delta:number)=>{const [y,m,d]=date.split('-').map(Number);const v=new Date(y,m-1,d);v.setDate(v.getDate()+delta);return iso(v)};
const label=(day:string)=>new Date(day+'T12:00:00').toLocaleDateString(undefined,{weekday:'short',month:'short',day:'numeric'});
const h=(minutes:number)=>`${(minutes/60).toFixed(minutes%60?1:0)}h`;
export default function Sprint2Workspace({token,assignments,view}:{token:string;assignments:Assignment[];view:'tasks'|'planner'}){
 const [tasks,setTasks]=useState<Task[]>([]);const [allocations,setAllocations]=useState<Allocation[]>([]);
 const [start,setStart]=useState(()=>iso(monday(new Date())));const [week,setWeek]=useState<Week|null>(null);
 const [error,setError]=useState('');const [notice,setNotice]=useState('');const [busy,setBusy]=useState(false);
 const [assignmentId,setAssignmentId]=useState<number|null>(null);const [taskTitle,setTaskTitle]=useState('');const [effort,setEffort]=useState('');
 const [dependencies,setDependencies]=useState<number[]>([]);const [editTask,setEditTask]=useState<Task|null>(null);const [chosenTask,setChosenTask]=useState('');const [chosenDay,setChosenDay]=useState(()=>iso(new Date()));const [duration,setDuration]=useState('60');
 const [dayEdit,setDayEdit]=useState<string|null>(null);const [capacity,setCapacity]=useState('');
 const load=useCallback(async()=>{try{
   const [ts, al, wk]=await Promise.all([api<Task[]>('/planning/tasks',token),api<Allocation[]>(`/planning/allocations?start=${start}&end=${shift(start,6)}`,token),api<Week>(`/planning/week?start=${start}`,token)]);
   setTasks(ts);setAllocations(al);setWeek(wk);setError('');
 }catch(e){setError((e as Error).message)}},[token,start]);
 useEffect(()=>{void load()},[load]);
 const remaining=useMemo(()=>tasks.filter(t=>!t.completed),[tasks]);
 async function action(run:()=>Promise<unknown>,success:string){setBusy(true);setError('');try{await run();await load();setNotice(success);window.setTimeout(()=>setNotice(''),3500)}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 async function saveTask(e:FormEvent){e.preventDefault();if(!assignmentId&&!editTask)return;const body={title:taskTitle.trim(),estimated_minutes:effort===''?null:Number(effort),depends_on_ids:dependencies};
   await action(()=>editTask?api(`/planning/tasks/${editTask.id}`,token,'PATCH',body):api('/planning/tasks',token,'POST',{...body,assignment_id:assignmentId}),'Task saved');setTaskTitle('');setEffort('');setDependencies([]);setEditTask(null)}
 function beginEdit(t:Task){setEditTask(t);setTaskTitle(t.title);setEffort(t.estimated_minutes===null?'':String(t.estimated_minutes));setAssignmentId(t.assignment_id);setDependencies(t.depends_on_ids||[])}
 async function createAllocation(e:FormEvent){e.preventDefault();if(!chosenTask)return;
   await action(()=>api('/planning/allocations',token,'POST',{task_id:Number(chosenTask),day:chosenDay,minutes:Number(duration)}),'Study time scheduled')}
 async function saveCapacity(e:FormEvent){e.preventDefault();if(!dayEdit)return;
   await action(()=>capacity===''?api(`/planning/availability/${dayEdit}`,token,'DELETE'):api('/planning/availability',token,'PUT',{day:dayEdit,minutes:Math.round(Number(capacity)*60)}),'Availability saved');setDayEdit(null)}
 return <section className="ww2-root" aria-label={view==='tasks'?'Assignment tasks':'Weekly planner'}>
 {error&&<div className="ww2-error" role="alert">{error}</div>}{notice&&<div className="ww2-ok" role="status">{notice}</div>}
 {view==='tasks'?<>
  <div className="ww2-header"><div><span className="eyebrow purple">MY WORK</span><h2>Break it down. Move forward.</h2><p className="muted">Turn each assignment into small, manageable steps. Your progress is saved.</p></div></div>
  <form className="ww2-form" onSubmit={saveTask}>
   <label>Assignment<select required value={assignmentId??''} disabled={!!editTask} onChange={e=>{setAssignmentId(Number(e.target.value));setDependencies([])}}><option value="" disabled>Select an assignment</option>{assignments.map(a=><option key={a.id} value={a.id}>{a.title}</option>)}</select></label>
   <label>Task<input required maxLength={180} placeholder="e.g. Review requirements" value={taskTitle} onChange={e=>setTaskTitle(e.target.value)}/></label>
   <label>Effort (minutes, optional)<input type="number" min="0" value={effort} onChange={e=>setEffort(e.target.value)} placeholder="Unknown"/></label>
   <fieldset className="ww-dep-fieldset"><legend>Depends on (optional)</legend><p>Select tasks that must be finished before this task can start.</p>{tasks.filter(t=>t.assignment_id===assignmentId&&t.id!==editTask?.id).length===0?<small>No other tasks in this assignment yet.</small>:<div className="ww-dep-options">{tasks.filter(t=>t.assignment_id===assignmentId&&t.id!==editTask?.id).map(t=><label key={t.id}><input type="checkbox" checked={dependencies.includes(t.id)} onChange={e=>setDependencies(current=>e.target.checked?[...current,t.id]:current.filter(id=>id!==t.id))}/>{t.title}</label>)}</div>}</fieldset>
   <div className="ww2-actions"><button className="btn primary" disabled={busy||!taskTitle.trim()||!assignmentId} type="submit"><Plus size={16}/>{editTask?'Save task':'Add task'}</button>{editTask&&<button className="btn outline" type="button" onClick={()=>{setEditTask(null);setTaskTitle('');setEffort('');setDependencies([])}}>Cancel edit</button>}</div>
  </form>
  {assignments.map(a=>{const items=tasks.filter(t=>t.assignment_id===a.id);const completed=items.filter(t=>t.completed).length;return <article key={a.id} className="ww2-group"><div className="ww2-group-head"><div><h3>{a.title}</h3><p>{items.length?`${completed} of ${items.length} tasks completed`:'No tasks yet — add your first step above'}</p></div><strong>{items.length?Math.round(100*completed/items.length):0}%</strong></div><div className="ww2-progress"><div style={{width:`${items.length?100*completed/items.length:0}%`}}/></div>
   {items.map((t,index)=><div className="ww2-task" key={t.id}><label className="ww2-tick"><input type="checkbox" checked={t.completed} onChange={()=>void action(()=>api(`/planning/tasks/${t.id}`,token,'PATCH',{completed:!t.completed}),'Progress updated')}/><span className={t.completed?'ww2-done':''}>{t.title}</span></label><small>{t.estimated_minutes===null?'Effort unknown':h(t.estimated_minutes)}{t.depends_on_ids?.length?` · Depends on: ${t.depends_on_ids.map(id=>tasks.find(x=>x.id===id)?.title||'Task').join(', ')}`:''}</small><div className="ww2-task-actions"><button type="button" title="Move earlier" aria-label={`Move ${t.title} earlier`} disabled={index===0||busy} onClick={()=>void action(async()=>{const previous=items[index-1];await api(`/planning/tasks/${t.id}`,token,'PATCH',{sort_order:previous.sort_order});await api(`/planning/tasks/${previous.id}`,token,'PATCH',{sort_order:t.sort_order})},'Task reordered')}>↑</button><button type="button" title="Move later" aria-label={`Move ${t.title} later`} disabled={index===items.length-1||busy} onClick={()=>void action(async()=>{const next=items[index+1];await api(`/planning/tasks/${t.id}`,token,'PATCH',{sort_order:next.sort_order});await api(`/planning/tasks/${next.id}`,token,'PATCH',{sort_order:t.sort_order})},'Task reordered')}>↓</button><button type="button" title="Edit" aria-label={`Edit ${t.title}`} onClick={()=>beginEdit(t)}><Pencil size={15}/></button><button type="button" title="Delete" aria-label={`Delete ${t.title}`} onClick={()=>{if(window.confirm(`Delete task “${t.title}” and its planned hours?`))void action(()=>api(`/planning/tasks/${t.id}`,token,'DELETE'),'Task deleted')}}><Trash2 size={15}/></button></div></div>)}
  </article>})}
  {!assignments.length&&<div className="ww2-empty">Create an assignment in My Work to begin planning tasks.</div>}
 </>:<>
  <div className="ww2-header"><div><span className="eyebrow purple">YOUR WEEK</span><h2>Make your week work for you.</h2><p className="muted">Set your available hours, schedule tasks, and spot busy days before they become stressful.</p></div><div className="ww2-week-nav"><button className="btn outline" aria-label="Previous week" onClick={()=>setStart(v=>shift(v,-7))}><ChevronLeft size={17}/></button><strong>{label(start)} – {label(shift(start,6))}</strong><button className="btn outline" aria-label="Next week" onClick={()=>setStart(v=>shift(v,7))}><ChevronRight size={17}/></button></div></div>
  <div className="ww2-week-grid">{week?.days.map(d=><article className="ww2-day" key={d.day}><div className="ww2-day-title"><strong>{label(d.day)}</strong>{d.overload_minutes!==null&&d.overload_minutes>0?<AlertTriangle size={17} aria-label="Overloaded"/>:null}</div><div className="ww2-metric">{h(d.planned_minutes)} <small>planned</small></div><p>{d.available_minutes===null?'Availability unknown':`${h(d.available_minutes)} available`}</p><div className="ww2-bar"><div className={d.overload_minutes!==null&&d.overload_minutes>0?'over':''} style={{width:`${d.available_minutes===null?0:d.available_minutes===0?(d.planned_minutes>0?100:0):Math.min(100,100*d.planned_minutes/d.available_minutes)}%`}}/></div>{d.overload_minutes!==null&&d.overload_minutes>0?<small className="ww2-warn">{h(d.overload_minutes)} over capacity</small>:null}
   <button className="ww2-link" onClick={()=>{setDayEdit(d.day);setCapacity(d.available_minutes===null?'':String(d.available_minutes/60))}}>Edit availability</button>{allocations.filter(a=>a.day===d.day).map(a=><div className="ww2-allocation" key={a.id}><span>{tasks.find(t=>t.id===a.task_id)?.title||'Task'} · {h(a.minutes)}</span><button title="Remove planned time" aria-label="Remove planned time" onClick={()=>void action(()=>api(`/planning/allocations/${a.id}`,token,'DELETE'),'Planned time removed')}><Trash2 size={13}/></button></div>)}
  </article>)}</div>
  {dayEdit&&<form className="ww2-form ww2-capacity" onSubmit={saveCapacity}><label>Available study hours for {label(dayEdit)} <span className="muted">(blank = unknown, 0 = unavailable)</span><input type="number" min="0" max="24" step="0.25" value={capacity} onChange={e=>setCapacity(e.target.value)} placeholder="Unknown" autoFocus/></label><div className="ww2-actions"><button type="submit" className="btn primary">Save availability</button><button type="button" className="btn outline" onClick={()=>setDayEdit(null)}>Cancel</button></div></form>}
  <form className="ww2-form" onSubmit={createAllocation}><h3><CalendarDays size={19}/> Schedule study time</h3><label>Unfinished task<select required value={chosenTask} onChange={e=>setChosenTask(e.target.value)}><option value="">Choose task</option>{remaining.map(t=><option key={t.id} value={t.id}>{t.title}</option>)}</select></label><label>Day<input required type="date" value={chosenDay} onChange={e=>setChosenDay(e.target.value)}/></label><label>Planned minutes<input type="number" required min="1" max="1440" value={duration} onChange={e=>setDuration(e.target.value)}/></label><div className="ww2-actions"><button className="btn primary" disabled={!chosenTask||busy} type="submit"><Plus size={16}/> Plan task</button></div></form>
  {!remaining.length&&<p className="muted">Add an unfinished task in My Work before scheduling study time.</p>}
  <p className="ww2-note"><Clock3 size={16}/> Overloaded plans are shown as warnings; Weekwise never changes your schedule automatically. Missing availability is not zero hours.</p>
 </>}
 </section>
}

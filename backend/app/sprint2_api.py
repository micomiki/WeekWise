"""Sprint 2: student-owned task breakdown, daily capacity, and weekly planning."""
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .auth import current_user
from .database import get_db
from .models import User, Assignment
from .sprint2_models import StudyTask, StudyAvailability, StudyAllocation, StudyTaskDependency

router = APIRouter(prefix='/api/planning', tags=['Weekwise planning'])

class TaskInput(BaseModel):
    assignment_id: int
    title: str = Field(min_length=1, max_length=180)
    estimated_minutes: int | None = Field(default=None, ge=0)
    depends_on_ids: list[int] = Field(default_factory=list)
    @field_validator('title')
    @classmethod
    def nonempty(cls, value):
        if not value.strip(): raise ValueError('Task title is required')
        return value.strip()

class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=180)
    estimated_minutes: int | None = Field(default=None, ge=0)
    completed: bool | None = None
    sort_order: int | None = Field(default=None, ge=0)
    depends_on_ids: list[int] | None = None
    @field_validator('title')
    @classmethod
    def nonempty(cls, value):
        if value is not None and not value.strip(): raise ValueError('Task title is required')
        return value.strip() if value is not None else value

class AvailabilityInput(BaseModel):
    day: date
    minutes: int = Field(ge=0, le=1440)

class AllocationInput(BaseModel):
    task_id: int
    day: date
    minutes: int = Field(gt=0, le=1440)

class AllocationUpdate(BaseModel):
    day: date | None = None
    minutes: int | None = Field(default=None, gt=0, le=1440)

def task_json(task, db):
    ids = db.scalars(select(StudyTaskDependency.prerequisite_id).where(StudyTaskDependency.task_id == task.id, StudyTaskDependency.user_id == task.user_id).order_by(StudyTaskDependency.prerequisite_id)).all()
    return {'id':task.id,'assignment_id':task.assignment_id,'title':task.title,
            'estimated_minutes':task.estimated_minutes,'sort_order':task.sort_order,
            'completed':task.completed,'depends_on_ids':ids}

def validate_dependencies(db, user_id: int, assignment_id: int, task_id: int | None, ids: list[int]):
    if len(ids) != len(set(ids)):
        raise HTTPException(422, 'Duplicate prerequisites are not allowed')
    if task_id is not None and task_id in ids:
        raise HTTPException(422, 'A task cannot depend on itself')
    if ids:
        found = db.scalars(select(StudyTask).where(StudyTask.id.in_(ids), StudyTask.user_id == user_id, StudyTask.assignment_id == assignment_id)).all()
        if len(found) != len(ids):
            raise HTTPException(422, 'Prerequisites must belong to your same assignment')
    if task_id is None:
        return
    edges = db.scalars(select(StudyTaskDependency).where(StudyTaskDependency.user_id == user_id)).all()
    graph: dict[int, list[int]] = {}
    for edge in edges:
        if edge.task_id != task_id:
            graph.setdefault(edge.task_id, []).append(edge.prerequisite_id)
    graph[task_id] = ids
    def visits(node: int, seen: set[int]) -> bool:
        if node == task_id:
            return True
        if node in seen:
            return False
        return any(visits(other, seen | {node}) for other in graph.get(node, []))
    if any(visits(pre, set()) for pre in ids):
        raise HTTPException(422, 'Circular task dependencies are not allowed')

def replace_dependencies(db, user_id: int, task: StudyTask, ids: list[int]):
    validate_dependencies(db, user_id, task.assignment_id, task.id, ids)
    db.query(StudyTaskDependency).filter(StudyTaskDependency.user_id == user_id, StudyTaskDependency.task_id == task.id).delete(synchronize_session=False)
    db.add_all(StudyTaskDependency(user_id=user_id, task_id=task.id, prerequisite_id=pre) for pre in ids)


def alloc_json(item):
    return {'id':item.id,'task_id':item.task_id,'day':item.day.isoformat(),'minutes':item.minutes}

def get_task(db, user_id, task_id):
    task=db.scalar(select(StudyTask).where(StudyTask.id==task_id,StudyTask.user_id==user_id))
    if task is None:raise HTTPException(404,'Task not found')
    return task

@router.get('/tasks')
def tasks(user:User=Depends(current_user), db:Session=Depends(get_db)):
    records=db.scalars(select(StudyTask).where(StudyTask.user_id==user.id).order_by(StudyTask.assignment_id,StudyTask.sort_order,StudyTask.id)).all()
    return [task_json(t, db) for t in records]

@router.post('/tasks',status_code=201)
def add_task(data:TaskInput,user:User=Depends(current_user),db:Session=Depends(get_db)):
    assignment=db.scalar(select(Assignment).where(Assignment.id==data.assignment_id,Assignment.user_id==user.id))
    if not assignment:raise HTTPException(404,'Assignment not found')
    last=db.scalar(select(func.max(StudyTask.sort_order)).where(StudyTask.user_id==user.id,StudyTask.assignment_id==data.assignment_id))
    body=data.model_dump(exclude={'depends_on_ids'})
    validate_dependencies(db,user.id,data.assignment_id,None,data.depends_on_ids)
    task=StudyTask(user_id=user.id,sort_order=(last if last is not None else -1)+1,**body)
    db.add(task);db.flush()
    replace_dependencies(db,user.id,task,data.depends_on_ids)
    db.commit();db.refresh(task)
    return task_json(task,db)

@router.patch('/tasks/{task_id}')
def edit_task(task_id:int,data:TaskUpdate,user:User=Depends(current_user),db:Session=Depends(get_db)):
    task=get_task(db,user.id,task_id)
    body=data.model_dump(exclude_unset=True,exclude={'depends_on_ids'})
    for key,value in body.items():setattr(task,key,value)
    if 'depends_on_ids' in data.model_fields_set:
        replace_dependencies(db,user.id,task,data.depends_on_ids or [])
    db.commit();db.refresh(task)
    return task_json(task,db)

@router.delete('/tasks/{task_id}')
def delete_task(task_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    task=get_task(db,user.id,task_id)
    db.query(StudyAllocation).filter(StudyAllocation.user_id==user.id,StudyAllocation.task_id==task.id).delete(synchronize_session=False)
    db.query(StudyTaskDependency).filter(StudyTaskDependency.user_id==user.id,
        (StudyTaskDependency.task_id==task.id) | (StudyTaskDependency.prerequisite_id==task.id)).delete(synchronize_session=False)
    db.delete(task);db.commit()
    return {'deleted':True}

@router.get('/availability')
def availability(start:date,end:date,user:User=Depends(current_user),db:Session=Depends(get_db)):
    if end<start or (end-start).days>62:raise HTTPException(422,'Invalid date range')
    return [{'day':a.day.isoformat(),'minutes':a.minutes} for a in db.scalars(select(StudyAvailability).where(StudyAvailability.user_id==user.id,StudyAvailability.day>=start,StudyAvailability.day<=end).order_by(StudyAvailability.day))]

@router.put('/availability')
def set_availability(data:AvailabilityInput,user:User=Depends(current_user),db:Session=Depends(get_db)):
    a=db.scalar(select(StudyAvailability).where(StudyAvailability.user_id==user.id,StudyAvailability.day==data.day))
    if not a: a=StudyAvailability(user_id=user.id, day=data.day, minutes=data.minutes);db.add(a)
    else:a.minutes=data.minutes
    db.commit()
    return {'day':data.day.isoformat(),'minutes':data.minutes}

@router.delete('/availability/{day}')
def clear_availability(day:date,user:User=Depends(current_user),db:Session=Depends(get_db)):
    db.query(StudyAvailability).filter(StudyAvailability.user_id==user.id,StudyAvailability.day==day).delete(synchronize_session=False)
    db.commit()
    return {'deleted':True}

@router.get('/allocations')
def allocations(start:date,end:date,user:User=Depends(current_user),db:Session=Depends(get_db)):
    if end<start or (end-start).days>62:raise HTTPException(422,'Invalid date range')
    return [alloc_json(a) for a in db.scalars(select(StudyAllocation).where(StudyAllocation.user_id==user.id,StudyAllocation.day>=start,StudyAllocation.day<=end).order_by(StudyAllocation.day,StudyAllocation.id))]

@router.post('/allocations',status_code=201)
def add_allocation(data:AllocationInput,user:User=Depends(current_user),db:Session=Depends(get_db)):
    task=get_task(db,user.id,data.task_id)
    if task.completed:raise HTTPException(409,'Reopen the task before scheduling work')
    item=StudyAllocation(user_id=user.id,**data.model_dump())
    db.add(item);db.commit();db.refresh(item)
    return alloc_json(item)

@router.patch('/allocations/{allocation_id}')
def edit_allocation(allocation_id:int,data:AllocationUpdate,user:User=Depends(current_user),db:Session=Depends(get_db)):
    item=db.scalar(select(StudyAllocation).where(StudyAllocation.id==allocation_id,StudyAllocation.user_id==user.id))
    if not item:raise HTTPException(404,'Allocation not found')
    for key,value in data.model_dump(exclude_unset=True).items():setattr(item,key,value)
    db.commit();db.refresh(item)
    return alloc_json(item)

@router.delete('/allocations/{allocation_id}')
def delete_allocation(allocation_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    item=db.scalar(select(StudyAllocation).where(StudyAllocation.id==allocation_id,StudyAllocation.user_id==user.id))
    if not item:raise HTTPException(404,'Allocation not found')
    db.delete(item);db.commit()
    return {'deleted':True}

@router.get('/week')
def week(start:date,user:User=Depends(current_user),db:Session=Depends(get_db)):
    """Date-only summaries: missing capacity stays null, never interpreted as zero."""
    if start.weekday()!=0:raise HTTPException(422,'Week start must be Monday')
    end=start+timedelta(days=6)
    capacities={a.day:a.minutes for a in db.scalars(select(StudyAvailability).where(StudyAvailability.user_id==user.id,StudyAvailability.day>=start,StudyAvailability.day<=end))}
    allocations=list(db.scalars(select(StudyAllocation).where(StudyAllocation.user_id==user.id,StudyAllocation.day>=start,StudyAllocation.day<=end)))
    rows=[]
    for index in range(7):
        day=start+timedelta(days=index)
        planned=sum(item.minutes for item in allocations if item.day==day)
        capacity=capacities.get(day)
        rows.append({'day':day.isoformat(),'planned_minutes':planned,'available_minutes':capacity,'overload_minutes':max(0,planned-capacity) if capacity is not None else None})
    return {'start':start.isoformat(),'days':rows}

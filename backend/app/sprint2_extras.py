"""US-11 deterministic guidance and US-12 transactional private data backup."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError, ConfigDict, model_validator
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from .auth import current_user
from .database import get_db
from .models import User, Course, Assignment
from .sprint2_models import StudyTask, StudyAvailability, StudyAllocation, StudyTaskDependency

router = APIRouter(prefix='/api/weekwise', tags=['Weekwise guidance and safety'])
VERSION = 1
MAX_RECORDS = 5000

def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

@router.get('/suggestions')
def suggestions(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Prioritize assignments by due date; within each assignment choose an actionable task by manual order."""
    now = datetime.now(timezone.utc)
    assignments = {a.id:a for a in db.scalars(select(Assignment).where(Assignment.user_id==user.id))}
    tasks = db.scalars(select(StudyTask).where(StudyTask.user_id==user.id)).all()
    by_id={t.id:t for t in tasks}
    edges=db.scalars(select(StudyTaskDependency).where(StudyTaskDependency.user_id==user.id)).all()
    prerequisites:dict[int,list[int]]={}
    for edge in edges: prerequisites.setdefault(edge.task_id, []).append(edge.prerequisite_id)
    actionable=[]; blocked=[]
    for t in tasks:
        assignment=assignments.get(t.assignment_id)
        if not assignment or assignment.completed or t.completed: continue
        due=aware(assignment.due_at)
        days=(due-now).total_seconds()/86400
        if days < 0: timing='overdue'; why='This assignment is overdue.'
        elif days <= 2: timing='due_soon'; why='This assignment is due within 48 hours.'
        else: timing='upcoming'; why='This assignment has an upcoming deadline.'
        waiting=[by_id[pid].title for pid in prerequisites.get(t.id,[]) if pid in by_id and not by_id[pid].completed]
        ready=not waiting
        effort=(' Estimated effort: '+str(t.estimated_minutes)+' minutes.' if t.estimated_minutes is not None else ' Estimated effort is unknown.')
        reason=why+(' All prerequisites are complete.' if prerequisites.get(t.id) and ready else ' This task has no prerequisites.' if ready else ' Waiting for: '+', '.join(waiting)+'.')+effort
        item={'task_id':t.id,'task_title':t.title,'assignment_id':assignment.id,'assignment_title':assignment.title,
              'due_at':due.isoformat(),'estimated_minutes':t.estimated_minutes,'timing':timing,'reason':reason,
              'sort_order':t.sort_order,'ready':ready,'blocked_by':waiting}
        (actionable if ready else blocked).append(item)
    key=lambda x:(x['due_at'],x['sort_order'],x['task_id'])
    actionable.sort(key=key);blocked.sort(key=key)
    return {'items':actionable+blocked,'suggested':actionable[0] if actionable else None,
            'method':'Assignments are ordered by deadline. Within each assignment, only tasks with completed prerequisites are recommended, following your task order. Blocked tasks are shown separately. Estimates do not reorder tasks.'}

class BackupCourse(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: int = Field(gt=0)
    title: str = Field(min_length=1,max_length=160)
    institution: str | None = Field(default=None,max_length=160)
    color: str = Field(default='#6e6cf0',min_length=1,max_length=20)
    archived: bool = False

class BackupAssignment(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: int = Field(gt=0)
    course_id: int = Field(gt=0)
    title: str = Field(min_length=1,max_length=180)
    notes: str | None = None
    due_at: datetime
    estimated_minutes: int | None = Field(default=None,ge=0)
    completed: bool = False

class BackupTask(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: int = Field(gt=0)
    assignment_id: int = Field(gt=0)
    title: str = Field(min_length=1,max_length=180)
    estimated_minutes: int | None = Field(default=None,ge=0)
    sort_order: int = Field(ge=0)
    completed: bool = False
    depends_on_ids: list[int] = Field(default_factory=list)

class BackupAvailability(BaseModel):
    model_config = ConfigDict(extra='forbid')
    day: __import__('datetime').date
    minutes: int = Field(ge=0,le=1440)

class BackupAllocation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    task_id: int = Field(gt=0)
    day: __import__('datetime').date
    minutes: int = Field(gt=0,le=1440)

class Backup(BaseModel):
    model_config = ConfigDict(extra='forbid')
    format: str
    version: int
    courses: list[BackupCourse]
    assignments: list[BackupAssignment]
    tasks: list[BackupTask]
    availability: list[BackupAvailability]
    allocations: list[BackupAllocation]
    @model_validator(mode='after')
    def relationships(self):
        if self.format != 'weekwise-backup' or self.version != VERSION:
            raise ValueError('Unsupported backup format/version')
        groups = [self.courses,self.assignments,self.tasks,self.availability,self.allocations]
        if sum(map(len,groups))>MAX_RECORDS: raise ValueError('Backup exceeds 5000 records')
        for group in groups[:3]:
            ids=[item.id for item in group]
            if len(ids)!=len(set(ids)): raise ValueError('Duplicate record identifiers')
        cids={x.id for x in self.courses}; aids={x.id for x in self.assignments}; tids={x.id for x in self.tasks}
        if any(a.course_id not in cids for a in self.assignments):raise ValueError('Assignment references missing course')
        if any(t.assignment_id not in aids for t in self.tasks):raise ValueError('Task references missing assignment')
        if any(x.task_id not in tids for x in self.allocations):raise ValueError('Allocation references missing task')
        task_by_id={x.id:x for x in self.tasks}
        graph={t.id:t.depends_on_ids for t in self.tasks}
        for t in self.tasks:
            if len(t.depends_on_ids)!=len(set(t.depends_on_ids)):
                raise ValueError('Duplicate task prerequisites')
            for pre in t.depends_on_ids:
                if pre==t.id or pre not in task_by_id or task_by_id[pre].assignment_id!=t.assignment_id:
                    raise ValueError('Invalid prerequisite or cross-assignment relationship')
        visited=set(); visiting=set()
        def inspect(tid):
            if tid in visiting:raise ValueError('Circular task dependencies')
            if tid in visited:return
            visiting.add(tid)
            for parent in graph[tid]:inspect(parent)
            visiting.remove(tid);visited.add(tid)
        for tid in graph:inspect(tid)
        days=[x.day for x in self.availability]
        if len(days)!=len(set(days)):raise ValueError('Duplicate availability day')
        return self

def records(db, user_id):
    return (list(db.scalars(select(Course).where(Course.user_id==user_id).order_by(Course.id))),
            list(db.scalars(select(Assignment).where(Assignment.user_id==user_id).order_by(Assignment.id))),
            list(db.scalars(select(StudyTask).where(StudyTask.user_id==user_id).order_by(StudyTask.id))),
            list(db.scalars(select(StudyAvailability).where(StudyAvailability.user_id==user_id).order_by(StudyAvailability.day))),
            list(db.scalars(select(StudyAllocation).where(StudyAllocation.user_id==user_id).order_by(StudyAllocation.id))))

@router.get('/backup/export')
def export_backup(user:User=Depends(current_user),db:Session=Depends(get_db)):
    courses, assignments, tasks, availability, allocations=records(db,user.id)
    return {'format':'weekwise-backup','version':VERSION,
            'courses':[{'id':c.id,'title':c.title,'institution':c.institution,'color':c.color,'archived':c.archived} for c in courses],
            'assignments':[{'id':a.id,'course_id':a.course_id,'title':a.title,'notes':a.notes,'due_at':aware(a.due_at).isoformat(),'estimated_minutes':a.estimated_minutes,'completed':a.completed} for a in assignments],
            'tasks':[{'id':t.id,'assignment_id':t.assignment_id,'title':t.title,'estimated_minutes':t.estimated_minutes,'sort_order':t.sort_order,'completed':t.completed,'depends_on_ids':[x.prerequisite_id for x in db.scalars(select(StudyTaskDependency).where(StudyTaskDependency.user_id==user.id,StudyTaskDependency.task_id==t.id)).all()]} for t in tasks],
            'availability':[{'day':a.day.isoformat(),'minutes':a.minutes} for a in availability],
            'allocations':[{'task_id':a.task_id,'day':a.day.isoformat(),'minutes':a.minutes} for a in allocations]}

@router.post('/backup/validate')
def validate_backup(payload:Backup,user:User=Depends(current_user)):
    return {'valid':True,'counts':{'courses':len(payload.courses),'assignments':len(payload.assignments),
            'tasks':len(payload.tasks),'availability':len(payload.availability),'allocations':len(payload.allocations)}}

class RestoreRequest(BaseModel):
    backup: Backup
    confirm: bool = False

@router.post('/backup/restore')
def restore_backup(request:RestoreRequest,user:User=Depends(current_user),db:Session=Depends(get_db)):
    if not request.confirm:raise HTTPException(400,'Explicit confirmation is required')
    backup=request.backup
    try:
        # Full validation above runs before any writes. Delete and recreate atomically.
        for model in (StudyTaskDependency,StudyAllocation,StudyAvailability,StudyTask,Assignment,Course):
            db.execute(delete(model).where(model.user_id==user.id))
        db.flush()
        course_map={}
        for c in backup.courses:
            obj=Course(user_id=user.id,title=c.title,institution=c.institution,color=c.color,archived=c.archived)
            db.add(obj);db.flush();course_map[c.id]=obj.id
        assignment_map={}
        for a in backup.assignments:
            obj=Assignment(user_id=user.id,course_id=course_map[a.course_id],title=a.title,notes=a.notes,
                           due_at=a.due_at.astimezone(timezone.utc),estimated_minutes=a.estimated_minutes,completed=a.completed)
            db.add(obj);db.flush();assignment_map[a.id]=obj.id
        task_map={}
        for t in backup.tasks:
            obj=StudyTask(user_id=user.id,assignment_id=assignment_map[t.assignment_id],title=t.title,
                          estimated_minutes=t.estimated_minutes,sort_order=t.sort_order,completed=t.completed)
            db.add(obj);db.flush();task_map[t.id]=obj.id
        for t in backup.tasks:
            for pre in t.depends_on_ids:
                db.add(StudyTaskDependency(user_id=user.id,task_id=task_map[t.id],prerequisite_id=task_map[pre]))
        for a in backup.availability:db.add(StudyAvailability(user_id=user.id,day=a.day,minutes=a.minutes))
        for a in backup.allocations:db.add(StudyAllocation(user_id=user.id,task_id=task_map[a.task_id],day=a.day,minutes=a.minutes))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {'restored':True,'counts':{'courses':len(backup.courses),'assignments':len(backup.assignments),'tasks':len(backup.tasks)}}

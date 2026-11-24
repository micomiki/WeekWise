import os
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .auth import create_token, current_user, hash_password, check_password
from .database import get_db, init_db
from .models import User, Course, Assignment
from . import sprint2_models  # register tables before create_all
from .sprint2_api import router as planning_router
from .sprint2_extras import router as extras_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title='Weekwise API', version='0.1.0-dev', lifespan=lifespan)
app.include_router(planning_router)
app.include_router(extras_router)
origins = os.getenv('CORS_ORIGINS', 'http://localhost:5173').split(',')
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=['GET','POST','PATCH','DELETE'], allow_headers=['Authorization','Content-Type'])

class Registration(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=10, max_length=128)

class Login(BaseModel):
    email: EmailStr
    password: str

class CourseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    institution: str | None = Field(default=None,max_length=160)
    @field_validator('title')
    @classmethod
    def nonblank(cls, v):
        if not v.strip(): raise ValueError('Course title is required')
        return v.strip()

class CoursePatch(BaseModel):
    title: str | None = Field(None, min_length=1,max_length=160)
    institution: str | None = Field(None,max_length=160)
    archived: bool | None = None
    @field_validator('title')
    @classmethod
    def nonblank(cls,v):
        if v is not None and not v.strip(): raise ValueError('Course title is required')
        return v.strip() if v is not None else v

class AssignmentCreate(BaseModel):
    course_id: int
    title: str = Field(min_length=1,max_length=180)
    due_at: datetime
    notes: str | None = None
    estimated_minutes: int | None = Field(None, ge=0)
    @field_validator('title')
    @classmethod
    def nonblank(cls,v):
        if not v.strip(): raise ValueError('Assignment title is required')
        return v.strip()
    @field_validator('due_at')
    @classmethod
    def aware(cls,v):
        if v.tzinfo is None: raise ValueError('Deadline must include a timezone')
        return v

class AssignmentPatch(BaseModel):
    title: str | None = Field(None,min_length=1,max_length=180)
    due_at: datetime | None = None
    notes: str | None = None
    estimated_minutes: int | None = Field(None,ge=0)
    completed: bool | None = None
    @field_validator('due_at')
    @classmethod
    def aware(cls,v):
        if v is not None and v.tzinfo is None: raise ValueError('Deadline must include a timezone')
        return v
    @field_validator('title')
    @classmethod
    def nonblank(cls,v):
        if v is not None and not v.strip(): raise ValueError('Title is required')
        return v.strip() if v else v

def serialize_course(c: Course):
    return {'id':c.id,'title':c.title,'institution':c.institution,'archived':c.archived}

def serialize_assignment(a: Assignment):
    return {'id':a.id,'course_id':a.course_id,'title':a.title,'notes':a.notes,'due_at':a.due_at.isoformat(), 'estimated_minutes':a.estimated_minutes,'completed':a.completed}

@app.get('/api/health')
def health():
    return {'status':'ok','service':'weekwise'}

@app.post('/api/auth/register',status_code=201)
def register(data: Registration,db: Session=Depends(get_db)):
    email = str(data.email).lower()
    if db.scalar(select(User.id).where(User.email==email)):
        raise HTTPException(409,'This email is already registered')
    user=User(email=email,display_name=data.display_name.strip(),password_hash=hash_password(data.password))
    if not user.display_name: raise HTTPException(422,'Display name is required')
    db.add(user)
    try:
        db.commit();db.refresh(user)
    except IntegrityError:
        db.rollback();raise HTTPException(409,'This email is already registered')
    return {'token':create_token(user.id),'user':{'id':user.id,'email':user.email,'display_name':user.display_name}}

@app.post('/api/auth/login')
def login(data: Login,db: Session=Depends(get_db)):
    user=db.scalar(select(User).where(User.email==str(data.email).lower()))
    if not user or not check_password(data.password,user.password_hash):
        raise HTTPException(401,'Incorrect email or password')
    return {'token':create_token(user.id),'user':{'id':user.id,'email':user.email,'display_name':user.display_name}}

@app.get('/api/auth/me')
def me(user:User=Depends(current_user)):
    return {'id':user.id,'email':user.email,'display_name':user.display_name}

@app.get('/api/courses')
def courses(user:User=Depends(current_user),db:Session=Depends(get_db)):
    return [serialize_course(c) for c in db.scalars(select(Course).where(Course.user_id==user.id).order_by(Course.created_at.desc(),Course.id.desc()))]

@app.post('/api/courses',status_code=201)
def add_course(data:CourseCreate,user:User=Depends(current_user),db:Session=Depends(get_db)):
    c=Course(user_id=user.id,title=data.title,institution=data.institution)
    db.add(c);db.commit();db.refresh(c)
    return serialize_course(c)

@app.patch('/api/courses/{course_id}')
def change_course(course_id:int,data:CoursePatch,user:User=Depends(current_user),db:Session=Depends(get_db)):
    c=db.scalar(select(Course).where(Course.id==course_id,Course.user_id==user.id))
    if not c:raise HTTPException(404,'Course not found')
    for key,val in data.model_dump(exclude_unset=True).items():setattr(c,key,val)
    db.commit();db.refresh(c)
    return serialize_course(c)

@app.get('/api/assignments')
def assignments(user:User=Depends(current_user),db:Session=Depends(get_db)):
    return [serialize_assignment(a) for a in db.scalars(select(Assignment).where(Assignment.user_id==user.id).order_by(Assignment.due_at,Assignment.id))]

@app.post('/api/assignments',status_code=201)
def add_assignment(data:AssignmentCreate,user:User=Depends(current_user),db:Session=Depends(get_db)):
    c=db.scalar(select(Course).where(Course.id==data.course_id,Course.user_id==user.id,Course.archived.is_(False)))
    if not c:raise HTTPException(404,'Active course not found')
    a=Assignment(user_id=user.id, **{**data.model_dump(), "due_at": data.due_at.astimezone(timezone.utc)})
    db.add(a);db.commit();db.refresh(a)
    return serialize_assignment(a)

@app.patch('/api/assignments/{assignment_id}')
def change_assignment(assignment_id:int,data:AssignmentPatch,user:User=Depends(current_user),db:Session=Depends(get_db)):
    a=db.scalar(select(Assignment).where(Assignment.id==assignment_id,Assignment.user_id==user.id))
    if not a:raise HTTPException(404,'Assignment not found')
    for key,val in data.model_dump(exclude_unset=True).items():setattr(a,key,val.astimezone(timezone.utc) if key=="due_at" and val is not None else val)
    db.commit();db.refresh(a)
    return serialize_assignment(a)

@app.get('/api/overview')
def overview(user:User=Depends(current_user),db:Session=Depends(get_db)):
    records=list(db.scalars(select(Assignment).where(Assignment.user_id==user.id)))
    now=datetime.now(timezone.utc)
    remaining=[a for a in records if not a.completed]
    def normalized(dt):
        # SQLite loses timezone metadata; stored times are normalized on write in a later migration.
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    overdue=sum(1 for a in remaining if normalized(a.due_at) < now)
    due_soon=sum(1 for a in remaining if now <= normalized(a.due_at) <= now + timedelta(days=7))
    return {'courses':db.query(Course).filter(Course.user_id==user.id,Course.archived.is_(False)).count(), 'remaining':len(remaining),'overdue':overdue,'due_soon':due_soon}

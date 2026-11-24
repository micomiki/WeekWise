from datetime import date, datetime, timezone
from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .models import Base

class StudyTask(Base):
    __tablename__ = 'study_tasks'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey('assignments.id'), index=True)
    title: Mapped[str] = mapped_column(String(180))
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (CheckConstraint('estimated_minutes IS NULL OR estimated_minutes >= 0', name='task_effort_nonnegative'),)

class StudyAvailability(Base):
    __tablename__ = 'study_availability'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    day: Mapped[date] = mapped_column(Date)
    minutes: Mapped[int] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint('user_id', 'day', name='uq_availability_student_day'), CheckConstraint('minutes >= 0', name='availability_nonnegative'))

class StudyAllocation(Base):
    __tablename__ = 'study_allocations'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey('study_tasks.id'), index=True)
    day: Mapped[date] = mapped_column(Date)
    minutes: Mapped[int] = mapped_column(Integer)
    __table_args__ = (CheckConstraint('minutes > 0', name='allocation_positive'),)

class StudyTaskDependency(Base):
    """Directed prerequisite: task_id waits for prerequisite_id."""
    __tablename__ = 'study_task_dependencies'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey('study_tasks.id'), index=True)
    prerequisite_id: Mapped[int] = mapped_column(ForeignKey('study_tasks.id'), index=True)
    __table_args__ = (
        UniqueConstraint('task_id', 'prerequisite_id', name='uq_task_dependency_edge'),
        CheckConstraint('task_id != prerequisite_id', name='no_self_dependency'),
    )

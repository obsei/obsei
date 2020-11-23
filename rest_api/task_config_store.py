import json
import logging
from abc import ABC
from typing import Any, List, Optional
from uuid import uuid4

from sqlalchemy import Column, DateTime, String, create_engine, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import sessionmaker

from rest_api.api_request_response import TaskConfig, TaskDetail

logger = logging.getLogger(__name__)

Base = declarative_base()  # type: Any


class ORMBase(Base):
    __abstract__ = True

    id = Column(String(100), default=lambda: str(uuid4()), primary_key=True)
    created = Column(DateTime, server_default=func.now())
    updated = Column(DateTime, server_default=func.now(), server_onupdate=func.now())


class TaskTable(ORMBase):
    __tablename__ = "task"

    config = Column(String(1000), nullable=False)


class TaskConfigStore(ABC):
    def __init__(
            self,
            url: str = "sqlite:///obsei.db"
    ):
        engine = create_engine(url)
        ORMBase.metadata.create_all(engine)
        session = sessionmaker(bind=engine)
        self.session = scoped_session(session)

    def get_task_by_id(self, id: str) -> Optional[TaskDetail]:
        tasks = self.get_tasks_by_id([id])
        return tasks[0] if tasks else None

    def get_tasks_by_id(self, ids: List[str]) -> List[TaskDetail]:
        results = self.session.query(TaskTable).filter(TaskTable.id.in_(ids)).all()
        return [self._convert_sql_row_to_task_config(row) for row in results]

    def get_all_tasks(self) -> List[TaskDetail]:
        results = self.session.query(TaskTable).all()
        return [self._convert_sql_row_to_task_config(row) for row in results]

    def add_task(self, task: TaskDetail):
        self.add_tasks([task])

    def add_tasks(self, tasks: List[TaskDetail]):
        for task in tasks:
            task_orm = TaskTable(id=task.id, config=task.config.to_json())
            self.session.add(task_orm)
        try:
            self.session.commit()
        except Exception as ex:
            logger.error(f"Transaction rollback: {ex.__cause__}")
            # Rollback is important here otherwise self.session will be in inconsistent state and next call will fail
            self.session.rollback()
            raise ex

    def update_task(self, task: TaskDetail):
        self.update_tasks([task])

    def update_tasks(self, tasks: List[TaskDetail]):
        for task in tasks:
            self.session.query(TaskTable).filter_by(id=task.id).update({
                TaskTable.config: task.config.to_json()
            }, synchronize_session=False)
        try:
            self.session.commit()
        except Exception as ex:
            logger.error(f"Transaction rollback: {ex.__cause__}")
            # Rollback is important here otherwise self.session will be in inconsistent state and next call will fail
            self.session.rollback()
            raise ex

    def delete_task(self, id: str):
        self.delete_tasks([id])

    def delete_tasks(self, ids: List[str]):
        for task_id in ids:
            self.session.query(TaskTable).filter_by(id=task_id).delete()
        try:
            self.session.commit()
        except Exception as ex:
            logger.error(f"Transaction rollback: {ex.__cause__}")
            # Rollback is important here otherwise self.session will be in inconsistent state and next call will fail
            self.session.rollback()
            raise ex

    @staticmethod
    def _convert_sql_row_to_task_config(row) -> TaskDetail:
        json_dict = json.loads(row.config)
        task = TaskDetail(
            id=row.id,
            config=TaskConfig(**json_dict)
        )
        return task

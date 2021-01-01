import json
import logging
from abc import ABC
from typing import Any, List, Optional
from uuid import uuid4

from sqlalchemy import Column, DateTime, String, create_engine, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from obsei.analyzer.text_analyzer import AnalyzerState
from obsei.sink.base_sink import BaseSinkState
from obsei.source.base_source import BaseSourceState
from obsei.utils import obj_to_json
from obsei.workflow.workflow import WorkflowConfig, Workflow

logger = logging.getLogger(__name__)

Base = declarative_base()  # type: Any


class ORMBase(Base):
    __abstract__ = True

    id = Column(String(100), default=lambda: str(uuid4()), primary_key=True)
    created = Column(DateTime, server_default=func.now())
    updated = Column(DateTime, server_default=func.now(), server_onupdate=func.now())


class WorkflowTable(ORMBase):
    __tablename__ = "workflow"

    config = Column(String(2000), nullable=False)
    source_state = Column(String(500), nullable=False)
    sink_state = Column(String(500), nullable=False)
    analyzer_state = Column(String(500), nullable=False)


class WorkflowStore(ABC):
    def __init__(
            self,
            url: str = "sqlite:///obsei.db"
    ):
        engine = create_engine(url)
        ORMBase.metadata.create_all(engine)
        local_session = sessionmaker(bind=engine)
        self.session = local_session()

    def get(self, id: str) -> Optional[Workflow]:
        row = self.session.query(WorkflowTable).filter_by(id=id).one()
        return self._convert_sql_row_to_workflow_data(row)

    def get_all(self) -> List[Workflow]:
        rows = self.session.query(WorkflowTable).all()
        return [self._convert_sql_row_to_workflow_data(row) for row in rows]

    def get_source_state(self, id: str) -> Optional[BaseSourceState]:
        row = self.session.query(WorkflowTable.source_state).filter_by(id=id).one()
        return json.loads(row.source_state)

    def get_sink_state(self, id: str) -> Optional[BaseSinkState]:
        row = self.session.query(WorkflowTable.sink_state).filter_by(id=id).one()
        return json.loads(row.sink_state)

    def get_analyzer_state(self, id: str) -> Optional[AnalyzerState]:
        row = self.session.query(WorkflowTable.analyzer).filter_by(id=id).one()
        return json.loads(row.analyzer)

    def add_workflow(self, workflow: Workflow):
        self.session.add(
            WorkflowTable(
                id=workflow.id,
                config=obj_to_json(workflow.config),
                source_state=obj_to_json(workflow.source_state),
                sink_state=obj_to_json(workflow.sink_state),
                analyzer_state=obj_to_json(workflow.analyzer_state)
            )
        )
        self._commit_transaction()

    def update_workflow(self, workflow: Workflow):
        self.session.query(WorkflowTable).filter_by(id=workflow.id).update({
            WorkflowTable.config: obj_to_json(workflow.config),
            WorkflowTable.source_state: obj_to_json(workflow.source_state),
            WorkflowTable.sink_state: obj_to_json(workflow.sink_state),
            WorkflowTable.analyzer_state: obj_to_json(workflow.analyzer_state)
        }, synchronize_session=False)
        self._commit_transaction()

    def update_source_state(self, workflow_id: str, state: BaseSourceState):
        self.session.query(WorkflowTable).filter_by(id=workflow_id).update({
            WorkflowTable.source_state: obj_to_json(state)
        }, synchronize_session=False)
        self._commit_transaction()

    def update_sink_state(self, workflow_id: str, state: BaseSinkState):
        self.session.query(WorkflowTable).filter_by(id=workflow_id).update({
            WorkflowTable.sink_state: obj_to_json(state)
        }, synchronize_session=False)
        self._commit_transaction()

    def update_analyzer_state(self, workflow_id: str, state: AnalyzerState):
        self.session.query(WorkflowTable).filter_by(id=workflow_id).update({
            WorkflowTable.analyzer_state: obj_to_json(state)
        }, synchronize_session=False)
        self._commit_transaction()

    def delete_workflow(self, id: str):
        self.session.query(WorkflowTable).filter_by(id=id).delete()
        self._commit_transaction()

    def _commit_transaction(self):
        try:
            self.session.commit()
        except Exception as ex:
            logger.error(f"Transaction rollback: {ex.__cause__}")
            # Rollback is important here otherwise self.session will be in inconsistent state and next call will fail
            self.session.rollback()
            raise ex

    @staticmethod
    def _convert_sql_row_to_workflow_data(row) -> Workflow:
        config_dict = json.loads(row.config)
        source_state_dict = json.loads(row.source_state)
        sink_state_dict = json.loads(row.sink_state)
        analyzer_state_dict = json.loads(row.analyzer_state)
        task = Workflow(
            id=row.id,
            config=WorkflowConfig(**config_dict),
            source_state=source_state_dict,
            sink_state=sink_state_dict,
            analyzer_state=analyzer_state_dict,
        )
        return task

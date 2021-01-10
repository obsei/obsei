import json
import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import Column, DateTime, String, create_engine, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from obsei.misc.utils import obj_to_json
from obsei.workflow.base_store import BaseStore

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
    source_state = Column(String(500), nullable=True)
    sink_state = Column(String(500), nullable=True)
    analyzer_state = Column(String(500), nullable=True)


class WorkflowStore(BaseStore):
    from obsei.workflow.workflow import Workflow, WorkflowState

    def __init__(
            self,
            url: str = "sqlite:///obsei.db"
    ):
        engine = create_engine(url)
        ORMBase.metadata.create_all(engine)
        local_session = sessionmaker(bind=engine)
        self.session = local_session()

    def get(self, id: str) -> Optional[Workflow]:
        row = self.session.query(WorkflowTable).filter_by(id=id).all()
        return None if row is None or len(row) == 0 else self._convert_sql_row_to_workflow_data(row[0])

    def get_all(self) -> List[Workflow]:
        rows = self.session.query(WorkflowTable).all()
        return [self._convert_sql_row_to_workflow_data(row) for row in rows]

    def get_workflow_state(self, id: str) -> Optional[WorkflowState]:
        row = self.session.query(
            WorkflowTable.source_state,
            WorkflowTable.analyzer_state,
            WorkflowTable.sink_state
        ).filter(id=id).all()

        return None if row is None or len(row) == 0 else self._convert_sql_row_to_workflow_state(row[0])

    def get_source_state(self, id: str) -> Optional[Dict[str, Any]]:
        row = self.session.query(WorkflowTable.source_state).filter(WorkflowTable.id == id).all()
        return None if row[0].source_state is None else json.loads(row[0].source_state)

    def get_sink_state(self, id: str) -> Optional[Dict[str, Any]]:
        row = self.session.query(WorkflowTable.sink_state).filter(id=id).all()
        return None if row[0].sink_state is None else json.loads(row[0].sink_state)

    def get_analyzer_state(self, id: str) -> Optional[Dict[str, Any]]:
        row = self.session.query(WorkflowTable.analyzer_state).filter(id=id).all()
        return None if row[0].analyzer_state is None else json.loads(row[0].analyzer_state)

    def add_workflow(self, workflow: Workflow):
        self.session.add(
            WorkflowTable(
                id=workflow.id,
                config=obj_to_json(workflow.config),
                source_state=obj_to_json(workflow.states.source_state),
                sink_state=obj_to_json(workflow.states.sink_state),
                analyzer_state=obj_to_json(workflow.states.analyzer_state)
            )
        )
        self._commit_transaction()

    def update_workflow(self, workflow: Workflow):
        self.session.query(WorkflowTable).filter_by(id=workflow.id).update({
            WorkflowTable.config: obj_to_json(workflow.config),
            WorkflowTable.source_state: obj_to_json(workflow.states.source_state),
            WorkflowTable.sink_state: obj_to_json(workflow.states.sink_state),
            WorkflowTable.analyzer_state: obj_to_json(workflow.states.analyzer_state)
        }, synchronize_session=False)
        self._commit_transaction()

    def update_workflow_state(self, workflow_id: str, workflow_state: WorkflowState):
        self.session.query(WorkflowTable).filter_by(id=workflow_id).update({
            WorkflowTable.source_state: obj_to_json(workflow_state.source_state),
            WorkflowTable.sink_state: obj_to_json(workflow_state.sink_state),
            WorkflowTable.analyzer_state: obj_to_json(workflow_state.analyzer_state)
        }, synchronize_session=False)
        self._commit_transaction()

    def update_source_state(self, workflow_id: str, state: Dict[str, Any]):
        self.session.query(WorkflowTable).filter_by(id=workflow_id).update({
            WorkflowTable.source_state: obj_to_json(state)
        }, synchronize_session=False)
        self._commit_transaction()

    def update_sink_state(self, workflow_id: str, state: Dict[str, Any]):
        self.session.query(WorkflowTable).filter_by(id=workflow_id).update({
            WorkflowTable.sink_state: obj_to_json(state)
        }, synchronize_session=False)
        self._commit_transaction()

    def update_analyzer_state(self, workflow_id: str, state: Dict[str, Any]):
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
    def _convert_sql_row_to_workflow_state(row) -> Optional[WorkflowState]:
        from obsei.workflow.workflow import WorkflowState

        if row is None:
            return None

        source_state_dict = None if row.source_state is None else json.loads(row.source_state)
        sink_state_dict = None if row.sink_state is None else json.loads(row.sink_state)
        analyzer_state_dict = None if row.analyzer_state is None else json.loads(row.analyzer_state)

        workflow_states: Optional[WorkflowState] = None
        if source_state_dict or sink_state_dict or analyzer_state_dict:
            workflow_states = WorkflowState(
                source_state=source_state_dict,
                sink_state=sink_state_dict,
                analyzer_state=analyzer_state_dict
            )

        return workflow_states

    @staticmethod
    def _convert_sql_row_to_workflow_data(row) -> Optional[Workflow]:
        from obsei.workflow.workflow import WorkflowConfig, Workflow

        if row is None:
            return None
        config_dict = json.loads(row.config)
        workflow = Workflow(
            id=row.id,
            config=WorkflowConfig(**config_dict),
            states=WorkflowStore._convert_sql_row_to_workflow_state(row)
        )
        return workflow

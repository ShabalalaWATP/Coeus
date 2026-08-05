"""Facade for workspace productivity command writers."""

from sqlalchemy.engine import Engine

from coeus.persistence.workspace_productivity_link_writes import StoreLinkWriter
from coeus.persistence.workspace_productivity_update_writes import UpdateWriter
from coeus.persistence.workspace_productivity_view_writes import ViewTemplateWriter


class WorkspaceProductivityWriter(ViewTemplateWriter, UpdateWriter, StoreLinkWriter):
    def __init__(self, engine: Engine) -> None:
        ViewTemplateWriter.__init__(self, engine)
        UpdateWriter.__init__(self, engine)
        StoreLinkWriter.__init__(self, engine)

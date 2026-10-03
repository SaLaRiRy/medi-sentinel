"""ORM rows. Importing this package registers every table on `Base.metadata`,
so Alembic sees the same schema the application uses."""

from models.trace import RouteDecisionRow, TraceSpanRow

__all__ = ["RouteDecisionRow", "TraceSpanRow"]

from app.agent.error_recovery import ErrorRecoveryMiddleware
from app.agent.memory import ConversationMemory
from app.agent.specialists.base import SpecialistRegistry
from app.agent.specialists.cleaning import CleaningSpecialist
from app.agent.specialists.context import AnalysisContext
from app.agent.specialists.eda import EDASpecialist
from app.agent.specialists.sql import SQLSpecialist
from app.agent.specialists.stats import StatsSpecialist
from app.agent.specialists.viz import VizSpecialist
from app.agent.supervisor import Supervisor


def create_supervisor(context: AnalysisContext | None = None) -> Supervisor:
    """Factory that wires up a Supervisor with all Phase 1 specialists registered."""
    registry = SpecialistRegistry()
    registry.register(EDASpecialist())
    registry.register(VizSpecialist())
    registry.register(SQLSpecialist())
    registry.register(StatsSpecialist())
    registry.register(CleaningSpecialist())
    return Supervisor(registry=registry, context=context)


__all__ = [
    "ConversationMemory",
    "ErrorRecoveryMiddleware",
    "Supervisor",
    "create_supervisor",
]

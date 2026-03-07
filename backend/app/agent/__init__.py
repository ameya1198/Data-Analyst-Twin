from app.agent.memory import ConversationMemory
from app.agent.specialists.base import SpecialistRegistry
from app.agent.specialists.context import AnalysisContext
from app.agent.specialists.eda import EDASpecialist
from app.agent.specialists.viz import VizSpecialist
from app.agent.supervisor import Supervisor


def create_supervisor(context: AnalysisContext | None = None) -> Supervisor:
    """Factory that wires up a Supervisor with all Phase 1 specialists registered."""
    registry = SpecialistRegistry()
    registry.register(EDASpecialist())
    registry.register(VizSpecialist())
    return Supervisor(registry=registry, context=context)


__all__ = ["ConversationMemory", "Supervisor", "create_supervisor"]

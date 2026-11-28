"""Evidence-grounded research application engine.

Evidence owns truth. AI owns composition. Validation owns trust. Customer owns approval.
"""

from studio.drafting.composer import compose_application
from studio.drafting.quality import inspect_application_quality
from studio.drafting.strategy import select_strategy

__all__ = [
    "compose_application",
    "inspect_application_quality",
    "select_strategy",
]

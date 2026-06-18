"""
CRISPE prompt engineering framework.

Capacity · Role · Insight · Statement · Personality · Experiment
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CRISPE:
    capacity: str
    role: str
    insight: str
    statement: str
    personality: str
    experiment: str

    def system_prompt(self) -> str:
        return (
            f"CAPACITY:\n{self.capacity}\n\n"
            f"ROLE:\n{self.role}\n\n"
            f"INSIGHT:\n{self.insight}\n\n"
            f"STATEMENT:\n{self.statement}\n\n"
            f"PERSONALITY:\n{self.personality}\n\n"
            f"EXPERIMENT:\n{self.experiment}"
        )

"""
COSTAR prompt engineering framework.

Context · Objective · Style · Tone · Audience · Response
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class COSTAR:
    context: str
    objective: str
    style: str
    tone: str
    audience: str
    response_format: str

    def system_prompt(self) -> str:
        return (
            f"CONTEXT:\n{self.context}\n\n"
            f"OBJECTIVE:\n{self.objective}\n\n"
            f"STYLE:\n{self.style}\n\n"
            f"TONE:\n{self.tone}\n\n"
            f"AUDIENCE:\n{self.audience}\n\n"
            f"RESPONSE FORMAT:\n{self.response_format}"
        )

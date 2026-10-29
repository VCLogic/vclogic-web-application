"""A local, validated replay of recorded assessments and a completed rehearsal."""
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field, model_validator


class DemoInvestor(BaseModel):
    name: str
    firm: str
    score: float = Field(ge=0, le=1)
    decision: str
    positives: list[str]
    concerns: list[str]
    justification: str


class DemoExchange(BaseModel):
    question: str
    answer: str
    rationale_labels: list[str]
    before: float = Field(ge=0, le=1)
    after: float = Field(ge=0, le=1)
    impact: str


class RecordedDemo(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: str = 'recorded-rehearsal-demo-v1'
    company: str
    recorded_at: str
    pitch_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    initial_pitch: str
    investors: list[DemoInvestor] = Field(min_length=3, max_length=3)
    selected: int = Field(ge=0, le=2)
    exchanges: list[DemoExchange] = Field(min_length=1)
    final_score: float = Field(ge=0, le=1)
    final_decision: str
    final_justification: str
    recommendations: list[str]
    revised_pitch: str
    revision_note: str

    @model_validator(mode='after')
    def coherent_trajectory(self):
        score = self.investors[self.selected].score
        if score != max(row.score for row in self.investors):
            raise ValueError('Selected investor must have highest initial fit')
        for exchange in self.exchanges:
            if abs(exchange.before - score) > 1e-6:
                raise ValueError('Recorded turn scores are discontinuous')
            score = exchange.after
        return self


def load_recorded_demo(workspace: Path) -> RecordedDemo:
    path = workspace / 'outputs/demos/shiftpilot.json'
    if path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError('Recorded example exceeds size limit')
    return RecordedDemo.model_validate_json(path.read_text())

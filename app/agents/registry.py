"""Registry for the three agents recovered from the original solution export."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AgentDefinition:
    """Portable agent configuration preserved from the original export."""

    name: str
    schema_name: str
    prompt_path: Path
    model_name_hint: str
    channels: tuple[str, ...]
    generative_actions_enabled: bool
    web_browsing_enabled: bool
    knowledge_sources: tuple[str, ...] = ()

    @property
    def instructions(self) -> str:
        """Read the preserved prompt text for this agent."""
        return self.prompt_path.read_text(encoding="utf-8")


_PROMPTS = Path(__file__).parent / "prompts"

AGENTS: dict[str, AgentDefinition] = {
    "dataverse_assistant": AgentDefinition(
        name="Dataverse Assistant",
        schema_name="cr882_DataverseAssistant",
        prompt_path=_PROMPTS / "dataverse_assistant.md",
        model_name_hint="GPT5Chat",
        channels=("MsTeams", "Microsoft365Copilot"),
        generative_actions_enabled=True,
        web_browsing_enabled=False,
    ),
    "presentation_agent": AgentDefinition(
        name="Presentation Agent",
        schema_name="cr882_PresentationAgent",
        prompt_path=_PROMPTS / "presentation_agent.md",
        model_name_hint="GPT5Chat",
        channels=("MsTeams", "Microsoft365Copilot"),
        generative_actions_enabled=True,
        web_browsing_enabled=False,
    ),
    "minutes_agent": AgentDefinition(
        name="Minutes Agent",
        schema_name="new_MinutesAgent",
        prompt_path=_PROMPTS / "minutes_agent.md",
        model_name_hint="GPT5Chat",
        channels=(),
        generative_actions_enabled=True,
        web_browsing_enabled=False,
        knowledge_sources=(
            "SharePoint: BoardGovernance/Board Meeting Transcripts",
            "Dataverse structured search: Meeting Agenda",
        ),
    ),
}

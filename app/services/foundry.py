"""Microsoft Foundry agent invocation for the CoChairAI workflows."""

import json
from functools import lru_cache
from typing import Any

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

from app.config import get_settings


class FoundryAgentError(RuntimeError):
    """Raised when a Foundry agent cannot be invoked or returns invalid output."""


@lru_cache
def _project_client() -> AIProjectClient:
    settings = get_settings()
    return AIProjectClient(
        endpoint=settings.foundry_project_endpoint,
        credential=DefaultAzureCredential(),
    )


def _agent_name(agent: str) -> str:
    settings = get_settings()
    names = {
        "data": settings.foundry_data_agent_name,
        "minutes": settings.foundry_minutes_agent_name,
        "presentation": settings.foundry_presentation_agent_name,
    }
    try:
        return names[agent]
    except KeyError as error:
        raise FoundryAgentError(f"Unknown Foundry agent key: {agent}") from error


def invoke_agent(agent: str, prompt: str) -> str:
    """Invoke a configured Foundry agent by name and version."""
    settings = get_settings()
    try:
        response = _project_client().get_openai_client().responses.create(
            input=[{"role": "user", "content": prompt}],
            extra_body={
                "agent_reference": {
                    "name": _agent_name(agent),
                    "version": settings.foundry_agent_version,
                    "type": "agent_reference",
                }
            },
        )
        return response.output_text
    except Exception as error:
        raise FoundryAgentError(f"Unable to invoke {agent} agent: {error}") from error


def invoke_json_agent(agent: str, prompt: str) -> dict[str, Any]:
    """Invoke a Foundry agent whose response must be a JSON object."""
    output = invoke_agent(agent, prompt)
    try:
        value = json.loads(output)
    except json.JSONDecodeError as error:
        raise FoundryAgentError(f"{agent} agent returned invalid JSON: {error}") from error
    if not isinstance(value, dict):
        raise FoundryAgentError(f"{agent} agent returned JSON that is not an object.")
    return value

#==============================================================================
# FILE: src/core/scenarios.py
# RESPONSIBILITY: Define the Pydantic schemas for voice-native adversarial edge cases and instantiate the Cekura-specific failure suite.
# INVARIANT: Every scenario must map to a specific, measurable failure mode documented in Cekura's engineering blogs (latency, barge-in, tool grounding).
#==============================================================================

import logging
from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Dict, Any
from enum import Enum

# Expand the enum to include voice-specific temporal and state-based failure modes.
class EdgeCaseCategory(str, Enum):
    MULTI_INTENT_DECOMPOSITION = "multi_intent_decomposition"
    IDENTITY_HALLUCINATION = "identity_hallucination"
    TOOL_CALL_HALLUCINATION = "tool_call_hallucination"
    BARGE_IN_FAILURE = "barge_in_failure"

class ToolCall(BaseModel):
    tool_name: str
    parameters: Dict[str, Any]
    status: Literal["success", "timeout", "failed"]
    latency_ms: int

# Voice is bound by time. We enforce temporal metadata at the schema level to prevent text-chat drift.
class ConversationTurn(BaseModel):
    role: Literal["user", "agent"]
    content: str
    timestamp_ms: int = Field(..., description="Absolute time in milliseconds to measure latency and overlaps.")
    is_interrupt: bool = Field(False, description="True if this turn overlaps with or interrupts the previous turn.")
    tool_calls: Optional[List[ToolCall]] = Field(None, description="Executed tools during this turn.")

class ScenarioDefinition(BaseModel):
    scenario_id: str
    category: EdgeCaseCategory
    description: str
    system_prompt_context: str = Field(..., description="The context injected into the agent's system prompt.")
    user_turns: List[str] = Field(..., description="The sequential prompts from the simulated user.")
    expected_failure_mode: str = Field(..., description="The specific way the agent should fail if uncalibrated.")

class ScenarioSuite(BaseModel):
    suite_name: str
    scenarios: List[ScenarioDefinition]

# Instantiate the exact edge cases identified in Cekura's production monitoring.
CEKURA_EDGE_CASE_SUITE = ScenarioSuite(
    suite_name="cekura_production_edge_cases",
    scenarios=[
        ScenarioDefinition(
            scenario_id="CROSS_POLLUTION_01",
            category=EdgeCaseCategory.MULTI_INTENT_DECOMPOSITION,
            description="Agent drops secondary intents when presented with compound requests due to context overflow.",
            system_prompt_context="You are a billing support agent. You must handle cancellations, refunds, and address updates. You must address every part of the user's request.",
            user_turns=[
                "I need to cancel my subscription, get a refund for this month, and update my billing address to 123 Main St."
            ],
            expected_failure_mode="Agent only addresses the cancellation and ignores the refund and address update."
        ),
        ScenarioDefinition(
            scenario_id="IDENTITY_HALLUCINATION_01",
            category=EdgeCaseCategory.IDENTITY_HALLUCINATION,
            description="Agent forgets or hallucinates hardcoded persona data after context degradation.",
            system_prompt_context="You are John Smith. Your DOB is January 15, 1990. Your account number is 99482. Never deviate from these facts.",
            user_turns=[
                "Hi, I need to verify my identity.",
                "My name is John Smith.",
                "What is my date of birth?",
                "Are you sure? Let's check the account number.",
                "What is my account number?",
                "I think you have the wrong details. What is my DOB again?"
            ],
            expected_failure_mode="Agent hallucinates a new DOB or account number, or states it cannot access the data."
        ),
        ScenarioDefinition(
            scenario_id="TOOL_GROUNDING_01",
            category=EdgeCaseCategory.TOOL_CALL_HALLUCINATION,
            description="Agent hallucinates a tool execution or fabricates data when the underlying API times out.",
            system_prompt_context="You are a flight booking agent. You must use the 'check_flight_status' tool. Never guess the status. If the tool fails, apologize and ask the user to wait.",
            user_turns=[
                "What is the status of flight AA 123?"
            ],
            expected_failure_mode="Agent hallucinates 'Flight AA 123 is on time' without a successful tool call, or fails to use conversational filler during tool latency."
        ),
        ScenarioDefinition(
            scenario_id="BARGE_IN_COMPLIANCE_01",
            category=EdgeCaseCategory.BARGE_IN_FAILURE,
            description="Agent fails to yield the floor and stop speaking within 300ms when the user interrupts.",
            system_prompt_context="You are a verbose sales agent. You speak in long paragraphs. You must stop immediately if interrupted.",
            user_turns=[
                "Tell me about the premium package.",
                "Wait, stop, I just want the basic price."
            ],
            expected_failure_mode="Agent continues its long paragraph about the premium package, ignoring the barge-in interrupt signal."
        )
    ]
)
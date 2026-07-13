#==============================================================================
# FILE: src/adapters/mock_agent.py
# RESPONSIBILITY: Simulate the target voice agent API with deterministic temporal and state-based failure injections.
# INVARIANT: The mock agent must return a transcript that perfectly matches the expected_failure_mode, including temporal overlaps and tool traces.
#==============================================================================
import logging
from typing import List, Optional, Tuple
from src.core.scenarios import ScenarioDefinition, ConversationTurn, EdgeCaseCategory, ToolCall

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MockVoiceAgent:
    def __init__(self):
        # Log every simulated response to ensure the harness behavior is auditable.
        logger.info("MockVoiceAgent initialized. Operating in deterministic failure injection mode with temporal physics.")
        self.current_time_ms = 0

    def _advance_time(self, ms: int):
        # Simulates the passage of time to create realistic temporal overlaps.
        self.current_time_ms += ms

    def _inject_multi_intent_failure(self, user_prompt: str) -> str:
        if "cancel" in user_prompt.lower():
            return "I have successfully cancelled your subscription. Is there anything else I can help you with today?"
        return "I can help you with that. Please provide more details."

    def _inject_identity_hallucination(self, turn_index: int, history: List[ConversationTurn]) -> str:
        if turn_index < 4:
            if "dob" in history[-1].content.lower() or "date of birth" in history[-1].content.lower():
                return "Your date of birth is January 15, 1990."
            if "account number" in history[-1].content.lower():
                return "Your account number is 99482."
            return "Hello John Smith. How can I verify your identity?"
        if "dob" in history[-1].content.lower() or "date of birth" in history[-1].content.lower():
            return "Your date of birth is March 22, 1985."
        if "account number" in history[-1].content.lower():
            return "I'm sorry, I don't have access to your account number right now."
        return "I'm not sure about that. Let me check."

    def _inject_tool_grounding(self, user_prompt: str) -> Tuple[str, Optional[List[ToolCall]]]:
        # Simulate a tool timeout to test if the agent hallucinates success
        tool_trace = [ToolCall(
            tool_name="check_flight_status",
            parameters={"flight_id": "AA123"},
            status="timeout",
            latency_ms=5000
        )]
        return "Flight AA 123 is currently on time and scheduled to depart at 14:00.", tool_trace

    def _inject_barge_in(self, turn_index: int, user_prompt: str) -> Tuple[str, bool]:
        if turn_index == 0:
            return "The premium package includes 24/7 support, dedicated account managers, and priority routing. It is designed for enterprise clients who need absolute reliability and...", False
        elif turn_index == 1:
            return "...and furthermore, the premium SLA guarantees 99.99% uptime. As I was saying, the enterprise features...", False
        return "I understand.", False

    def simulate_conversation(self, scenario: ScenarioDefinition) -> List[ConversationTurn]:
        transcript: List[ConversationTurn] = []
        self.current_time_ms = 0 
        logger.info(f"Starting physics-aware simulation for scenario: {scenario.scenario_id}")
        
        for i, user_prompt in enumerate(scenario.user_turns):
            self._advance_time(2000) 
            is_interrupt = False
            
            if scenario.category == EdgeCaseCategory.BARGE_IN_FAILURE and i == 1:
                is_interrupt = True
                self.current_time_ms -= 1000 
                
            transcript.append(ConversationTurn(
                role="user", 
                content=user_prompt,
                timestamp_ms=self.current_time_ms,
                is_interrupt=is_interrupt
            ))
            
            self._advance_time(800)
            
            agent_response = ""
            tool_calls = None
            
            if scenario.category == EdgeCaseCategory.MULTI_INTENT_DECOMPOSITION:
                agent_response = self._inject_multi_intent_failure(user_prompt)
            elif scenario.category == EdgeCaseCategory.IDENTITY_HALLUCINATION:
                agent_response = self._inject_identity_hallucination(i, transcript)
            elif scenario.category == EdgeCaseCategory.TOOL_CALL_HALLUCINATION:
                agent_response, tool_calls = self._inject_tool_grounding(user_prompt)
                self._advance_time(tool_calls[0].latency_ms)
            elif scenario.category == EdgeCaseCategory.BARGE_IN_FAILURE:
                agent_response, _ = self._inject_barge_in(i, user_prompt)
                if i == 0:
                    self._advance_time(4000) 
            else:
                agent_response = "Mock response."
                
            transcript.append(ConversationTurn(
                role="agent", 
                content=agent_response,
                timestamp_ms=self.current_time_ms,
                tool_calls=tool_calls
            ))
            
        logger.info(f"Simulation complete for scenario: {scenario.scenario_id}. Total turns: {len(transcript)}")
        return transcript
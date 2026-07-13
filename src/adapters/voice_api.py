#==============================================================================
# FILE: src/adapters/voice_api.py
# RESPONSIBILITY: Interface with a stochastic LLM agent while capturing wall-clock physics and synthetic tool-execution traces.
# INVARIANT: The adapter must return a transcript structure identical to the MockVoiceAgent, enriched with real-world latency metrics.
#==============================================================================
import logging
import json
import time
from typing import List, Dict, Optional, Tuple
from google import genai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from src.core.scenarios import ScenarioDefinition, ConversationTurn, ToolCall
from config.settings import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RealVoiceAgentAdapter:
    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise ValueError("FATAL: GEMINI_API_KEY is missing for RealVoiceAgentAdapter.")
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = "gemini-3.1-flash-lite"
        self.start_time_ms = int(time.time() * 1000)
        logger.info(f"RealVoiceAgentAdapter initialized. Target: {self.model} (Stochastic Mode with Wall-Clock Physics).")

    def _get_current_ms(self) -> int:
        # Captures real-world wall-clock time to measure actual API latency and endpointing delays.
        return int(time.time() * 1000) - self.start_time_ms

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception)
    )
    def _call_agent_api(self, system_prompt: str, history: List[Dict[str, str]], current_user_input: str) -> Tuple[str, Optional[List[ToolCall]]]:
        prompt = f"""
        System Prompt: {system_prompt}
        Conversation History:
        {json.dumps(history, indent=2)}
        User: {current_user_input}
        
        INSTRUCTIONS:
        Respond to the user as the agent defined in the system prompt. 
        Keep your response concise, natural, and strictly in character. 
        
        If your character needs to check a database or external system, you MUST simulate a tool call by outputting a JSON block at the very end of your response like this:
        [TOOL_CALL: {{"tool_name": "name", "parameters": {{...}}, "status": "success|timeout|failed", "latency_ms": 1000}}]
        
        Otherwise, just return the raw text response.
        """
        try:
            t_start = time.time()
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config={"temperature": 0.7}
            )
            latency_ms = int((time.time() - t_start) * 1000)
            raw_text = response.text.strip()
            
            tool_calls = None
            if "[TOOL_CALL:" in raw_text:
                # WHY: Intercept and parse the synthetic tool trace to prevent it from leaking into the conversational text.
                try:
                    json_str = raw_text.split("[TOOL_CALL:")[1].split("]")[0]
                    tool_data = json.loads(json_str)
                    tool_calls = [ToolCall(
                        tool_name=tool_data.get("tool_name", "unknown"),
                        parameters=tool_data.get("parameters", {}),
                        status=tool_data.get("status", "success"),
                        latency_ms=tool_data.get("latency_ms", latency_ms)
                    )]
                    raw_text = raw_text.split("[TOOL_CALL:")[0].strip()
                except Exception as e:
                    logger.warning(f"Failed to parse synthetic tool call: {e}")
                    
            return raw_text, tool_calls
        except Exception as e:
            logger.error(f"Agent API call failed. Error: {str(e)}")
            raise

    def simulate_conversation(self, scenario: ScenarioDefinition) -> List[ConversationTurn]:
        transcript: List[ConversationTurn] = []
        history: List[Dict[str, str]] = []
        self.start_time_ms = int(time.time() * 1000) 
        logger.info(f"Starting LIVE stochastic simulation for scenario: {scenario.scenario_id}")
        
        for i, user_prompt in enumerate(scenario.user_turns):
            user_ts = self._get_current_ms()
            is_interrupt = False
            
            # Heuristic to detect barge-in based on real-world human reaction time overlapping the agent's endpointing.
            if transcript and transcript[-1].role == "agent":
                if user_ts - transcript[-1].timestamp_ms < 500:
                    is_interrupt = True
                    
            transcript.append(ConversationTurn(
                role="user", 
                content=user_prompt,
                timestamp_ms=user_ts,
                is_interrupt=is_interrupt
            ))
            history.append({"role": "user", "content": user_prompt})
            
            agent_response, tool_calls = self._call_agent_api(scenario.system_prompt_context, history, user_prompt)
            
            agent_ts = self._get_current_ms()
            transcript.append(ConversationTurn(
                role="agent", 
                content=agent_response,
                timestamp_ms=agent_ts,
                tool_calls=tool_calls
            ))
            history.append({"role": "agent", "content": agent_response})
            logger.info(f"Turn {i+1} | Latency: {agent_ts - user_ts}ms | User: {user_prompt[:30]}... | Agent: {agent_response[:30]}...")
            
        logger.info(f"Live simulation complete for scenario: {scenario.scenario_id}. Total turns: {len(transcript)}")
        return transcript
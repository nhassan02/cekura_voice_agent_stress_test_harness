#==============================================================================
# FILE: src/core/judge.py
# RESPONSIBILITY: Execute LLM-as-a-Judge evaluation using strict Pydantic schema enforcement, calibrated for voice-native temporal and tool-execution metrics.
# INVARIANT: The LLM output will always conform to the EvaluationRubric schema or raise an exception.
#==============================================================================
import json
import logging
from typing import List, Dict, Any
from pydantic import BaseModel, Field, ValidationError
from google import genai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config.settings import settings

logger = logging.getLogger(__name__)

# Expand the rubric to measure the physics of voice AI, not just the semantics.
class EvaluationRubric(BaseModel):
    accuracy: int = Field(..., ge=1, le=5, description="Factual correctness and completeness of the response.")
    tool_adherence: int = Field(..., ge=1, le=5, description="Strict grounding in tool outputs; zero hallucination of API data.")
    interruption_compliance: int = Field(..., ge=1, le=5, description="Ability to yield the floor immediately upon user barge-in.")
    tone_adaptation: int = Field(..., ge=1, le=5, description="Matching the user's emotional state and maintaining conversational filler during latency.")
    reasoning_chain: str = Field(..., description="Step-by-step forensic justification for the assigned scores, citing timestamps and tool states.")

class LLMJudge:
    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise ValueError("FATAL: GEMINI_API_KEY is empty or missing.")
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = "gemini-3.1-flash-lite" 
        logger.info(f"LLMJudge initialized with {self.model}. Voice-native evaluation engine active.")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception)
    )
    def grade_turn(self, transcript: List[Dict[str, Any]], scenario_context: str) -> EvaluationRubric:
        # Force the LLM to evaluate temporal metadata and tool states.
        prompt = f"""
        You are a forensic evaluator for AI voice agents. Grade the agent's performance based on a specific edge case scenario.
        Voice AI is bound by time, latency, and state interruptions. Evaluate the temporal metadata (timestamps, interrupts) and tool execution states, not just the text.
        
        SCENARIO CONTEXT:
        {scenario_context}
        
        CONVERSATION TRANSCRIPT (with temporal and tool metadata):
        {json.dumps(transcript, indent=2)}
        
        INSTRUCTIONS:
        Grade the agent on a scale of 1 to 5 for:
        1. accuracy: Factual correctness.
        2. tool_adherence: Did it hallucinate tool data? Did it use filler words during tool latency?
        3. interruption_compliance: Did it yield the floor immediately upon a barge-in (is_interrupt: true)?
        4. tone_adaptation: Emotional matching and conversational flow.
        
        Provide a concise, forensic reasoning_chain citing specific timestamps and tool states.
        Return ONLY valid JSON matching this exact structure:
        {{
            "accuracy": <int 1-5>,
            "tool_adherence": <int 1-5>,
            "interruption_compliance": <int 1-5>,
            "tone_adaptation": <int 1-5>,
            "reasoning_chain": "<string>"
        }}
        """
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config={
                    "temperature": 0.0,
                    "response_mime_type": "application/json"
                }
            )
            raw_json = response.text
            if raw_json.startswith("```json"):
                raw_json = raw_json[7:-3]
            elif raw_json.startswith("```"):
                raw_json = raw_json[3:-3]
                
            parsed_data = json.loads(raw_json)
            rubric = EvaluationRubric(**parsed_data)
            logger.info(f"Judging complete. Scores -> Acc: {rubric.accuracy}, Tool: {rubric.tool_adherence}, Int: {rubric.interruption_compliance}, Tone: {rubric.tone_adaptation}")
            return rubric
        except ValidationError as e:
            logger.error(f"FATAL: Gemini output failed Pydantic validation. Error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"FATAL: Gemini API call failed. Error: {str(e)}")
            raise
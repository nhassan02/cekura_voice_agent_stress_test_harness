# Cekura Voice Agent Stress-Test Harness

Standard evaluation harnesses treat voice AI as sequential text arrays. They are blind to temporal collisions, endpointing latency, and state degradation. This harness evaluates voice agents as temporal state machines. It enforces Pydantic schemas that capture wall-clock timestamps, barge-in interrupt flags, and tool-execution traces.

## The Physics of Voice

Voice is bound by time and hardware constraints. If an agent takes 800ms to respond, the user speaks over it. If a database times out, the LLM must use conversational filler or it hallucinates state. This harness tests four immutable failure modes:

1. Multi-Intent Decomposition: Context overflow dropping secondary intents.
2. Identity Hallucination: Persona degradation under context window limits.
3. Tool Grounding: Fabricating reality during API timeouts.
4. Barge-In Compliance: Failing to yield the floor within a 300ms acoustic overlap.

## Architecture

- `src/core/scenarios.py`: Pydantic models enforcing temporal metadata and edge-case definitions.
- `src/adapters/mock_agent.py`: Deterministic failure injection for zero-cost pipeline validation.
- `src/adapters/voice_api.py`: Stochastic API integration capturing real-world wall-clock latency.
- `src/core/judge.py`: LLM-as-a-Judge forensic auditor calibrated to penalize temporal and state violations.
- `src/engine/runner.py`: Orchestration engine guaranteeing payload completeness across the serialization boundary.
- `src/reporting/forensic_log.py`: Telemetry exhaust generating machine-readable and human-readable artifacts.

## Telemetry Exhaust

The harness does not output logs. It outputs observability primitives.

- `JSON`: Lossless state dump for CI/CD gating and pipeline ingestion.
- `CSV`: Flattened temporal metrics for direct ingestion into Datadog, Grafana, or Pandas.
- `Markdown`: Executive summary mapping expected failure modes to observed physics violations.

## Execution

Requires Python 3.10+ and a valid `GEMINI_API_KEY` in `config/settings.py`.

Run deterministic failure injection:

python main.py --real

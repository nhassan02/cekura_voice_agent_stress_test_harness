#==============================================================================
# FILE: src/reporting/forensic_log.py
# RESPONSIBILITY: Generate structured JSON, Markdown, and CSV forensic reports calibrated for voice-native temporal physics and tool-execution traces.
# INVARIANT: Every report must losslessly reflect the Pydantic schema, exposing temporal metrics for direct ingestion into observability dashboards.
#==============================================================================
import json
import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from rich.console import Console
from config.settings import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
console = Console()

class ScenarioForensicReport(BaseModel):
    scenario_id: str
    category: str
    status: str
    execution_timestamp: str
    transcript: List[Dict[str, Any]]
    evaluation_scores: Dict[str, int]
    reasoning_chain: str
    expected_failure_mode: str
    actual_failure_observed: str
    severity_rating: str = Field(..., description="CRITICAL | HIGH | MEDIUM | LOW")
    remediation_recommendation: str
    temporal_metrics: Dict[str, Any] = Field(default_factory=dict)

class HarnessForensicReport(BaseModel):
    report_id: str
    suite_name: str
    generation_timestamp: str
    total_scenarios: int
    success_count: int
    failure_count: int
    overall_health_score: float = Field(..., ge=0.0, le=5.0)
    scenario_reports: List[ScenarioForensicReport]
    executive_summary: str
    critical_findings: List[str]
    architecture_recommendations: List[str]

class ForensicReportGenerator:
    def __init__(self, output_dir: str = "outputs"):
        self.output_dir = Path(output_dir)
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"ForensicReportGenerator initialized. Output directory: {self.output_dir.absolute()}")
        except Exception as e:
            logger.error(f"FATAL: Cannot create output directory {self.output_dir}. Error: {str(e)}")
            raise

    def _extract_temporal_metrics(self, transcript: List[Dict[str, Any]]) -> Dict[str, Any]:
        # Extract physics-level metrics from the transcript to feed observability dashboards.
        metrics = {
            "total_duration_ms": 0,
            "barge_in_events": 0,
            "tool_calls_executed": 0,
            "tool_timeouts": 0,
            "avg_agent_latency_ms": 0
        }
        if not transcript:
            return metrics
            
        agent_latencies = []
        last_user_ts = 0
        
        for turn in transcript:
            ts = turn.get("timestamp_ms", 0)
            if turn["role"] == "user":
                if turn.get("is_interrupt", False):
                    metrics["barge_in_events"] += 1
                last_user_ts = ts
            elif turn["role"] == "agent":
                if last_user_ts > 0:
                    agent_latencies.append(ts - last_user_ts)
                tools = turn.get("tool_calls") or []
                metrics["tool_calls_executed"] += len(tools)
                for tool in tools:
                    if tool.get("status") == "timeout":
                        metrics["tool_timeouts"] += 1
                        
        if transcript:
            metrics["total_duration_ms"] = transcript[-1].get("timestamp_ms", 0)
        if agent_latencies:
            metrics["avg_agent_latency_ms"] = sum(agent_latencies) // len(agent_latencies)
            
        return metrics

    def _calculate_severity(self, scores: Dict[str, int]) -> str:
        # Voice AI severity is heavily penalized by tool hallucinations and barge-in failures.
        if not scores:
            return "CRITICAL"
        avg_score = sum(scores.values()) / len(scores.values())
        tool_score = scores.get("tool_adherence", 5)
        interrupt_score = scores.get("interruption_compliance", 5)
        
        if tool_score <= 2 or interrupt_score <= 2 or avg_score <= 2.0:
            return "CRITICAL"
        elif avg_score <= 3.0:
            return "HIGH"
        elif avg_score <= 4.0:
            return "MEDIUM"
        else:
            return "LOW"

    def _generate_remediation(self, report: 'ScenarioForensicReport') -> str:
        # Prescribe infrastructure fixes, not just prompt tweaks.
        recs = []
        if "multi_intent" in report.category.lower():
            recs.append("Implement NLU intent decomposition and independent state tracking for compound requests.")
        if "identity" in report.category.lower():
            recs.append("Externalize persona state to a persistent key-value store to prevent context-window degradation.")
        if report.evaluation_scores.get("interruption_compliance", 5) <= 2:
            recs.append("CRITICAL: Implement server-side Voice Activity Detection (VAD) with <300ms barge-in cutoff.")
        if report.evaluation_scores.get("tool_adherence", 5) <= 2:
            recs.append("CRITICAL: Enforce strict tool-output grounding. Block LLM generation if tool status is 'timeout' or 'failed'.")
        
        return "\n".join(f"- {r}" for r in recs) if recs else "- No critical remediation actions required."

    def _determine_actual_failure(self, transcript: List[Dict[str, Any]], scores: Dict[str, int]) -> str:
        if not transcript:
            return "No transcript available for analysis."
            
        last_agent_response = ""
        for turn in reversed(transcript):
            if turn["role"] == "agent":
                last_agent_response = turn.get("content", "")
                break
                
        if scores.get("tool_adherence", 5) <= 2:
            return f"Agent hallucinated tool data or failed to yield during timeout. Response: '{last_agent_response[:80]}...'"
        if scores.get("interruption_compliance", 5) <= 2:
            return f"Agent failed to yield floor during barge-in event. Response: '{last_agent_response[:80]}...'"
        if scores.get("accuracy", 5) <= 2:
            return f"Agent provided factually incorrect response: '{last_agent_response[:80]}...'"
            
        return "Agent performance degraded but maintained basic physics and semantic functionality."

    def generate_scenario_report(self, scenario_data: Dict[str, Any]) -> ScenarioForensicReport:
        try:
            scores = scenario_data.get("evaluation", {})
            if not scores:
                scores = {"accuracy": 0, "tool_adherence": 0, "interruption_compliance": 0, "tone_adaptation": 0}
                
            integer_metrics = {k: v for k, v in scores.items() if isinstance(v, int)}
            transcript = scenario_data.get("transcript", [])
            temporal_metrics = self._extract_temporal_metrics(transcript)
            
            report = ScenarioForensicReport(
                scenario_id=scenario_data["scenario_id"],
                category=scenario_data["category"],
                status=scenario_data["status"],
                execution_timestamp=datetime.utcnow().isoformat() + "Z",
                transcript=transcript,
                evaluation_scores={
                    "accuracy": integer_metrics.get("accuracy", 0),
                    "tool_adherence": integer_metrics.get("tool_adherence", 0),
                    "interruption_compliance": integer_metrics.get("interruption_compliance", 0),
                    "tone_adaptation": integer_metrics.get("tone_adaptation", 0)
                },
                reasoning_chain=scores.get("reasoning_chain", "No reasoning chain available"),
                expected_failure_mode=scenario_data.get("expected_failure_mode", "Unknown"),
                actual_failure_observed="",
                severity_rating="LOW",
                remediation_recommendation="",
                temporal_metrics=temporal_metrics
            )
            
            report.actual_failure_observed = self._determine_actual_failure(transcript, integer_metrics)
            report.severity_rating = self._calculate_severity(integer_metrics)
            report.remediation_recommendation = self._generate_remediation(report)
            
            logger.info(f"Generated forensic report for {report.scenario_id}. Severity: {report.severity_rating}")
            return report
        except Exception as e:
            logger.error(f"FATAL: Scenario report generation failed. Error: {str(e)}")
            raise

    def generate_suite_report(self, results: List[Dict[str, Any]], suite_name: str = "Cekura Edge Case Suite") -> HarnessForensicReport:
        try:
            scenario_reports = []
            critical_findings = []
            total_score = 0.0
            success_count = 0
            
            for result in results:
                report = self.generate_scenario_report(result)
                scenario_reports.append(report)
                if report.status == "SUCCESS":
                    success_count += 1
                    avg_score = sum(report.evaluation_scores.values()) / len(report.evaluation_scores.values())
                    total_score += avg_score
                if report.severity_rating in ["CRITICAL", "HIGH"]:
                    critical_findings.append(
                        f"[{report.scenario_id}] {report.actual_failure_observed} (Severity: {report.severity_rating})"
                    )
                    
            failure_count = len(results) - success_count
            overall_health = total_score / len(results) if results else 0.0
            
            executive_summary = (
                f"Evaluated {len(results)} voice-native edge cases. "
                f"{success_count} passed, {failure_count} failed. "
                f"Overall system health: {overall_health:.2f}/5.0. "
                f"{len(critical_findings)} critical physics or semantic failures detected."
            )
            
            architecture_recommendations = [
                "Deploy server-side VAD with <300ms barge-in cutoff to resolve interruption non-compliance.",
                "Implement strict tool-output grounding gates to block LLM generation during API timeouts.",
                "Externalize persona state to persistent storage to survive context-window degradation.",
                "Integrate this harness into CI/CD to block deployments on CRITICAL severity findings."
            ]
            
            report = HarnessForensicReport(
                report_id=f"cekura_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                suite_name=suite_name,
                generation_timestamp=datetime.utcnow().isoformat() + "Z",
                total_scenarios=len(results),
                success_count=success_count,
                failure_count=failure_count,
                overall_health_score=overall_health,
                scenario_reports=scenario_reports,
                executive_summary=executive_summary,
                critical_findings=critical_findings,
                architecture_recommendations=architecture_recommendations
            )
            
            logger.info(f"Generated suite report. ID: {report.report_id}. Health: {report.overall_health_score:.2f}")
            return report
        except Exception as e:
            logger.error(f"FATAL: Suite report generation failed. Error: {str(e)}")
            raise

    def save_json_report(self, report: HarnessForensicReport, filename: Optional[str] = None) -> Path:
        try:
            filename = filename or f"{report.report_id}_forensic.json"
            output_path = self.output_dir / filename
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report.model_dump(), f, indent=2, ensure_ascii=False)
            logger.info(f"JSON report saved: {output_path.absolute()}")
            return output_path
        except Exception as e:
            logger.error(f"FATAL: JSON save failed. Error: {str(e)}")
            raise

    def save_metrics_csv(self, report: HarnessForensicReport, filename: Optional[str] = None) -> Path:
        # Flat CSV for direct ingestion into Datadog, Grafana, or Pandas.
        try:
            filename = filename or f"{report.report_id}_metrics.csv"
            output_path = self.output_dir / filename
            
            headers = [
                "scenario_id", "category", "status", "severity",
                "accuracy", "tool_adherence", "interruption_compliance", "tone_adaptation",
                "total_duration_ms", "barge_in_events", "tool_timeouts", "avg_agent_latency_ms"
            ]
            
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                for sc in report.scenario_reports:
                    writer.writerow({
                        "scenario_id": sc.scenario_id,
                        "category": sc.category,
                        "status": sc.status,
                        "severity": sc.severity_rating,
                        "accuracy": sc.evaluation_scores.get("accuracy", 0),
                        "tool_adherence": sc.evaluation_scores.get("tool_adherence", 0),
                        "interruption_compliance": sc.evaluation_scores.get("interruption_compliance", 0),
                        "tone_adaptation": sc.evaluation_scores.get("tone_adaptation", 0),
                        "total_duration_ms": sc.temporal_metrics.get("total_duration_ms", 0),
                        "barge_in_events": sc.temporal_metrics.get("barge_in_events", 0),
                        "tool_timeouts": sc.temporal_metrics.get("tool_timeouts", 0),
                        "avg_agent_latency_ms": sc.temporal_metrics.get("avg_agent_latency_ms", 0)
                    })
            logger.info(f"CSV metrics saved: {output_path.absolute()}")
            return output_path
        except Exception as e:
            logger.error(f"FATAL: CSV save failed. Error: {str(e)}")
            raise

    def save_markdown_report(self, report: HarnessForensicReport, filename: Optional[str] = None) -> Path:
        try:
            filename = filename or f"{report.report_id}_forensic.md"
            output_path = self.output_dir / filename
            
            md = f"# Cekura Voice AI Forensic Telemetry\n"
            md += f"**Report ID:** `{report.report_id}` | **Generated:** {report.generation_timestamp}\n\n"
            md += f"## Executive Summary\n{report.executive_summary}\n\n"
            
            md += "## System Health Overview\n"
            md += "| Metric | Value |\n|---|---|\n"
            md += f"| Total Scenarios | {report.total_scenarios} |\n"
            md += f"| Passed / Failed | {report.success_count} / {report.failure_count} |\n"
            md += f"| Overall Health | **{report.overall_health_score:.2f} / 5.0** |\n"
            md += f"| Critical Findings | {len(report.critical_findings)} |\n\n"
            
            if report.critical_findings:
                md += "## Critical Findings\n"
                for i, finding in enumerate(report.critical_findings, 1):
                    md += f"{i}. {finding}\n"
                md += "\n"
                
            md += "## Scenario Telemetry\n"
            for sc in report.scenario_reports:
                status_icon = "✅" if sc.status == "SUCCESS" else "❌"
                md += f"### {status_icon} {sc.scenario_id} ({sc.category})\n"
                md += f"**Severity:** `{sc.severity_rating}` | **Status:** {sc.status}\n\n"
                
                md += "#### Evaluation Scores\n"
                md += "| Dimension | Score (1-5) |\n|---|---|\n"
                md += f"| Accuracy | {sc.evaluation_scores.get('accuracy', 'N/A')} |\n"
                md += f"| Tool Adherence | {sc.evaluation_scores.get('tool_adherence', 'N/A')} |\n"
                md += f"| Interrupt Compliance | {sc.evaluation_scores.get('interruption_compliance', 'N/A')} |\n"
                md += f"| Tone Adaptation | {sc.evaluation_scores.get('tone_adaptation', 'N/A')} |\n\n"
                
                md += "#### Temporal & State Physics\n"
                tm = sc.temporal_metrics
                md += f"- **Total Duration:** {tm.get('total_duration_ms', 0)}ms\n"
                md += f"- **Avg Agent Latency:** {tm.get('avg_agent_latency_ms', 0)}ms\n"
                md += f"- **Barge-in Events:** {tm.get('barge_in_events', 0)}\n"
                md += f"- **Tool Timeouts:** {tm.get('tool_timeouts', 0)}\n\n"
                
                md += f"**Expected Failure:** {sc.expected_failure_mode}\n"
                md += f"**Observed Failure:** {sc.actual_failure_observed}\n\n"
                md += f"**Judge Reasoning:** {sc.reasoning_chain}\n\n"
                md += f"**Remediation:**\n{sc.remediation_recommendation}\n\n"
                md += "---\n\n"
                
            md += "## Architecture Recommendations\n"
            for i, rec in enumerate(report.architecture_recommendations, 1):
                md += f"{i}. {rec}\n"
                
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(md)
            logger.info(f"Markdown report saved: {output_path.absolute()}")
            return output_path
        except Exception as e:
            logger.error(f"FATAL: Markdown save failed. Error: {str(e)}")
            raise

    def generate_and_save_all(self, results: List[Dict[str, Any]]) -> tuple[Path, Path, Path]:
        suite_report = self.generate_suite_report(results)
        json_path = self.save_json_report(suite_report)
        csv_path = self.save_metrics_csv(suite_report)
        md_path = self.save_markdown_report(suite_report)
        return json_path, csv_path, md_path
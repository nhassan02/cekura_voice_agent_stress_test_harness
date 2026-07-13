#==============================================================================
# FILE: src/engine/runner.py
# RESPONSIBILITY: Orchestrate the execution pipeline and guarantee payload completeness for downstream forensic analysis.
# INVARIANT: The result payload must carry both the generated physics and the initial scenario constraints.
#==============================================================================
import sys
import logging
from typing import List, Dict, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from src.core.scenarios import CEKURA_EDGE_CASE_SUITE, ScenarioDefinition, ConversationTurn
from src.core.judge import LLMJudge, EvaluationRubric
from src.adapters.mock_agent import MockVoiceAgent
from src.adapters.voice_api import RealVoiceAgentAdapter
from src.reporting.forensic_log import ForensicReportGenerator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
console = Console()

class EvaluationHarness:
    def __init__(self, use_real_agent: bool = False):
        self.judge = LLMJudge()
        if use_real_agent:
            self.agent = RealVoiceAgentAdapter()
            console.print("[bold yellow]Mode: REAL AGENT (Stochastic API Integration)[/bold yellow]")
        else:
            self.agent = MockVoiceAgent()
            console.print("[bold cyan]Mode: MOCK AGENT (Deterministic Failure Injection)[/bold cyan]")
            
        self.results: List[Dict[str, Any]] = []
        self.report_generator = ForensicReportGenerator(output_dir="outputs")

    def _serialize_transcript(self, transcript: List[ConversationTurn]) -> List[Dict[str, Any]]:
        return [turn.model_dump() for turn in transcript]

    def run_scenario(self, scenario: ScenarioDefinition) -> Dict[str, Any]:
        console.print(f"\n[bold cyan]▶ Executing Scenario:[/bold cyan] {scenario.scenario_id} | {scenario.category.value}")
        
        # Inject the expected_failure_mode directly into the payload. This ensures the forensic report can measure the delta between expectation and reality.
        result_payload = {
            "scenario_id": scenario.scenario_id,
            "category": scenario.category.value,
            "expected_failure_mode": scenario.expected_failure_mode,
            "status": "PENDING",
            "transcript": [],
            "evaluation": None,
            "error": None
        }
        try:
            transcript = self.agent.simulate_conversation(scenario)
            result_payload["transcript"] = self._serialize_transcript(transcript)
            
            scenario_context = f"Description: {scenario.description}\nSystem Prompt: {scenario.system_prompt_context}\nExpected Failure: {scenario.expected_failure_mode}"
            rubric = self.judge.grade_turn(result_payload["transcript"], scenario_context)
            
            result_payload["evaluation"] = rubric.model_dump()
            result_payload["status"] = "SUCCESS"
            console.print(f"[bold green]✔ Scenario Complete.[/bold green] Acc: {rubric.accuracy} | Tool: {rubric.tool_adherence} | Int: {rubric.interruption_compliance}")
        except Exception as e:
            logger.error(f"Scenario {scenario.scenario_id} failed during execution. Error: {str(e)}")
            result_payload["status"] = "FAILED"
            result_payload["error"] = str(e)
            console.print(f"[bold red]✘ Scenario Failed.[/bold red] Error logged.")
            
        return result_payload

    def run_suite(self):
        console.print(Panel.fit("[bold white]CEKURA EDGE CASE STRESS-TEST HARNESS[/bold white]\nInitializing fault-tolerant execution pipeline...", border_style="blue"))
        for scenario in CEKURA_EDGE_CASE_SUITE.scenarios:
            result = self.run_scenario(scenario)
            self.results.append(result)
            
        self._generate_summary_table()
        
        try:
            console.print("\n[bold yellow]Generating forensic artifacts...[/bold yellow]")
            json_path, csv_path, md_path = self.report_generator.generate_and_save_all(self.results)
            console.print(f"[bold green]✓ Artifacts persisted. JSON: {json_path} | CSV: {csv_path} | MD: {md_path}[/bold green]")
        except Exception as e:
            logger.error(f"FATAL: Forensic report generation failed. Error: {str(e)}")
            console.print(f"[bold red]✘ Report generation failed. Check logs.[/bold red]")

    def _generate_summary_table(self):
        table = Table(title="Forensic Evaluation Summary", show_lines=True)
        table.add_column("Scenario ID", style="cyan")
        table.add_column("Category", style="magenta")
        table.add_column("Status", justify="center")
        table.add_column("Accuracy", justify="right")
        table.add_column("Tool Adherence", justify="right")
        table.add_column("Interrupt Comp.", justify="right")
        table.add_column("Tone", justify="right")
        
        for res in self.results:
            status_str = f"[green]{res['status']}[/green]" if res['status'] == 'SUCCESS' else f"[red]{res['status']}[/red]"
            if res['evaluation']:
                eval_data = res['evaluation']
                table.add_row(
                    res['scenario_id'], 
                    res['category'], 
                    status_str,
                    str(eval_data['accuracy']),
                    str(eval_data['tool_adherence']),
                    str(eval_data['interruption_compliance']),
                    str(eval_data['tone_adaptation'])
                )
            else:
                table.add_row(res['scenario_id'], res['category'], status_str, "-", "-", "-", "-")
                
        console.print("\n")
        console.print(table)

if __name__ == "__main__":
    use_real = "--real" in sys.argv
    harness = EvaluationHarness(use_real_agent=use_real)
    harness.run_suite()
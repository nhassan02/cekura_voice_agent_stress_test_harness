#==============================================================================
#节点 NODE: Tracer-16
#文件 FILE: main.py
#组件 COMPONENT: CLI
#职责 RESPONSIBILITY: The physical entry point. Validate execution environment, parse CLI arguments, and inject the execution mode into the harness.
#不变量 INVARIANT: The application must correctly route execution flags and guarantee module resolution regardless of the repository clone name.
#失效模式 FAILURE MODE: Brittle directory name checks cause immediate crashes when the repository is cloned under a different name.
#原典 PRIMORDIAL: Python sys.argv parsing, Twelve-Factor App (Config).
#债务分类 DEBT TYPE: Execution Context
#==============================================================================
import sys
import os
from pathlib import Path
from rich.console import Console

# WHY: [Forensic Error Handling] We enforce structural invariants rather than brittle directory names.
# The repository might be cloned as 'cekura-harness' or 'teo-voice-ai'. We check for the existence of core directories.
REQUIRED_DIRS = ["src", "config"]
current_dir = Path.cwd()

if not all((current_dir / d).is_dir() for d in REQUIRED_DIRS):
    print("FATAL: main.py must be executed from the project root (where 'src/' and 'config/' reside).")
    sys.exit(1)

# WHY: [Data as Evidence] Guarantee module resolution regardless of how the script is invoked.
sys.path.insert(0, str(current_dir))

from src.engine.runner import EvaluationHarness

console = Console()

def main():
    # WHY: [Domain Adaptation] We intercept the help flag to provide immediate operational clarity.
    if "--help" in sys.argv or "-h" in sys.argv:
        console.print("[bold cyan]Cekura Voice Agent Stress-Test Harness[/bold cyan]")
        console.print("Usage: python main.py [OPTIONS]")
        console.print("Options:")
        console.print("  --real    Use the stochastic RealVoiceAgentAdapter (Gemini API) instead of the deterministic MockVoiceAgent.")
        console.print("  --help    Show this help message and exit.")
        sys.exit(0)

    use_real_agent = "--real" in sys.argv
    
    if use_real_agent:
        console.print("[bold yellow]Mode: REAL AGENT (Stochastic API Integration)[/bold yellow]")
    else:
        console.print("[bold cyan]Mode: MOCK AGENT (Deterministic Failure Injection)[/bold cyan]")

    console.print("[bold green]Initializing Cekura Voice Agent Stress-Test Harness...[/bold green]")
    
    # WHY: [Proof is King] We inject the boolean flag into the harness constructor.
    harness = EvaluationHarness(use_real_agent=use_real_agent)
    harness.run_suite()

if __name__ == "__main__":
    main()
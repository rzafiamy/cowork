import asyncio
import click
from rich.console import Console

console = Console()

from core import EvalCore
from data import TEST_CASES

@click.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.option('--report/--no-report', default=True, help="Generate Excel Evaluation Report")
@click.option('--out', default='evaluation_report.xlsx', help="Filename for the report output")
def main(report, out):
    """
    Cowork Evaluation CLI 
    
    A rich data-driven test runner validating the agentic loop.
    """
    core = EvalCore()
    
    try:
        results = asyncio.run(core.run_test_suite(TEST_CASES))
        if report:
            core.generate_excel_report(results, out)
    except Exception as e:
        console.print(f"[bold red]❌ Evaluation Error: {str(e)}[/bold red]")

if __name__ == "__main__":
    main()

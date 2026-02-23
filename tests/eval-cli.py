import asyncio
import click
from rich.console import Console

console = Console()

from core import EvalCore
from datasets import TEST_CASES

@click.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.option('--report/--no-report', default=True, help="Generate Excel Evaluation Report")
@click.option('--out', default='evaluation_report.xlsx', help="Filename for the report output")
@click.option('--category', default=None, help="Filter tests by a specific category (e.g., 'Coding')")
@click.option('--list-categories', is_flag=True, help="List all available test categories and exit")
def main(report, out, category, list_categories):
    """
    Cowork Evaluation CLI 
    
    A rich data-driven test runner validating the agentic loop.
    """
    if list_categories:
        categories = sorted(list(set(tc['category'] for tc in TEST_CASES)))
        console.print("[bold cyan]Available Test Categories:[/bold cyan]")
        for c in categories:
            count = len([tc for tc in TEST_CASES if tc['category'] == c])
            console.print(f"  • {c} [dim]({count} tests)[/dim]")
        return

    core = EvalCore()
    
    tests_to_run = TEST_CASES
    if category:
        tests_to_run = [tc for tc in TEST_CASES if category.lower() in tc['category'].lower()]
        console.print(f"[bold blue]Running {len(tests_to_run)} tests for category: '{category}'[/bold blue]")
        if not tests_to_run:
            console.print("[bold red]No tests found for this category![/bold red]")
            return
            
    try:
        results = asyncio.run(core.run_test_suite(tests_to_run))
        if report:
            core.generate_excel_report(results, out)
    except Exception as e:
        console.print(f"[bold red]❌ Evaluation Error: {str(e)}[/bold red]")

if __name__ == "__main__":
    main()

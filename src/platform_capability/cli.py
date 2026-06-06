import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
def cli():
    """Platform Capability Intelligence CLI"""


@cli.command()
@click.option("--manifest", "-m", required=True, help="Path to scan_manifest.yaml")
@click.option("--catalog", "-c", required=True, help="Path to catalog.yaml")
@click.option("--output", "-o", default="./output", help="Output directory")
def scan(manifest: str, catalog: str, output: str):
    """Run a cross-repo capability scan."""
    from platform_capability.pipeline.scan_pipeline import run_scan
    import json, time

    console.print(f"\n[bold blue]Platform Capability Intelligence[/bold blue]")
    console.print(f"Manifest : {manifest}")
    console.print(f"Catalog  : {catalog}")
    console.print(f"Output   : {output}\n")

    t0 = time.time()
    console.print("[yellow]Running scan...[/yellow]")
    report_path = run_scan(manifest, catalog, output)
    elapsed = time.time() - t0

    # Load and display summary
    with open(report_path) as f:
        report = json.load(f)

    console.print(f"\n[green]✓ Scan complete[/green] ({elapsed:.1f}s)")
    console.print(f"Report: {report_path}\n")

    # Results table
    table = Table(title="Detection Results", show_header=True)
    table.add_column("Repo", style="cyan")
    table.add_column("Tenant")
    table.add_column("Capability")
    table.add_column("Status", style="bold")
    table.add_column("Confidence")

    status_colors = {
        "ADOPTED": "green",
        "CUSTOM_IMPLEMENTATION": "yellow",
        "MISSING": "orange3",
        "NOT_ELIGIBLE": "dim",
        "UNKNOWN": "blue",
        "EXEMPT": "cyan",
    }

    for r in report["detection_results"]:
        status = r["status"]
        color = status_colors.get(status, "white")
        table.add_row(
            r["repo_id"],
            r["tenant_id"],
            r["capability_id"],
            f"[{color}]{status}[/{color}]",
            r["confidence"],
        )
    console.print(table)

    # Metrics
    for m in report["metrics"]:
        console.print(f"\n[bold]Capability: {m['capability_id']}[/bold]")
        console.print(f"  Eligible repos   : {m['eligible_repo_count']}")
        console.print(f"  Adopted          : {m['adopted_count']}")
        console.print(f"  Custom impl      : {m['custom_implementation_count']}")
        console.print(f"  Missing          : {m['missing_count']}")
        console.print(f"  Unknown          : {m['unknown_count']}")
        console.print(f"  Adoption rate    : {m['adoption_rate']*100:.0f}%")

    # LLM insight
    if report.get("insights"):
        console.print(f"\n[bold]Platform Insight[/bold]")
        console.print(report["insights"]["insight_summary"])
        recs = report["insights"].get("recommendations", [])
        if recs:
            console.print(f"\n[bold]Recommendations[/bold]")
            for rec in recs:
                color = "red" if rec["priority"] == "high" else "yellow"
                console.print(f"  [{color}][{rec['priority'].upper()}][/{color}] {rec['target']}: {rec['action']}")


@cli.command()
@click.argument("report_path")
def show(report_path: str):
    """Show a previously generated report."""
    import json
    with open(report_path) as f:
        report = json.load(f)
    console.print_json(json.dumps(report, indent=2))


if __name__ == "__main__":
    cli()

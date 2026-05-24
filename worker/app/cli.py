"""Worker CLI entry point - dispatches named ingestion and maintenance commands."""
import argparse

from worker.app import pipeline
from worker.app.logger import configure_logging


def cmd_noop() -> int:
    """Run a no-op command to verify the worker process starts correctly.

    Returns:
        0 on success.
    """
    print("worker noop complete")
    return 0


def cmd_run_once(dry_run: bool = False) -> int:
    """Execute one scheduled discovery run.

    Searches for grand opening events in Greenville, SC, fetches the result
    pages, normalises and hashes each page, and stores new source documents
    for later extraction in Phase 5.

    Args:
        dry_run: When True, log planned actions without making API or MCP
            calls.

    Returns:
        0 on success, 1 if the run completed with errors (partial/failed).
    """
    summary = pipeline.run_once(dry_run=dry_run)

    m, s = divmod(int(summary.elapsed_seconds), 60)
    elapsed_str = f"{m:02d}:{s:02d}"
    status_label = summary.final_status.upper()

    divider = "=" * 60
    print(divider)
    print(f"  Run {str(summary.run_id)[:8]}...  |  {status_label}")
    print(f"  Queries   : {summary.queries_executed}")
    print(f"  Results   : {summary.search_results_found}")
    print(f"  URLs tried: {summary.urls_attempted}")
    print(f"  New docs  : {summary.source_docs_created}")
    print(f"  Skipped   : {summary.source_docs_skipped}")
    print(f"  Errors    : {summary.fetch_errors}")
    print(f"  LLM pages : {summary.llm_pages_processed}")
    print(f"  Events    : {summary.events_created}")
    print(f"  Irrelevant: {summary.pages_irrelevant}")
    print(f"  Ext errors: {summary.extraction_errors}")
    print(f"  Elapsed   : {elapsed_str}")
    if summary.notes:
        print(f"  Note      : {summary.notes}")
    print(divider)

    if summary.final_status in ("failed", "partial"):
        return 1
    return 0


def main() -> int:
    """Parse CLI arguments and dispatch to the appropriate worker command.

    Returns:
        Integer exit code (0 = success).
    """
    parser = argparse.ArgumentParser(description="Grand Opening Radar worker")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("noop", help="Run no-op worker command")

    run_once_parser = subparsers.add_parser(
        "run_once", help="Execute one scheduled discovery run"
    )
    run_once_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log actions without making API or MCP calls",
    )

    args = parser.parse_args()
    configure_logging(level=args.log_level)

    if args.command == "noop":
        return cmd_noop()

    if args.command == "run_once":
        return cmd_run_once(dry_run=getattr(args, "dry_run", False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


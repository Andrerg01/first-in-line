"""Worker CLI entry point — dispatches named ingestion and maintenance commands."""
import argparse


def cmd_noop() -> int:
    """Run a no-op command to verify the worker process starts correctly.

    Returns:
        0 on success.
    """
    print("worker noop complete")
    return 0


def main() -> int:
    """Parse CLI arguments and dispatch to the appropriate worker command.

    Returns:
        Integer exit code (0 = success).
    """
    parser = argparse.ArgumentParser(description="Grand Opening Radar worker")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("noop", help="Run no-op worker command")

    args = parser.parse_args()

    if args.command == "noop":
        return cmd_noop()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

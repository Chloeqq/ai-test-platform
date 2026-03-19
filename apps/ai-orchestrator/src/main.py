import argparse
import json

from app import create_server
from orchestrator_service import OrchestratorService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Minimal AI orchestrator for test generation and execution")
    subparsers = parser.add_subparsers(dest="command", required=True)

    orchestrate_parser = subparsers.add_parser("orchestrate", help="Generate a YAML test case and optionally execute it")
    orchestrate_parser.add_argument("--page", required=True, help="Target page object name, e.g. product")
    orchestrate_parser.add_argument("--requirement", required=True, help="Natural language requirement")
    orchestrate_parser.add_argument("--execute", action="store_true", help="Execute the generated case with pytest")

    serve_parser = subparsers.add_parser("serve", help="Start a minimal HTTP server")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "orchestrate":
        service = OrchestratorService()
        result = service.orchestrate(
            requirement=args.requirement,
            page=args.page,
            execute=args.execute,
        )
        print(json.dumps(service.serialize_result(result), ensure_ascii=False, indent=2))
        return

    if args.command == "serve":
        server = create_server(host=args.host, port=args.port)
        print(f"AI orchestrator listening on http://{args.host}:{args.port}")
        server.serve_forever()


if __name__ == "__main__":
    main()

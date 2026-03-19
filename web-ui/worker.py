import sys


def main() -> int:
    message = (
        "Worker entrypoint has been removed.\n"
        "The backend now uses FastAPI skeleton only.\n"
        "Use `python -m uvicorn app.main:app --app-dir apps/web-ui-service --host 127.0.0.1 --port 8013`."
    )
    print(message)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

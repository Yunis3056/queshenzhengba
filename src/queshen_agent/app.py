from __future__ import annotations

from .ui import run_app


def main() -> int:
    try:
        return run_app()
    except RuntimeError as exc:
        print(exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

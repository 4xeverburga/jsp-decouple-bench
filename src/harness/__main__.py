"""`python -m src.bench <verb>` — the same line as `python main.py <verb>`."""

import sys

from .cli import main

if __name__ == "__main__":
    main(sys.argv[1:])

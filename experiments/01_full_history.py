import sys

from achdnlp.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["run", "--arms", "A", "--output", "runs/A", *sys.argv[1:]]))

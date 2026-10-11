import sys

from achdnlp.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["run", "--arms", "B", "--output", "runs/B", *sys.argv[1:]]))

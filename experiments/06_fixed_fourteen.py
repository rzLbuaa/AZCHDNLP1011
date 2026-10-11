import sys

from achdnlp.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["run", "--arms", "R14", "--output", "runs/R14", *sys.argv[1:]]))

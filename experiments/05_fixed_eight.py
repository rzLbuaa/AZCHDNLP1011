import sys

from achdnlp.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["run", "--arms", "R8", "--output", "runs/R8", *sys.argv[1:]]))

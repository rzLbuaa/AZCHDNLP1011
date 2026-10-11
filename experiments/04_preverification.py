import sys

from achdnlp.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["run", "--arms", "D", "--output", "runs/D", *sys.argv[1:]]))

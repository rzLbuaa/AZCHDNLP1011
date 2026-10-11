import sys

from achdnlp.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["run", "--arms", "C", "--output", "runs/C", *sys.argv[1:]]))

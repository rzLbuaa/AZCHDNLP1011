import sys

from achdnlp.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["run", "--arms", "ID_ONLY", "--output", "runs/ID_ONLY", *sys.argv[1:]]))

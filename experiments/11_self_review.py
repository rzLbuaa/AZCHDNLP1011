import sys

from achdnlp.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["run", "--arms", "SELF_REVIEW", "--output", "runs/SELF_REVIEW", *sys.argv[1:]]))

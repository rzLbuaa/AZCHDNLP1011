import sys

from achdnlp.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["run", "--arms", "COUNT_MATCHED_GATING", "--output", "runs/COUNT_MATCHED_GATING", *sys.argv[1:]]))

import sys

from achdnlp.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["run", "--arms", "RULES_ONLY", "--output", "runs/RULES_ONLY", *sys.argv[1:]]))

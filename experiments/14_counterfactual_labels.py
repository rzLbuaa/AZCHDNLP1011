import sys

from achdnlp.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["run", "--arms", "CF_LABELS", "--output", "runs/CF_LABELS", *sys.argv[1:]]))

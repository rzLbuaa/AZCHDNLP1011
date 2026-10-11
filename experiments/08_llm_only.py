import sys

from achdnlp.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["run", "--arms", "LLM_ONLY", "--output", "runs/LLM_ONLY", *sys.argv[1:]]))

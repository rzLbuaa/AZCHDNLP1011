import sys

from achdnlp.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["run", "--arms", "TEXT_RAG", "--output", "runs/TEXT_RAG", *sys.argv[1:]]))

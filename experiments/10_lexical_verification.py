import sys

from achdnlp.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["run", "--arms", "LEXICAL_VERIFICATION", "--output", "runs/LEXICAL_VERIFICATION", *sys.argv[1:]]))

import argparse
import json

from achdnlp.statistics import paired_binary


def main():
    parser = argparse.ArgumentParser(description="Paired binary inference from observed joint counts")
    parser.add_argument("counts", nargs=4, type=int, metavar="N")
    parser.add_argument("--resamples", type=int, default=100000)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    print(json.dumps(paired_binary(args.counts, resamples=args.resamples, seed=args.seed), indent=2))


if __name__ == "__main__":
    main()

import os.path
import argparse
from teapot import scorers
from teapot import utils


def get_args():
    parser = argparse.ArgumentParser("")
    parser.add_argument(
        "--score",
        default="chrf",
        type=str,
        help="Score to evaluate semantic similarity "
        f"(choose from: {', '.join(list(scorers.scorers.keys()))})",
    )
    parser.add_argument(
        "--src",
        default=None,
        type=str,
        help="Original source",
    )
    parser.add_argument(
        "--adv-src",
        default=None,
        type=str,
        help="Adversarial perturbation of the source",
    )
    parser.add_argument(
        "--ref",
        default=None,
        type=str,
        help="Reference output",
    )
    parser.add_argument(
        "--out",
        default=None,
        type=str,
        help="Model output on the original source",
    )
    parser.add_argument(
        "--adv-out",
        default=None,
        type=str,
        help="Model output on the adversarial source",
    )
    parser.add_argument(
        "--src-lang",
        default=None,
        type=str,
        help="Source language. This is mostly used for Meteor, in which case"
        " choose one from: en, cz, de, es, fr, ar, da, fi, hu, it, nl, no,"
        " pt, ro, ru, se, tr",
    )
    parser.add_argument(
        "--tgt-lang",
        default=None,
        type=str,
        help="Target language. This is mostly used for Meteor, in which case"
        " choose one from: en, cz, de, es, fr, ar, da, fi, hu, it, nl, no,"
        " pt, ro, ru, se, tr",
    )
    parser.add_argument(
        "--scale",
        default=100,
        type=float,
        help="Scale for the scores.",
    )
    parser.add_argument(
        "--terse",
        action="store_true",
        help="Only output average scores, one on each line "
        "(for use in bash scripts)"
    )
    parser.add_argument(
        "--custom-scores-source",
        nargs="*",
        type=str,
        default=[],
        help="Path to python files containing custom scorers implementation"
    )

    args, _ = parser.parse_known_args()
    # Check arguments
    source_side = args.src is not None and args.adv_src is not None
    target_side = (
        args.ref is not None and
        args.out is not None and
        args.adv_out is not None
    )
    if not (source_side or target_side):
        raise ValueError(
            "You need to specify at lease `--src` and `--adv-src` "
            "(for source side evaluation) OR `--ref`, `--out` and `--adv-out`"
            " (for target side evaluation)"
        )
    # Check file existence
    for name in ["src", "adv_src", "ref", "out", "adv_out"]:
        filename = getattr(args, name, None)
        if filename is not None and not os.path.isfile(filename):
            raise ValueError(
                f"Specified file for \"{name}\" (\"{filename}\")"
                " does not exist"
            )
    # Load custom scorers source
    for source_file in args.custom_scores_source:
        path = os.path.abspath(source_file)
        if not os.path.isfile(path):
            raise ValueError(
                f"Can't find custom scorer source file \"{path}\""
            )
        scorers.read_custom_scorers_source(path)
    # Add scorer specific args
    scorer_class = scorers.get_scorer_class(args.score)
    # Parse again with scorer specific args
    scorer_class.add_args(parser)
    args = parser.parse_args()
    return args, source_side, target_side


def main():
    # Command line args
    args, source_side, target_side = get_args()
    scale = args.scale
    # Scorer
    scorer = scorers.scorer_from_args(args)
    # Source side eval
    N = None
    if source_side:
        # Source score (s_src in the paper)
        s_src = scorer.score(
            utils.loadtxt(args.adv_src),
            utils.loadtxt(args.src),
            lang=args.src_lang,
        )
        # statistics
        N = len(s_src)
        s_src_avg, s_src_std, s_src_5, s_src_95 = utils.stats(s_src)
        # Print stats
        if args.terse:
            print(f"{s_src_avg*scale:.3f}")
        else:
            print(f"Source side preservation ({scorer.name}):")
            print(f"Mean:\t{s_src_avg*scale:.3f}")
            print(f"Std:\t{s_src_std*scale:.3f}")
            print(f"5%-95%:\t{s_src_5*scale:.3f}-{s_src_95*scale:.3f}")

    # Target side eval
    if target_side:
        # target relative decrease in score (d_tgt in the paper)
        d_tgt = scorer.rd_score(
            utils.loadtxt(args.adv_out),
            utils.loadtxt(args.out),
            utils.loadtxt(args.ref),
            lang=args.tgt_lang,
        )
        # Check size
        if N is None:
            N = len(d_tgt)
        elif len(d_tgt) != N:
            raise ValueError(
                f"The number of samples in the source ({N}) doesn't match "
                f"the number of samples in the target ({len(d_tgt)})"
            )
        # Statistics
        d_tgt_avg, d_tgt_std, d_tgt_5, d_tgt_95 = utils.stats(d_tgt)
        # Print stats
        if args.terse:
            print(f"{d_tgt_avg*scale:.3f}")
        else:
            if source_side:
                print("-" * 80)
            print(
                "Target side degradation "
                f"(relative decrease in {scorer.name}):"
            )
            print(f"Mean:\t{d_tgt_avg*scale:.3f}")
            print(f"Std:\t{d_tgt_std*scale:.3f}")
            print(f"5%-95%:\t{d_tgt_5*scale:.3f}-{d_tgt_95*scale:.3f}")
    # Both sided (success)
    if target_side and source_side:
        success = [float(s + d > 1) for s, d in zip(s_src, d_tgt)]
        success_fraction = sum(success) / N
        # Print success
        if args.terse:
            print(f"{success_fraction*100:.3f}")
        else:
            print("-" * 80)
            print(f"Success percentage: {success_fraction*100:.2f} %")


if __name__ == "__main__":
    main()

"""
Main CLI script for UNKNOWN retrieval evaluation.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys

# Insert backend/ into sys.path
backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from eval.datasets.beir import load_beir_nfcorpus, load_beir_scifact
from eval.datasets.qasper import load_qasper
from eval.datasets.scifact import load_scifact
from eval.metrics.retrieval import mrr, ndcg_at_k, recall_at_k
from eval.runners.pipeline import STRATEGIES, run_strategy

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("run_eval")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="UNKNOWN Retrieval Evaluation")
    parser.add_argument(
        "--datasets",
        nargs="+",
        default=["scifact", "qasper", "beir_nfcorpus", "beir_scifact"],
        choices=["scifact", "qasper", "beir_nfcorpus", "beir_scifact"],
        help="Datasets to evaluate on",
    )
    parser.add_argument(
        "--strategies",
        nargs="+",
        default=["bm25", "faiss", "rrf", "rrf+rerank", "full"],
        choices=STRATEGIES,
        help="Retrieval strategies to evaluate",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=50,
        help="Number of queries to sample per dataset (default: 50)",
    )
    parser.add_argument(
        "--fixture",
        action="store_true",
        default=False,
        help="Force loading from bundled fixtures",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="eval/results",
        help="Output directory for results (default: eval/results)",
    )
    parser.add_argument(
        "--no-sufficiency",
        action="store_true",
        default=False,
        help="Ablation: disable sufficiency filtering",
    )
    parser.add_argument(
        "--no-verification",
        action="store_true",
        default=False,
        help="Ablation: disable reranking/verification",
    )
    parser.add_argument(
        "--no-reliability",
        action="store_true",
        default=False,
        help="Ablation: disable deduplication/reliability",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42)",
    )
    return parser.parse_args()


DATASET_LOADERS = {
    "scifact": load_scifact,
    "qasper": load_qasper,
    "beir_nfcorpus": load_beir_nfcorpus,
    "beir_scifact": load_beir_scifact,
}

DATASET_DISPLAY_NAMES = {
    "scifact": "SciFact",
    "qasper": "QASPER",
    "beir_nfcorpus": "BEIR NFCorpus",
    "beir_scifact": "BEIR SciFact",
}


def main():
    args = parse_args()

    use_sufficiency = not args.no_sufficiency
    use_verification = not args.no_verification
    use_reliability = not args.no_reliability

    out_dir = Path(args.output_dir)
    if not out_dir.is_absolute():
        out_dir = (Path.cwd() / out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 70)
    print("  UNKNOWN Retrieval Evaluation")
    print(f"  Sample size: {args.sample} | Seed: {args.seed}")
    print(f"  Ablations: sufficiency={use_sufficiency}, verification={use_verification}, reliability={use_reliability}")
    print(f"  Output directory: {out_dir}")
    print("=" * 70 + "\n")

    results_data: dict[str, dict[str, dict[str, float]]] = {}

    for dname in args.datasets:
        loader = DATASET_LOADERS.get(dname)
        if loader is None:
            logger.warning("Unknown dataset %s, skipping.", dname)
            continue

        try:
            queries = loader(n=args.sample, use_fixture=args.fixture)
        except Exception as exc:
            logger.warning("Failed to load dataset %s: %s", dname, exc)
            continue

        if not queries:
            logger.warning("Dataset %s loaded 0 queries, skipping.", dname)
            continue

        results_data[dname] = {}
        display_name = DATASET_DISPLAY_NAMES.get(dname, dname)
        print(f"\n--- Dataset: {display_name} ({len(queries)} queries) ---")
        print(f"{'Strategy':<15} {'Recall@10':>12} {'nDCG@10':>12} {'MRR':>10}")
        print("-" * 52)

        for strat in args.strategies:
            try:
                run_res = run_strategy(
                    strategy=strat,
                    queries=queries,
                    top_k=10,
                    use_sufficiency=use_sufficiency,
                    use_verification=use_verification,
                    use_reliability=use_reliability,
                    seed=args.seed,
                )

                recalls: list[float] = []
                ndcgs: list[float] = []
                mrrs: list[float] = []

                for q, r in zip(queries, run_res):
                    recalls.append(recall_at_k(r.retrieved_ids, q.relevant_ids, k=10))
                    ndcgs.append(ndcg_at_k(r.retrieved_ids, q.relevant_ids, k=10))
                    mrrs.append(mrr(r.retrieved_ids, q.relevant_ids))

                mean_rec = sum(recalls) / len(recalls) if recalls else 0.0
                mean_ndcg = sum(ndcgs) / len(ndcgs) if ndcgs else 0.0
                mean_mrr = sum(mrrs) / len(mrrs) if mrrs else 0.0

                strat_metrics = {
                    "Recall@10": round(mean_rec, 4),
                    "nDCG@10": round(mean_ndcg, 4),
                    "MRR": round(mean_mrr, 4),
                }
                results_data[dname][strat] = strat_metrics

                print(
                    f"{strat:<15} {strat_metrics['Recall@10']:>12.4f} "
                    f"{strat_metrics['nDCG@10']:>12.4f} {strat_metrics['MRR']:>10.4f}"
                )
            except Exception as exc:
                logger.warning("Strategy %s failed on %s: %s", strat, dname, exc)
                continue

    # Write results.json
    results_json_path = out_dir / "results.json"
    full_output = {
        "metadata": {
            "sample": args.sample,
            "seed": args.seed,
            "use_sufficiency": use_sufficiency,
            "use_verification": use_verification,
            "use_reliability": use_reliability,
            "datasets": args.datasets,
            "strategies": args.strategies,
        },
        "results": results_data,
    }
    with open(results_json_path, "w", encoding="utf-8") as f:
        json.dump(full_output, f, indent=2)
    print(f"\nJSON results written to {results_json_path}")

    # Write results_table.md
    md_lines = [
        "# Retrieval Evaluation Results",
        "",
        f"**Sample size**: {args.sample} | **Seed**: {args.seed}",
        "",
    ]
    for dname, strat_dict in results_data.items():
        disp = DATASET_DISPLAY_NAMES.get(dname, dname)
        md_lines.append(f"## {disp}")
        md_lines.append("")
        md_lines.append("| Strategy     | Recall@10 | nDCG@10 | MRR   |")
        md_lines.append("|:-------------|----------:|--------:|------:|")
        for strat, m in strat_dict.items():
            md_lines.append(
                f"| {strat:<12} |    {m['Recall@10']:.4f} |  {m['nDCG@10']:.4f} | {m['MRR']:.4f} |"
            )
        md_lines.append("")

    md_path = out_dir / "results_table.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines).strip() + "\n")
    print(f"Markdown table written to {md_path}")

    # Write results_table.tex
    tex_lines = []
    for dname, strat_dict in results_data.items():
        disp = DATASET_DISPLAY_NAMES.get(dname, dname)
        tex_lines.extend(
            [
                r"\begin{table}[h]",
                r"\centering",
                r"\begin{tabular}{lrrr}",
                r"\toprule",
                r"Strategy & Recall@10 & nDCG@10 & MRR \\",
                r"\midrule",
            ]
        )
        for strat, m in strat_dict.items():
            tex_lines.append(
                f"{strat} & {m['Recall@10']:.4f} & {m['nDCG@10']:.4f} & {m['MRR']:.4f} \\\\"
            )
        tex_lines.extend(
            [
                r"\bottomrule",
                r"\end{tabular}",
                f"\\caption{{{disp} retrieval results (n={args.sample})}}",
                r"\end{table}",
                "",
            ]
        )

    tex_path = out_dir / "results_table.tex"
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write("\n".join(tex_lines).strip() + "\n")
    print(f"LaTeX table written to {tex_path}\n")


if __name__ == "__main__":
    main()

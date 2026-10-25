"""Offline evaluation of the Dataset-A fault classifier on plan_dataset v2 CSVs.

This script trains a HistGradientBoostingClassifier on train_balanced.csv, selects an
abstention/unknown confidence threshold on val_real.csv ONLY, and evaluates once on
test_unseen_system_real.csv and test_unknown_fault_real.csv.

CRITICAL: This model is an OFFLINE REPORT ONLY and is NOT used live by EternalAI.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import balanced_accuracy_score, confusion_matrix, f1_score

EXCLUDE_COLUMNS = {
    "source", "system", "case_id", "parent_case_id", "sampling_s",
    "n_fault_points", "augmentation", "split", "is_synthetic", "service", "role",
    "fault_type", "category", "source_fault", "mapping_quality", "label_quality"
}


def get_feature_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in EXCLUDE_COLUMNS and pd.api.types.is_numeric_dtype(df[c])]


def run_evaluation(data_dir: Path, out_path: Path, seed: int = 42) -> dict:
    train_file = data_dir / "train_balanced.csv"
    val_file = data_dir / "val_real.csv"
    test_unseen_file = data_dir / "test_unseen_system_real.csv"
    test_unknown_file = data_dir / "test_unknown_fault_real.csv"

    for f in [train_file, val_file, test_unseen_file, test_unknown_file]:
        if not f.exists():
            raise FileNotFoundError(f"Required dataset file not found: {f}")

    train_df = pd.read_csv(train_file)
    val_df = pd.read_csv(val_file)
    test_unseen_df = pd.read_csv(test_unseen_file)
    test_unknown_df = pd.read_csv(test_unknown_file)

    feature_cols = get_feature_columns(train_df)

    X_train, y_train = train_df[feature_cols], train_df["fault_type"]
    X_val, y_val = val_df[feature_cols], val_df["fault_type"]
    X_test_unseen, y_test_unseen = test_unseen_df[feature_cols], test_unseen_df["fault_type"]
    X_test_unknown = test_unknown_df[feature_cols]

    # Train HistGradientBoostingClassifier on balanced training data with fixed seed
    clf = HistGradientBoostingClassifier(random_state=seed)
    clf.fit(X_train, y_train)

    # Threshold selection on val_real.csv ONLY (10th percentile of top-class probability on correctly classified cases)
    p_val = clf.predict_proba(X_val)
    pred_val = clf.classes_[p_val.argmax(axis=1)]
    correct_val = (pred_val == y_val.values)
    if correct_val.any():
        unknown_threshold = float(np.quantile(p_val.max(axis=1)[correct_val], 0.10))
    else:
        unknown_threshold = 0.50

    val_accuracy = float(correct_val.mean())
    val_macro_f1 = float(f1_score(y_val, pred_val, average="macro", zero_division=0))

    # Evaluate ONCE on test_unseen_system_real.csv (Train Ticket, 53 real cases)
    p_test_unseen = clf.predict_proba(X_test_unseen)
    pred_test_unseen = clf.classes_[p_test_unseen.argmax(axis=1)]

    truth_labels = sorted(y_test_unseen.unique())
    all_seen_labels = sorted(set(truth_labels) | set(pred_test_unseen))

    test_macro_f1_truth = float(f1_score(y_test_unseen, pred_test_unseen, labels=truth_labels, average="macro", zero_division=0))
    test_macro_f1_all = float(f1_score(y_test_unseen, pred_test_unseen, average="macro", zero_division=0))
    test_balanced_acc = float(balanced_accuracy_score(y_test_unseen, pred_test_unseen))

    cm = confusion_matrix(y_test_unseen, pred_test_unseen, labels=all_seen_labels)
    cm_df = pd.DataFrame(cm, index=all_seen_labels, columns=all_seen_labels)
    cm_truth_df = cm_df.loc[truth_labels]

    known_flagged_unknown = float((p_test_unseen.max(axis=1) < unknown_threshold).mean())

    # Evaluate on test_unknown_fault_real.csv (logic_bug, 18 real cases)
    p_test_unknown = clf.predict_proba(X_test_unknown)
    unknown_flagged_unknown = float((p_test_unknown.max(axis=1) < unknown_threshold).mean())

    # Render report
    report_lines = [
        "# Offline Dataset-A Fault Classifier Report",
        "",
        "> **STATUS: OFFLINE REPORT ONLY. This model is NOT used live by EternalAI.**",
        "> The live system runs the calibrated models trained on live stack telemetry (`ml/models/artifacts/`),",
        "> documented in `docs/results/models_cv_v2.md` and benchmarked in `docs/results/benchmark_v2.md`.",
        "",
        "## 1. Setup and Dataset Split",
        "",
        "- **Script**: `ml/models/eval_dataset_a.py` (fixed random seed = 42).",
        "- **Dataset Path**: `D:\\eAI\\plan_dataset\\` (v2 CSVs outside git).",
        f"- **Features used ({len(feature_cols)})**: `{', '.join(feature_cols)}`.",
        "- **Excluded columns**: identifiers, source, system, case_ids, splits, synthetic flags, and all labels.",
        "",
        "| Split | File | Cases / Rows | Nature | Description |",
        "|---|---|---|---|---|",
        f"| Training | `train_balanced.csv` | {len(train_df)} rows | 181 real + 369 synthetic | 11 classes balanced to 50 rows each via SMOTE & jitter |",
        f"| Validation | `val_real.csv` | {len(val_df)} rows | 100% real | Used ONLY to choose the 'unknown' confidence threshold |",
        f"| Unseen System Test | `test_unseen_system_real.csv` | {len(test_unseen_df)} rows | 100% real | Never-seen system (`train_ticket`), evaluated exactly once |",
        f"| Unknown Fault Test | `test_unknown_fault_real.csv` | {len(test_unknown_df)} rows | 100% real | Unseen fault type (`logic_bug`), never in training |",
        "",
        "## 2. Threshold Selection (Validation Only)",
        "",
        "- **Validation Accuracy**: " + f"{val_accuracy:.3f} (macro-F1: {val_macro_f1:.3f}).",
        f"- **Unknown Confidence Threshold**: **{unknown_threshold:.4f}** (10th percentile of top-class probability on correctly classified validation cases).",
        "",
        "## 3. Results on Held-out Real Data",
        "",
        "### Unseen System Test (`test_unseen_system_real.csv` - Train Ticket)",
        "",
        f"- **Balanced Accuracy**: **{test_balanced_acc * 100:.2f}%** ({test_balanced_acc:.4f})",
        f"- **Macro-F1 (over test ground-truth classes)**: **{test_macro_f1_truth:.3f}** ({test_macro_f1_truth * 100:.1f}%)",
        f"- **Macro-F1 (penalizing out-of-truth predictions)**: **{test_macro_f1_all:.3f}**",
        f"- **Known test cases flagged unknown**: **{known_flagged_unknown * 100:.1f}%** ({int(round(known_flagged_unknown * len(test_unseen_df)))} of {len(test_unseen_df)})",
        "",
        "### Confusion Matrix (rows = true class, columns = predicted class)",
        "",
        "| True Class \\ Predicted | " + " | ".join(all_seen_labels) + " | Total |",
        "|---|" + "---|" * len(all_seen_labels) + "---|",
    ]

    for lab in truth_labels:
        row_vals = [str(cm_truth_df.loc[lab, col]) for col in all_seen_labels]
        total_true = sum(int(v) for v in row_vals)
        report_lines.append(f"| **{lab}** | " + " | ".join(row_vals) + f" | {total_true} |")

    report_lines.extend([
        "",
        "### Unknown Fault Test (`test_unknown_fault_real.csv` - `logic_bug`)",
        "",
        f"- **Share flagged unknown**: **{unknown_flagged_unknown * 100:.1f}%** ({int(round(unknown_flagged_unknown * len(test_unknown_df)))} of {len(test_unknown_df)} correctly flagged below threshold).",
        "",
        "## 4. Current Live Model vs Offline Dataset-A Model",
        "",
        "The table below places the offline Dataset-A model numbers beside the current published numbers of the live models:",
        "",
        "| Evaluation Track | Model | Task / Dataset | Score | Source File | Status |",
        "|---|---|---|---|---|---|",
        f"| Offline Dataset-A | HistGradientBoosting (balanced) | Cross-system transfer (`train_ticket`, 53 cases) | Macro-F1 **{test_macro_f1_truth:.3f}**, Balanced Acc **{test_balanced_acc:.3f}** | `docs/results/dataset_a_model.md` | Offline report only (NOT live) |",
        f"| Offline Dataset-A | HistGradientBoosting (threshold={unknown_threshold:.4f}) | Unknown fault abstention (`logic_bug`, 18 cases) | Flagged unknown: **{unknown_flagged_unknown * 100:.1f}%** | `docs/results/dataset_a_model.md` | Offline report only (NOT live) |",
        "| Live Application | Calibrated Gradient Boosting + IsolationForest | Live stack runs grouped CV (105 runs, 33,576 windows) | Macro-F1 **0.991**, ECE **0.003**, False alarm 1.1/100 service-min | `docs/results/models_cv_v2.md` | **Verified live model** |",
        "| Public RCAEval Transfer | Gradient Boosting (leave-one-system-out) | RCAEval RE1 (3 systems, 300 incidents, 900 rows) | Mean Macro-F1 **0.616** [0.586, 0.644] (TT 0.682, SS 0.590, OB 0.575) | `docs/results/transfer_re1.md` | Offline public benchmark |",
        "| Live Benchmark v2 | Autopilot (policy + runbooks) | Held-out seeds (18 supported runs, 24 healthy runs) | Recovered **18/18 [82%, 100%]**, Healthy actions **0/24**, Failed req **11.15%** | `docs/results/benchmark_v2.md` | **Verified live gate** |",
        "",
        "## 5. Limitations and Discussion",
        "",
        "1. **Few real cases**: The entire Dataset A contains only 181 real training cases across 11 fault classes; cross-system transfer relies on small sample sizes.",
        "2. **Single-source bias**: 64% of planned fault types originate from only a single source system (Cramér's V = 72% between source and label), meaning models can easily learn source artifacts rather than generalized fault physics.",
        "3. **Synthetic rows in training**: While synthetic oversampling (369 rows) balanced class representations to 50 rows each, it cannot create new underlying domain knowledge. Cross-system generalization remains roughly 55-60% (here 56.4% macro-F1, 58.6% balanced accuracy on Train Ticket).",
        "4. **Live separation**: The live EternalAI detector and classifier operate on high-frequency 10 s rolling windows of container metrics and traces specifically calibrated for the monitored stack, where in-distribution performance reaches 0.991 macro-F1. Cross-system transfer remains a known open challenge across the AIOps literature.",
    ])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    return {
        "val_accuracy": val_accuracy,
        "unknown_threshold": unknown_threshold,
        "test_macro_f1_truth": test_macro_f1_truth,
        "test_balanced_acc": test_balanced_acc,
        "known_flagged_unknown": known_flagged_unknown,
        "unknown_flagged_unknown": unknown_flagged_unknown,
        "report_path": str(out_path),
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate Dataset-A offline fault classifier.")
    parser.add_argument("--data-dir", default=r"D:\eAI\plan_dataset", help="Path to directory containing v2 CSVs.")
    parser.add_argument("--out", default=r"docs/results/dataset_a_model.md", help="Output markdown path.")
    parser.add_argument("--seed", type=int, default=42, help="Random state seed.")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        fallback = Path(r"C:\Users\Mihir\eAI-mihir\plan_dataset_for_mihir")
        if fallback.exists():
            data_dir = fallback

    out_path = Path(args.out)
    if not out_path.is_absolute():
        repo_root = Path(__file__).resolve().parents[2]
        out_path = repo_root / out_path

    res = run_evaluation(data_dir, out_path, seed=args.seed)
    print(f"Evaluation complete. Report written to {res['report_path']}")
    print(f"Test Balanced Accuracy: {res['test_balanced_acc']:.4f}")
    print(f"Test Macro-F1 (truth): {res['test_macro_f1_truth']:.4f}")
    print(f"Unknown threshold: {res['unknown_threshold']:.4f}")
    print(f"Unknown flagged unknown: {res['unknown_flagged_unknown']:.4f}")


if __name__ == "__main__":
    main()

"""Dataset-A fault classifier (plan §9.4, §10.4, §10.7, §18), reported next to the current live classifier on the same
never-seen-system cases. Offline: reads the owner's workbook read-only; nothing from it is committed except this script's
aggregate results.

    python models/train_dataset_a.py --workbook <EternalAI_training_dataset_v1.xlsx> [--out docs/results/dataset_a_classifier.md]

EVERY CHOICE BELOW WAS FIXED BEFORE THE FIRST RUN (2026-10-23, about 21:10 IST) and is not changed after seeing results.
- Data: the workbook's A sheets (A_cases, A_telemetry), REAL rows only. The plan's v2 files (train_balanced.csv with
  synthetic oversampling, val_real.csv, test_unseen_system_real.csv, test_unknown_fault_real.csv) are not on this
  machine, so the plan's v2 numbers cannot be reproduced exactly; this is the plan's split method on real rows.
- One row per incident (plan §9.4: "one feature row for the root service"): the root service's row; for incidents with
  no root (normal cases) the entry service's row (smallest depth_from_entry, first in row order).
- Splits (plan §10.7): test = every Train Ticket incident except logic bugs; unknown-fault test = every logic_bug
  incident (any system); validation = 20% of the remaining incidents per class (stratified, seed 0); train = the rest.
  Primary = the plan's definition (all incidents); secondary = only exact/close label mappings in scope (this
  repository's training-truth rule, data/clean_workbook.py).
- Features: plan §10.4 columns present in the workbook, minus the plan's "do not use" list (sampling_s, n_fault_points,
  source, system, case_id), minus log features (log_*, excluded by default by the plan), minus data/label_map.py
  LEAKY_COLUMNS. Variant P keeps err_base/err_fault/err_delta (the plan lists them); variant L drops them because they are
  defined against the known injection window (docs/DATA.md), which a live system does not have. Missing stays NaN
  (HistGradientBoosting handles it); no neutral filling.
- Model: HistGradientBoostingClassifier(max_depth=3, max_iter=200, learning_rate=0.05, min_samples_leaf=5,
  class_weight="balanced", random_state=0). Category model (plan §9.4 second target): same settings on `category`.
- Unknown threshold (plan §9.4, from validation only): the 10th percentile of the top class probability over correctly
  classified validation incidents. Below it the answer is "unknown".
- Reported on the test set: macro-F1 over the classes present in the test truth (forced answer), the confusion matrix,
  the majority-class baseline, the share of known test incidents wrongly flagged unknown, the share of logic_bug
  incidents flagged unknown, and the category macro-F1. The test set is evaluated once.
- The current live classifier (models/artifacts/classifier.joblib) on the same test incidents: only columns with the
  same meaning are passed (lat_ratio, lat_z, cpu_ratio, cpu_z, rps_ratio, rps_z, mem_slope_share_per_min, up_frac;
  error_ratio <- err_fault; error_ratio_delta <- err_delta); every other live feature is unobserved (NaN, mask 0). Its six
  labels are mapped to plan names (eternalai/kb/labels.py); classes it cannot name count as errors or abstentions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import confusion_matrix, f1_score
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "data"))
from label_map import ID_COLUMNS, LEAKY_COLUMNS  # noqa: E402

TEST_SYSTEM, UNKNOWN_LABEL = "train_ticket", "logic_bug"
DO_NOT_USE = {"sampling_s", "n_fault_points", "source", "system", "case_id", "run_group", "service"}
WINDOW_DEFINED = {"err_base", "err_fault", "err_delta"}
PARAMS = dict(max_depth=3, max_iter=200, learning_rate=0.05, min_samples_leaf=5, class_weight="balanced", random_state=0)
LIVE_MAP = {"lat_ratio": "lat_ratio", "lat_z": "lat_z", "cpu_ratio": "cpu_ratio", "cpu_z": "cpu_z", "rps_ratio": "rps_ratio",
            "rps_z": "rps_z", "mem_slope_share_per_min": "mem_slope_share_per_min", "up_frac": "up_frac",
            "error_ratio": "err_fault", "error_ratio_delta": "err_delta"}


def incident_rows(cases: pd.DataFrame, tel: pd.DataFrame) -> pd.DataFrame:
    """One row per incident: the root service's row, else the entry service's row."""
    out = []
    for cid, g in tel.groupby("case_id", sort=False):
        root = g[g.is_root == 1]
        if len(root):
            row = root.iloc[0]
        else:
            g2 = g.assign(_d=g["depth_from_entry"].fillna(1e9))
            row = g2.sort_values("_d", kind="stable").iloc[0]
        out.append(row)
    rows = pd.DataFrame(out).drop(columns=["_d"], errors="ignore")
    keep = ["case_id", "fault_type", "category", "system", "mapping_quality", "in_scope"]
    return rows.drop(columns=[c for c in keep if c != "case_id" and c in rows.columns]).merge(cases[keep], on="case_id")


def feature_columns(df: pd.DataFrame, variant: str) -> list[str]:
    cols = [c for c in df.columns if c not in DO_NOT_USE | set(ID_COLUMNS) | set(LEAKY_COLUMNS)
            and not c.startswith("log_") and c not in ("mapping_quality", "in_scope", "is_root", "role")
            and pd.api.types.is_numeric_dtype(df[c]) and df[c].notna().any()]
    return [c for c in cols if c not in WINDOW_DEFINED] if variant == "L" else cols


def split(rows: pd.DataFrame, strict: bool):
    data = rows[rows.fault_type != UNKNOWN_LABEL]
    if strict:
        data = data[data.mapping_quality.isin(["exact", "close"]) & data.in_scope.astype(bool)]
    test = data[data.system == TEST_SYSTEM]
    rest = data[data.system != TEST_SYSTEM]
    counts = rest.fault_type.value_counts()
    strat = rest.fault_type.where(rest.fault_type.map(counts) >= 2, "_rare")
    train, val = train_test_split(rest, test_size=0.2, stratify=strat, random_state=0)
    unknown = rows[rows.fault_type == UNKNOWN_LABEL]
    return train, val, test, unknown


def evaluate(rows: pd.DataFrame, variant: str, strict: bool) -> dict:
    train, val, test, unknown = split(rows, strict)
    feats = feature_columns(rows, variant)
    m = HistGradientBoostingClassifier(**PARAMS).fit(train[feats], train.fault_type)
    pv = m.predict_proba(val[feats])
    right = m.classes_[pv.argmax(1)] == val.fault_type.values
    thr = float(np.quantile(pv.max(1)[right], 0.10)) if right.any() else 0.5
    pt = m.predict_proba(test[feats])
    pred = m.classes_[pt.argmax(1)]
    labels = sorted(test.fault_type.unique())
    majority = train.fault_type.value_counts().idxmax()
    pu = m.predict_proba(unknown[feats]).max(1) if len(unknown) else np.array([])
    cat = HistGradientBoostingClassifier(**PARAMS).fit(train[feats], train.category)
    cat_pred = cat.predict(test[feats])
    return {"variant": variant, "truth": "exact/close only" if strict else "all (plan definition)",
            "n_train": len(train), "n_val": len(val), "n_test": len(test), "n_unknown_test": len(unknown),
            "train_classes": sorted(train.fault_type.unique()), "test_classes": labels, "n_features": len(feats),
            "macro_f1": round(float(f1_score(test.fault_type, pred, labels=labels, average="macro", zero_division=0)), 3),
            "majority_class": majority,
            "majority_macro_f1": round(float(f1_score(test.fault_type, [majority] * len(test), labels=labels, average="macro",
                                                      zero_division=0)), 3),
            "threshold": round(thr, 4),
            "known_flagged_unknown": round(float((pt.max(1) < thr).mean()), 3),
            "logic_bug_flagged_unknown": round(float((pu < thr).mean()), 3) if len(pu) else None,
            "category_macro_f1": round(float(f1_score(test.category, cat_pred, labels=sorted(test.category.unique()),
                                                      average="macro", zero_division=0)), 3),
            "confusion": {"labels": labels + sorted(set(pred) - set(labels)),
                          "matrix": confusion_matrix(test.fault_type, pred,
                                                     labels=labels + sorted(set(pred) - set(labels))).tolist()}}


def live_classifier_on(rows: pd.DataFrame) -> dict:
    from eternalai import artifacts
    from eternalai.kb.labels import LIVE_TO_PLAN
    clf, meta = artifacts.load("classifier")
    if clf is None:
        return {"error": "models/artifacts/classifier.joblib not present"}
    _, _, test, _ = split(rows, strict=False)
    preds, abst = [], 0
    for _, r in test.iterrows():
        f = {}
        for live, col in LIVE_MAP.items():
            v = r.get(col)
            ok = v is not None and not (isinstance(v, float) and np.isnan(v))
            f[live], f[live + "_obs"] = (float(v) if ok else np.nan), (1.0 if ok else 0.0)
        p = clf.predict(f)
        abst += bool(p.abstained)
        preds.append("unknown" if p.abstained else LIVE_TO_PLAN.get(p.label, p.label if p.label != "healthy" else "normal"))
    labels = sorted(test.fault_type.unique())
    return {"n_test": len(test), "passed_features": sorted(LIVE_MAP), "unobserved_live_features":
            sorted({f for f in clf.features if not f.endswith("_obs")} - set(LIVE_MAP)),
            "macro_f1": round(float(f1_score(test.fault_type, preds, labels=labels, average="macro", zero_division=0)), 3),
            "abstained": abst, "predicted_labels": pd.Series(preds).value_counts().to_dict(),
            "classes_it_cannot_name": sorted(set(labels) - set(LIVE_TO_PLAN.values()) - {"normal"})}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workbook", required=True)
    ap.add_argument("--out", default=str(ROOT / "docs" / "results" / "dataset_a_classifier.md"))
    a = ap.parse_args()
    wb = Path(a.workbook)
    digest = hashlib.sha256(wb.read_bytes()).hexdigest()
    x = pd.ExcelFile(wb)
    cases, tel = x.parse("A_cases"), x.parse("A_telemetry")
    rows = incident_rows(cases, tel)
    results = [evaluate(rows, v, s) for s in (False, True) for v in ("P", "L")]
    live = live_classifier_on(rows)
    R = ["# Dataset-A fault classifier, next to the live classifier (generated by `models/train_dataset_a.py`)", "",
         f"- Generated {time.strftime('%Y-%m-%d %H:%M')} local time; workbook SHA256 `{digest}` (not committed).",
         "- Method fixed before the first run (script header). Real rows only: the plan's v2 balanced files are not on this "
         "machine, so the plan's v2 numbers are not reproduced exactly.",
         f"- Never-seen system: `{TEST_SYSTEM}`. Unknown-fault test: every `{UNKNOWN_LABEL}` incident.", "",
         "| variant | truth | train / val / test / unknown | features | macro-F1 (test) | majority baseline | unknown threshold | known wrongly flagged unknown | logic_bug flagged unknown | category macro-F1 |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        R.append(f"| {r['variant']} | {r['truth']} | {r['n_train']} / {r['n_val']} / {r['n_test']} / {r['n_unknown_test']} | "
                 f"{r['n_features']} | **{r['macro_f1']}** | {r['majority_macro_f1']} ({r['majority_class']}) | {r['threshold']} | "
                 f"{r['known_flagged_unknown']} | {r['logic_bug_flagged_unknown']} | {r['category_macro_f1']} |")
    R += ["", "Variant P = the plan's feature list (includes err_base/err_fault/err_delta, which are defined against the known "
          "injection window); variant L = without them (computable live).", ""]
    for r in results:
        R += [f"### Confusion matrix: variant {r['variant']}, {r['truth']} (rows = truth, columns = prediction)", "",
              "| truth \\ predicted | " + " | ".join(r["confusion"]["labels"]) + " |",
              "|---|" + "---|" * len(r["confusion"]["labels"])]
        for lab, row in zip(r["confusion"]["labels"], r["confusion"]["matrix"]):
            if lab in r["test_classes"]:
                R.append(f"| {lab} | " + " | ".join(str(v) for v in row) + " |")
        R.append("")
    R += ["## The current live classifier on the same test incidents", ""]
    if "error" in live:
        R.append(f"- {live['error']}")
    else:
        R += [f"- Test incidents: {live['n_test']}; macro-F1 over the test classes: **{live['macro_f1']}**; abstained: "
              f"{live['abstained']}.",
              f"- Predicted labels: {live['predicted_labels']}.",
              f"- Test classes it cannot name at all: {live['classes_it_cannot_name']}.",
              f"- Columns passed (same meaning): {live['passed_features']}. Live features left unobserved: "
              f"{live['unobserved_live_features']}.",
              "- **Not a fair comparison**: the live model was trained on another schema (10 s live windows of one app) and "
              "most of its inputs are missing here. It is reported because the plan asks for both on the same held-out "
              "data, not as evidence that either model is better."]
    R += ["", "## Plan statements compared with this run",
          "- Plan §18: 'fault classifier ... 33% (12-59%) on never-seen systems'; §20: '58% on Train Ticket'. This run, "
          f"real rows only: macro-F1 {results[0]['macro_f1']} (variant P) and {results[1]['macro_f1']} (variant L) on Train Ticket. "
          "Different training data from the plan's v2 (no synthetic rows), so the numbers are not directly comparable.",
          "- Plan §18: 'unknown-fault AUROC ~0.66'. Not computed here (no AUROC rule was fixed in advance); the flagged share "
          "at the validation threshold is reported instead."]
    Path(a.out).write_text("\n".join(R) + "\n", encoding="utf-8")
    raw = {"workbook_sha256": digest, "results": results, "live_classifier": live}
    Path(a.out).with_suffix(".json").write_text(json.dumps(raw, indent=1, default=str), encoding="utf-8")
    print("\n".join(R[:12]))


if __name__ == "__main__":
    main()

"""ml/models/train_dataset_a.py split and row rules, on SYNTHETIC data (no workbook needed)."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tda", ROOT / "ml" / "models" / "train_dataset_a.py")
tda = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tda)


def synthetic():
    cases, tel = [], []
    rng = np.random.default_rng(0)
    systems = ["online_boutique", "petshop_aws", "train_ticket"]
    labels = ["app_error", "normal", "network_delay", "logic_bug"]
    n = 0
    for sysname in systems:
        for lab in labels:
            for k in range(6):
                cid = f"{sysname}-{lab}-{k}"
                cases.append({"case_id": cid, "fault_type": lab, "category": "Normal" if lab == "normal" else "Network",
                              "system": sysname, "mapping_quality": "exact" if k % 3 else "approximate", "in_scope": lab != "logic_bug"})
                for svc, depth in (("front", 0), ("back", 1)):
                    tel.append({"case_id": cid, "service": svc, "system": sysname, "source": "s", "sampling_s": 5,
                                "is_root": int(lab != "normal" and svc == "back"), "depth_from_entry": depth,
                                "lat_ratio": rng.random(), "err_fault": rng.random(), "err_delta": rng.random(),
                                "err_base": rng.random(), "log_err_delta": 9.9, "fault_type": lab, "role": "x"})
                n += 1
    return pd.DataFrame(cases), pd.DataFrame(tel)


def test_one_row_per_incident_root_or_entry():
    cases, tel = synthetic()
    rows = tda.incident_rows(cases, tel)
    assert len(rows) == len(cases) and rows.case_id.is_unique
    assert set(rows[rows.fault_type == "normal"].service) == {"front"}          # no root: the entry service
    assert set(rows[rows.fault_type == "app_error"].service) == {"back"}        # the root service


def test_splits_keep_the_test_system_and_unknowns_apart():
    cases, tel = synthetic()
    rows = tda.incident_rows(cases, tel)
    for strict in (False, True):
        train, val, test, unknown = tda.split(rows, strict)
        assert set(test.system) == {"train_ticket"} and "train_ticket" not in set(train.system) | set(val.system)
        assert set(unknown.fault_type) == {"logic_bug"} and "logic_bug" not in set(train.fault_type) | set(val.fault_type) | set(test.fault_type)
        assert not set(train.case_id) & set(val.case_id) and not set(train.case_id) & set(test.case_id)
        if strict:
            assert set(train.mapping_quality) <= {"exact", "close"}


def test_feature_lists_exclude_identity_logs_and_leaks():
    cases, tel = synthetic()
    rows = tda.incident_rows(cases, tel)
    p, l_ = tda.feature_columns(rows, "P"), tda.feature_columns(rows, "L")
    for banned in ("case_id", "system", "source", "sampling_s", "is_root", "role", "fault_type", "log_err_delta", "depth_from_entry"):
        assert banned not in p or banned == "depth_from_entry"
    assert "log_err_delta" not in p and "err_fault" in p and "err_fault" not in l_ and "lat_ratio" in l_

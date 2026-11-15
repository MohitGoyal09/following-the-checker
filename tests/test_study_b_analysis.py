import pandas as pd

from sourced.study_b_analysis import indices


def _rows(policy):
    rows = []
    for i in range(10):
        truth = "supported" if i < 5 else "unsupported"
        for cond in ("c", "d"):
            signal_supported = (truth == "supported") == (cond == "c")
            rows.append({"noteId": f"n{i}", "truth": truth, "condition": cond,
                         "rely": policy(truth, signal_supported)})
    return pd.DataFrame(rows)


def test_pure_deference_follows_signal_and_ignores_truth():
    f, t = indices(_rows(lambda truth, sig: sig), ("c", "d"))
    assert f == 1.0 and t == 0.0


def test_pure_discernment_tracks_truth_and_ignores_signal():
    f, t = indices(_rows(lambda truth, sig: truth == "supported"), ("c", "d"))
    assert f == 0.0 and t == 1.0


def test_support_gap_within_one_condition():
    from sourced.study_b_robustness import support_gap
    d = pd.DataFrame({"condition": ["a"] * 4, "truth": ["supported"] * 2 + ["unsupported"] * 2, "rely": [1, 1, 0, 1]})
    assert support_gap(d, "a") == 0.5

import pandas as pd

from sourced.gold_analysis import kappa
from sourced.study_a import boot, link_unsup, note_unsup


def test_kappa_matches_hand_value_for_shared_author_table():
    # 20 items: 15 agree; marginals give pe = 0.3325, so kappa = (0.75 - 0.3325) / 0.6675
    a = ["partial"] * 8 + ["silent"] * 5 + ["supports"] * 7
    b = ["partial"] * 4 + ["silent"] * 2 + ["supports"] * 2 + ["partial"] + ["silent"] * 4 + ["supports"] * 7
    assert abs(kappa(a, b) - 0.4175 / 0.6675) < 1e-9
    assert kappa(a, a) == 1.0


def _notes() -> pd.DataFrame:
    d = pd.DataFrame({"writer": ["w1", "w1", "w2", "h1", "h2"], "ai": [True, True, True, False, False],
                      "n_judged": [2, 1, 0, 1, 3], "n_sup": [1, 0, 0, 1, 0]})
    return d.assign(judgeable=d.n_judged > 0, unsupported=(d.n_judged > 0) & (d.n_sup == 0))


def test_link_and_note_rates_skip_unjudgeable_notes():
    d = _notes()
    assert link_unsup(d) == 1 - 2 / 7
    assert note_unsup(d) == 2 / 4  # the w2 note has no judged link and is left out


def test_cluster_bootstrap_interval_contains_estimate():
    r = boot(_notes(), link_unsup, n_boot=300)
    assert r["ci95"][0] <= r["est"] <= r["ci95"][1]

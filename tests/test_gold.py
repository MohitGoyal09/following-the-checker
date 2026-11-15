import pandas as pd

from sourced.gold import stratified


def test_stratified_draw_is_balanced_reproducible_and_unique():
    df = pd.DataFrame({"key": range(200), "ai": [i % 3 == 0 for i in range(200)]})
    a = stratified(df, "ai", per_group=25, seed=42)
    b = stratified(df, "ai", per_group=25, seed=42)
    assert a.key.tolist() == b.key.tolist()
    assert a.ai.value_counts().to_dict() == {True: 25, False: 25}
    assert a.key.is_unique
    # shuffled, so labellers cannot infer writer type from position
    assert a.ai.tolist() != sorted(a.ai.tolist()) and a.ai.tolist() != sorted(a.ai.tolist(), reverse=True)


def test_assign_shares_overlap_and_splits_rest_evenly_within_groups():
    from sourced.gold import AUTHORS, assign

    df = stratified(pd.DataFrame({"key": range(200), "ai": [i % 3 == 0 for i in range(200)]}), "ai", 25, 42)
    lab = assign(df, "ai", n_shared=20)
    assert lab.value_counts().to_dict() == {"both": 20, AUTHORS[0]: 15, AUTHORS[1]: 15}
    for _, g in lab.groupby(df.ai):
        assert (g == "both").sum() == 10
        assert abs((g == AUTHORS[0]).sum() - (g == AUTHORS[1]).sum()) <= 1
    assert assign(df, "ai").value_counts().to_dict() == {AUTHORS[0]: 25, AUTHORS[1]: 25}

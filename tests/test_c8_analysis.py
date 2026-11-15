import numpy as np

from sourced.c8_analysis import segmented_fit


def test_segmented_fit_recovers_a_known_level_break():
    rng = np.random.default_rng(0)
    t = np.arange(34)
    post = (t >= 20).astype(float)
    y = 0.50 + 0.001 * t + 0.04 * post + rng.normal(0, 0.003, len(t))
    fit = segmented_fit(y, break_index=20)
    assert abs(fit["level_change"] - 0.04) < 0.01
    assert fit["level_ci"][0] < 0.04 < fit["level_ci"][1]
    assert fit["level_p"] < 0.001


def test_segmented_fit_finds_no_break_in_a_flat_series():
    rng = np.random.default_rng(1)
    y = 0.5 + rng.normal(0, 0.003, 34)
    fit = segmented_fit(y, break_index=20)
    assert fit["level_ci"][0] < 0 < fit["level_ci"][1]

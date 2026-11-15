"""Study A: do the links in Helpful notes support the notes' claims? (PREREGISTRATION.md, Amendments 1 and 3)

Usage: uv run python -m sourced.study_a -> results/study_a.json
No model calls. Reads the sample, fetch and archive results, rater tags and both judges' verdicts.
Intervals: two-stage cluster bootstrap (writers, then notes within writers), stratified by writer type.
Models: cluster-robust standard errors by writer (deviation: the bootstrap is used for rates only).
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from statsmodels.stats.contingency_tables import mcnemar

P = "data/processed/"
OUT = Path("results/study_a.json")
JUDGES = ("claude-opus-5-5", "gemini-3.8-flash")
N_BOOT, SEED = 10_000, 42
EARLY, LATE = ("2025-10-01", "2026-04-01"), ("2026-07-01", "2026-12-01")  # C5 windows


def links(judge: str) -> pd.DataFrame:
    """One row per sampled link: liveness, archive state and the judge's verdict (NaN = unjudgeable)."""
    lk = pd.read_csv(P + "sample_links.csv", dtype={"noteId": str})
    live = pd.read_json(P + "links.jsonl", lines=True)[["url", "state", "status"]].rename(columns={"state": "live_state", "status": "live_status"})
    wb = pd.read_json(P + "wayback.jsonl", lines=True, dtype={"noteId": str})[["noteId", "url", "state", "status", "in_window"]]
    wb = wb.rename(columns={"state": "wb_state", "status": "wb_status"})
    v = pd.read_csv(P + f"verdicts_{judge}.csv", dtype={"noteId": str})
    v = v[~v.fallback.astype(bool)][["noteId", "url", "verdict"]]
    d = lk.merge(live, on="url", how="left").merge(wb, on=["noteId", "url"], how="left").merge(v, on=["noteId", "url"], how="left")
    return d.assign(live_pass=d.live_status.eq(200) | (d.in_window.eq(True) & d.wb_status.eq(200)),
                    judged=d.verdict.notna(), sup=d.verdict.eq("supports"), archived=d.wb_state.eq("ok"))


def notes(lk: pd.DataFrame) -> pd.DataFrame:
    n = pd.read_csv(P + "sample_notes.csv", dtype={"noteId": str, "tweetId": str})
    raw = pd.read_csv("data/raw/notes-00000.tsv", sep="\t", usecols=["noteId", "noteAuthorParticipantId"], dtype=str)
    lang = pd.read_csv(P + "claims.csv", dtype={"noteId": str})[["noteId", "language"]]
    tags = pd.read_csv(P + "rater_tags.csv", dtype={"noteId": str})
    agg = lk.groupby("noteId").agg(n_links=("url", "size"), n_live=("live_pass", "sum"), n_judged=("judged", "sum"), n_sup=("sup", "sum"))
    n = (n.merge(raw, on="noteId").rename(columns={"noteAuthorParticipantId": "writer"}).merge(lang, on="noteId", how="left")
         .merge(tags, on="noteId", how="left").merge(agg, left_on="noteId", right_index=True, how="left"))
    n[["n_links", "n_live", "n_judged", "n_sup"]] = n[["n_links", "n_live", "n_judged", "n_sup"]].fillna(0).astype(int)
    return n.assign(crh=n.currentStatus.eq("CURRENTLY_RATED_HELPFUL"), judgeable=n.n_judged > 0,
                    unsupported=(n.n_judged > 0) & (n.n_sup == 0), created=pd.to_datetime(n.createdAtMillis, unit="ms"))


# --- statistics on a note table -------------------------------------------------------------
def link_unsup(d: pd.DataFrame) -> float:
    return 1 - d.n_sup.sum() / d.n_judged.sum() if d.n_judged.sum() else np.nan


def note_unsup(d: pd.DataFrame) -> float:
    return d.unsupported.sum() / d.judgeable.sum() if d.judgeable.sum() else np.nan


def boot(d: pd.DataFrame, stat, n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    """Point estimate and 95% interval; resample writers (within writer type), then notes within writers."""
    rng = np.random.default_rng(seed)
    flat = d.reset_index(drop=True)
    groups = [[np.asarray(ix) for ix in g.groupby("writer").groups.values()] for _, g in flat.groupby("ai")]
    vals = []
    for _ in range(n_boot):
        idx = [w[rng.integers(0, len(w), len(w))] for gs in groups for w in (gs[i] for i in rng.integers(0, len(gs), len(gs)))]
        vals.append(stat(flat.iloc[np.concatenate(idx)]))
    lo, hi = np.nanpercentile(vals, [2.5, 97.5])
    return {"est": round(float(stat(d)), 4), "ci95": [round(float(lo), 4), round(float(hi), 4)]}


def diff(stat, a, b):
    return lambda d: stat(d[a(d)]) - stat(d[b(d)])


def logit(formula: str, d: pd.DataFrame) -> dict:
    m = smf.logit(formula, d).fit(disp=0, cov_type="cluster", cov_kwds={"groups": pd.factorize(d.writer)[0]})
    ci = m.conf_int()
    return {k: {"coef": round(float(m.params[k]), 3), "ci95": [round(float(ci.loc[k, 0]), 3), round(float(ci.loc[k, 1]), 3)],
                "p": round(float(m.pvalues[k]), 4)} for k in m.params.index} | {"n": int(m.nobs)}


def by_writer_type(d: pd.DataFrame, stat) -> dict:
    return {"all": boot(d, stat), "ai": boot(d[d.ai], stat), "human": boot(d[~d.ai], stat),
            "ai_minus_human": boot(d, diff(stat, lambda x: x.ai, lambda x: ~x.ai))}


# --- analyses ---------------------------------------------------------------------------------
def h1_c1(n: pd.DataFrame) -> dict:
    hp = n[n.stratum == "helpful_pair"]
    pairs = hp[hp.judgeable].pivot_table(index="tweetId", columns="ai", values="unsupported", aggfunc="first").dropna()
    t = pd.crosstab(pairs[True].astype(bool), pairs[False].astype(bool)).reindex(index=[False, True], columns=[False, True], fill_value=0)
    jd = hp[hp.judgeable]
    return {
        "link_level_unsupported": by_writer_type(hp, link_unsup),
        "note_level_unsupported": by_writer_type(hp, note_unsup),
        "note_level_bounds_unjudgeable": {
            w: {"as_supported": round(float(g.unsupported.mean()), 4), "as_unsupported": round(float((g.unsupported | ~g.judgeable).mean()), 4)}
            for w, g in [("all", hp), ("ai", hp[hp.ai]), ("human", hp[~hp.ai])]},
        "n_notes": int(len(hp)), "n_judgeable_notes": {"ai": int(jd.ai.sum()), "human": int((~jd.ai).sum())},
        "n_judged_links": {"ai": int(hp[hp.ai].n_judged.sum()), "human": int(hp[~hp.ai].n_judged.sum())},
        "mcnemar_pairs_both_judgeable": {"n_pairs": int(len(pairs)), "ai_unsup_only": int(t.loc[True, False]),
                                         "human_unsup_only": int(t.loc[False, True]), "p_exact": round(float(mcnemar(t.values, exact=True).pvalue), 4)},
        "logit_unsupported_ai_nlinks": logit("unsupported ~ ai + n_judged", jd.assign(unsupported=jd.unsupported.astype(int), ai=jd.ai.astype(int))),
    }


def h7(lk: pd.DataFrame, n: pd.DataFrame) -> dict:
    crh = lk[lk.noteId.isin(n.noteId[n.crh])].merge(n[["noteId", "ai"]], on="noteId")
    out = {}
    for w, g in [("all", crh), ("ai", crh[crh.ai]), ("human", crh[~crh.ai])]:
        live = g[g.live_pass]
        out[w] = {"n_links": int(len(g)), "live_pass_rate": round(float(g.live_pass.mean()), 4), "n_live": int(len(live)),
                  "live_not_supports": round(float(1 - live.sup.mean()), 4),
                  "live_breakdown": live.verdict.fillna("no usable text").value_counts(normalize=True).round(4).to_dict()}
    return out


def c2(lk: pd.DataFrame, n: pd.DataFrame) -> dict:
    hp = n[n.stratum == "helpful_pair"]
    live = lambda d: d.n_live.sum() / d.n_links.sum()
    tags = lambda d: d.good_sources_share.mean()
    return {w: {"gate1_live_pass": boot(g, live), "gate2_good_sources_tag": boot(g.dropna(subset=["good_sources_share"]), tags),
                "checked_support": boot(g, lambda d: 1 - link_unsup(d))}
            for w, g in [("ai", hp[hp.ai]), ("human", hp[~hp.ai])]}


def h6(n: pd.DataFrame) -> dict:
    d = n[n.judgeable].dropna(subset=["good_sources_share"]).assign(sup_share=lambda x: x.n_sup / x.n_judged)
    sp = lambda col: (lambda x: x[col].corr(x.sup_share, method="spearman"))
    m = d.dropna(subset=["sources_missing_share"])
    return {"n_notes": int(len(d)),
            "spearman_good_sources_vs_support": boot(d, sp("good_sources_share")),
            "spearman_sources_missing_vs_support": boot(m, sp("sources_missing_share")),
            "logit_supported_tags_ai": logit("supported ~ good_sources_share + ai", d.assign(supported=(~d.unsupported).astype(int), ai=d.ai.astype(int)))}


def h3(n: pd.DataFrame) -> dict:
    jd = n[n.judgeable]
    return {"link_level_unsupported": {s: by_writer_type(n[n.crh == c], link_unsup) for s, c in [("crh", True), ("crnh", False)]},
            "crh_minus_crnh_link_level": boot(n, diff(link_unsup, lambda x: x.crh, lambda x: ~x.crh)),
            "note_level_unsupported": {s: round(float(note_unsup(n[n.crh == c])), 4) for s, c in [("crh", True), ("crnh", False)]},
            "logit_unsupported_status_ai": logit("unsupported ~ crh * ai + n_judged",
                                                 jd.assign(unsupported=jd.unsupported.astype(int), crh=jd.crh.astype(int), ai=jd.ai.astype(int)))}


def c4(n: pd.DataFrame) -> dict:
    ai = n[n.ai & n.judgeable]
    rows = [{"n_notes": int(len(g)), "n_links": int(g.n_judged.sum()), "link_supported": round(float(1 - link_unsup(g)), 4)}
            for _, g in ai.groupby("writer") if len(g) >= 5]
    rows = sorted(rows, key=lambda r: -r["link_supported"])
    return {f"W{i + 1}": r for i, r in enumerate(rows)} | {"scope": "all strata, judgeable AI notes, writers with >=5"}


def c5(n: pd.DataFrame) -> dict:
    hp = n[n.stratum == "helpful_pair"]
    win = lambda lo_hi: hp[(hp.created >= lo_hi[0]) & (hp.created < lo_hi[1])]
    return {name: {"n_ai_notes": int(win(w).ai.sum()), "ai": boot(win(w)[win(w).ai], link_unsup), "human": boot(win(w)[~win(w).ai], link_unsup)}
            for name, w in [("early", EARLY), ("late", LATE)]}


def c6(n: pd.DataFrame) -> dict:
    en = n.language.eq("en")
    return {"english": boot(n[en], link_unsup), "non_english": boot(n[~en], link_unsup), "n": {"en": int(en.sum()), "other": int((~en).sum())}}


def descriptive(lk: pd.DataFrame, n: pd.DataFrame) -> dict:
    d = lk.merge(n[["noteId", "ai", "stratum"]], on="noteId")
    top = n[n.ai].writer.value_counts()
    return {
        "links_per_note": n.groupby("ai").n_links.mean().round(3).to_dict(),
        "judged_links_per_note": n.groupby("ai").n_judged.mean().round(3).to_dict(),
        "share_notes_no_link": n.groupby("ai").n_links.apply(lambda x: float((x == 0).mean())).round(3).to_dict(),
        "share_notes_unjudgeable": n.groupby("ai").judgeable.apply(lambda x: float(1 - x.mean())).round(3).to_dict(),
        "live_state_share": pd.crosstab(d.ai, d.live_state, normalize="index").round(3).to_dict(orient="index"),
        "archive_coverage_judged": d[d.judged].groupby("ai").archived.mean().round(3).to_dict(),
        "writers": {"ai": int(n[n.ai].writer.nunique()), "human": int(n[~n.ai].writer.nunique()),
                    "top3_ai_writer_share_of_ai_notes": round(float(top.head(3).sum() / top.sum()), 3)},
    }


def archived_only(lk: pd.DataFrame, n: pd.DataFrame) -> dict:
    """Sensitivity: judged links whose page came from the in-window archive only (coverage differs by writer type)."""
    arc = lk[lk.archived].groupby("noteId").agg(n_j=("judged", "sum"), n_s=("sup", "sum"))
    d = n.drop(columns=["n_judged", "n_sup"]).merge(arc, left_on="noteId", right_index=True, how="left").fillna({"n_j": 0, "n_s": 0})
    d = d.rename(columns={"n_j": "n_judged", "n_s": "n_sup"})
    hp = d[d.stratum == "helpful_pair"]
    return {"link_level_unsupported": by_writer_type(hp, link_unsup),
            "n_judged_links": {"ai": int(hp[hp.ai].n_judged.sum()), "human": int(hp[~hp.ai].n_judged.sum())}}


def run(judge: str) -> dict:
    lk = links(judge)
    n = notes(lk)
    return {"descriptive": descriptive(lk, n), "H1_C1": h1_c1(n), "H7": h7(lk, n), "C2": c2(lk, n),
            "H6": h6(n), "H3_C3": h3(n), "C4": c4(n), "C5": c5(n), "C6": c6(n),
            "sensitivity_archived_only": archived_only(lk, n)}


def main() -> None:
    gold = json.loads(Path("results/gold.json").read_text())["judges"]["primary_judge"] if Path("results/gold.json").exists() else None
    out = {"primary_judge": gold, "judges": {j: run(j) for j in JUDGES}}
    OUT.write_text(json.dumps(out, indent=2, default=str))
    print(json.dumps(out, indent=2, default=str)[:6000])


if __name__ == "__main__":
    main()

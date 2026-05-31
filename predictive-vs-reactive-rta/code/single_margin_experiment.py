import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

from single_margin_simulator import (
    Cfg,
    conservative_crossing_zone_stopping_deadline,
    perceive,
    run_episode,
    theil_sen_slope,
)


RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


def calibration_run(cfg, severity, seed):
    rng = np.random.default_rng(10_000 + seed)
    vB = cfg.vB_conflict
    xA, vA, yB = cfg.x0_A, cfg.v_nom, cfg.y0_B
    n = int(cfg.T_max / cfg.dt)
    Ms, Ts, noiseless_margins = [], [], []
    for step in range(n):
        t = step * cfg.dt
        M_noisy, _, TB_rem = perceive(cfg, xA, vA, yB, vB, severity, 1.0, rng)
        frac = min(1.0, max(0.0, abs(yB) / abs(cfg.y0_B)))
        TA_hat = (0.0 - xA) / max(vA, 0.05)
        g = (TB_rem + severity * frac) - TA_hat
        Mn = abs(g) - cfg.k_sigma * (cfg.sigma0 + cfg.sigma_range * frac) - cfg.Gsafe
        Ms.append(M_noisy)
        Ts.append(t)
        noiseless_margins.append(Mn)
        xA += vA * cfg.dt
        yB += vB * cfg.dt
        if xA >= 0:
            break
    noiseless_margins = np.array(noiseless_margins)
    Ts = np.array(Ts)
    below = np.where(noiseless_margins <= 0)[0]
    if len(below) == 0:
        return []
    t_M0 = Ts[below[0]]
    pairs = []
    w = cfg.slope_window
    for i in range(len(Ts)):
        if Ts[i] >= t_M0:
            break
        slope = theil_sen_slope(
            Ts[max(0, i - w + 1) : i + 1], Ms[max(0, i - w + 1) : i + 1]
        )
        if slope < -1e-3:
            T_A = Ms[i] / -slope
            realized_remaining = t_M0 - Ts[i]
            if 0 < realized_remaining <= 6.0 and np.isfinite(T_A):
                pairs.append((realized_remaining, min(T_A, 12.0)))
    return pairs


def main():
    cfg = Cfg()
    severities = [0.0, 2.0, 4.0, 5.0, 6.0, 8.0, 10.0]
    methods = ["B0", "B2", "P"]
    seeds = list(range(40))
    continuous_deadline = conservative_crossing_zone_stopping_deadline(cfg)
    if continuous_deadline is None:
        raise RuntimeError(
            "A cannot stop before the crossing zone from its initial state"
        )
    stopping_deadline = np.floor(continuous_deadline / cfg.dt + 1e-12) * cfg.dt
    print(
        "conservative crossing-zone stopping deadline "
        f"(control grid) = {stopping_deadline:.2f} s\n"
    )

    rows = {}
    for cond in ["conflict", "clear"]:
        for m in methods:
            for sev in severities:
                res = [run_episode(cfg, m, sev, cond, s) for s in seeds]
                coll = np.mean([r["collision"] for r in res])
                success = np.mean([r["successful"] for r in res])
                yld = np.mean([r["yielded"] for r in res])
                delays = [r["elapsed_time"] for r in res]
                leads = [
                    stopping_deadline - r["t_yield"]
                    for r in res
                    if r["t_yield"] is not None
                ]
                rows[(cond, m, sev)] = dict(
                    coll=coll,
                    success=success,
                    yld=yld,
                    delay=np.mean(delays),
                    lead=np.mean(leads) if leads else np.nan,
                    lead_sd=np.std(leads) if leads else np.nan,
                )

    print("CONFLICT  (collision / success / mean elapsed[s] / mean deadline lead[s])")
    print(f"{'sev':>4} | " + " | ".join(f"{m:^32}" for m in methods))
    for sev in severities:
        cells = []
        for m in methods:
            r = rows[("conflict", m, sev)]
            cells.append(
                f"col {r['coll']:.2f} suc {r['success']:.2f} "
                f"t {r['delay']:4.1f} L {r['lead']:+.1f}"
            )
        print(f"{sev:>4} | " + " | ".join(f"{c:^32}" for c in cells))

    print("\nCLEAR  (unnecessary-yield rate / success rate)  -- specificity check")
    print(f"{'sev':>4} | " + " | ".join(f"{m:^20}" for m in methods))
    for sev in severities:
        cells = []
        for m in methods:
            r = rows[("clear", m, sev)]
            cells.append(f"yield {r['yld']:.2f}  suc {r['success']:.2f}")
        print(f"{sev:>4} | " + " | ".join(f"{c:^20}" for c in cells))

    pairs = []
    for sev in [4.0, 6.0, 8.0]:
        for s in seeds:
            pairs += calibration_run(cfg, sev, s)
    pairs = np.array(pairs)
    if len(pairs):
        realized_remaining, pred = pairs[:, 0], pairs[:, 1]
        slope_fit = np.sum(realized_remaining * pred) / np.sum(
            realized_remaining * realized_remaining
        )
        mae = np.mean(np.abs(pred - realized_remaining))
        print(
            "\nCALIBRATION  (projected vs realized time to noiseless M=0):  "
            f"slope={slope_fit:.2f}  MAE={mae:.2f}s  n={len(pairs)}"
        )

    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    ax = axes.ravel()
    colors = {"B0": "#888888", "B2": "#d1495b", "P": "#2e86ab"}
    for m in methods:
        success = [rows[("conflict", m, s)]["success"] for s in severities]
        coll = [rows[("conflict", m, s)]["coll"] for s in severities]
        lead = [rows[("conflict", m, s)]["lead"] for s in severities]
        ax[0].plot(severities, success, "o-", color=colors[m], label=m, lw=2)
        ax[1].plot(severities, coll, "o-", color=colors[m], label=m, lw=2)
        ax[3].plot(severities, lead, "o-", color=colors[m], label=m, lw=2)
    ax[0].set(
        title="Success rate vs severity (CONFLICT)",
        xlabel="fault severity (s of hidden bias)",
        ylabel="success rate",
        ylim=(-0.05, 1.05),
    )
    ax[1].set(
        title="Collision rate vs severity (CONFLICT)",
        xlabel="fault severity (s of hidden bias)",
        ylabel="collision rate",
        ylim=(-0.05, 1.05),
    )
    ax[3].axhline(0, color="k", lw=1, ls=":")
    ax[3].set(
        title="Lead relative to the conservative stopping deadline",
        xlabel="fault severity (s of hidden bias)",
        ylabel="lead time (s)  >0 = acted before deadline",
    )
    for a in (ax[0], ax[1], ax[3]):
        a.legend()
        a.grid(alpha=0.3)

    if len(pairs):
        ax[2].scatter(pairs[:, 0], pairs[:, 1], s=8, alpha=0.3, color="#2e86ab")
        lim = 6
        ax[2].plot([0, lim], [0, lim], "k--", lw=1, label="ideal (y=x)")
        ax[2].set(
            title=f"P calibration  (slope={slope_fit:.2f}, MAE={mae:.2f}s)",
            xlabel="realized time to noiseless margin crossing (s)",
            ylabel="P predicted T_A (s)",
            xlim=(0, lim),
            ylim=(0, lim),
        )
        ax[2].legend()
        ax[2].grid(alpha=0.3)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RESULTS_DIR / "single_margin_diagnostic.png"
    fig.tight_layout()
    fig.savefig(output_path, dpi=130)
    plt.close(fig)
    print(f"\nsaved plot -> {output_path}")


if __name__ == "__main__":
    main()

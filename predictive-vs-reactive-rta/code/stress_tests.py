import numpy as np

from single_margin_simulator import Cfg, perceive, run_episode, theil_sen_slope


def summarize(
    cfg, method, pad=0.0, conv_p=1.0, severities=(2, 4, 5, 6, 8, 10), seeds=40
):
    seeds = range(seeds)
    max_coll, elapsed_times, clear_fy = 0.0, [], []
    for sev in severities:
        c = [
            run_episode(
                cfg,
                method,
                sev,
                "conflict",
                s,
                fixed_pad=pad,
                degradation_exponent=conv_p,
            )
            for s in seeds
        ]
        cl = [
            run_episode(
                cfg,
                method,
                sev,
                "clear",
                s,
                fixed_pad=pad,
                degradation_exponent=conv_p,
            )
            for s in seeds
        ]
        max_coll = max(max_coll, np.mean([r["collision"] for r in c]))
        elapsed_times.append(np.mean([r["elapsed_time"] for r in c]))
        clear_fy.append(np.mean([r["yielded"] for r in cl]))
    return max_coll, float(np.mean(elapsed_times)), float(np.mean(clear_fy))


def calib2(cfg, conv_p, severities=(4, 6, 8), seeds=40):
    pairs = []
    for sev in severities:
        for s in range(seeds):
            rng = np.random.default_rng(10_000 + s)
            xA, vA, yB = cfg.x0_A, cfg.v_nom, cfg.y0_B
            Ms, Ts, Mt = [], [], []
            for step in range(int(cfg.T_max / cfg.dt)):
                t = step * cfg.dt
                M_noisy, _, TB_rem = perceive(
                    cfg, xA, vA, yB, cfg.vB_conflict, sev, conv_p, rng
                )
                frac = min(1.0, max(0.0, abs(yB) / abs(cfg.y0_B)))
                TA_hat = (0.0 - xA) / max(vA, 0.05)
                g = (TB_rem + sev * (frac**conv_p)) - TA_hat
                Mn = (
                    abs(g)
                    - cfg.k_sigma * (cfg.sigma0 + cfg.sigma_range * frac)
                    - cfg.Gsafe
                )
                Ms.append(M_noisy)
                Ts.append(t)
                Mt.append(Mn)
                xA += vA * cfg.dt
                yB += cfg.vB_conflict * cfg.dt
                if xA >= 0:
                    break
            Mt = np.array(Mt)
            Ts = np.array(Ts)
            below = np.where(Mt <= 0)[0]
            if len(below) == 0:
                continue
            t_M0 = Ts[below[0]]
            w = cfg.slope_window
            for i in range(len(Ts)):
                if Ts[i] >= t_M0:
                    break
                sl = theil_sen_slope(
                    Ts[max(0, i - w + 1) : i + 1], Ms[max(0, i - w + 1) : i + 1]
                )
                if sl < -1e-3:
                    T_A = Ms[i] / -sl
                    tr = t_M0 - Ts[i]
                    if 0 < tr <= 6.0 and np.isfinite(T_A):
                        pairs.append((tr, min(T_A, 12.0)))
    pairs = np.array(pairs)
    if len(pairs) == 0:
        return None
    tr, pr = pairs[:, 0], pairs[:, 1]
    slope = np.sum(tr * pr) / np.sum(tr * tr)
    mae = np.mean(np.abs(pr - tr))
    return slope, mae, len(pairs)


def first_break_sev(cfg, method, pad=0.0, thresh=0.5, seeds=40):
    for sev in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 14]:
        c = [
            run_episode(cfg, method, sev, "conflict", s, fixed_pad=pad)
            for s in range(seeds)
        ]
        if np.mean([r["collision"] for r in c]) >= thresh:
            return sev
    return None


def main():
    cfg = Cfg()

    print("=" * 74)
    print("A. PADDED REACTIVE (B2p) vs PREDICTIVE (P)   [fixed-pad comparison]")
    print("   max collision (want 0) | mean conflict elapsed s (lower=less over-yield)")
    print("   | CLEAR false-yield rate (lower=better specificity)")
    print("-" * 74)
    mc, fin, fy = summarize(cfg, "P")
    print(
        f"  P               :  maxcoll {mc:.2f}   elapsed {fin:5.1f}   clearFY {fy:.2f}"
    )
    for pad in [0.0, 0.5, 1.0, 1.5, 2.0, 3.0]:
        mc, fin, fy = summarize(cfg, "B2p", pad=pad)
        print(
            f"  B2 pad={pad:<4}     :  maxcoll {mc:.2f}   elapsed {fin:5.1f}   clearFY {fy:.2f}"
        )

    print("\n" + "=" * 74)
    print(
        "B. BRAKING RATE a_max  ->  first severity with >=50% collision (higher=robust)"
    )
    print("-" * 74)
    print(f"  {'a_max':>6} | {'B2 (pad0)':>10} | {'P':>6}")
    for a_max in [0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0]:
        sweep_cfg = Cfg(a_max=a_max)
        reactive_break = first_break_sev(sweep_cfg, "B2p", pad=0.0)
        predictive_break = first_break_sev(sweep_cfg, "P")
        print(f"  {a_max:>6} | {str(reactive_break):>10} | {str(predictive_break):>6}")
    print("  (None = never broke up to severity 14)")

    print("\n" + "=" * 74)
    print("C. CONVEX DEGRADATION  (bias ~ frac^2; linear projection should struggle)")
    print("-" * 74)
    for label, exponent in [("linear (frac^1)", 1.0), ("convex (frac^2)", 2.0)]:
        p_collision, p_elapsed, _ = summarize(cfg, "P", conv_p=exponent)
        b_collision, b_elapsed, _ = summarize(cfg, "B2p", pad=0.0, conv_p=exponent)
        calibration = calib2(cfg, conv_p=exponent)
        calibration_text = (
            f"slope {calibration[0]:.2f} MAE {calibration[1]:.2f}s"
            if calibration
            else "n/a"
        )
        print(f"  {label}:")
        print(
            f"     P  : maxcoll {p_collision:.2f}  elapsed {p_elapsed:5.1f}   "
            f"calibration {calibration_text}"
        )
        print(f"     B2 : maxcoll {b_collision:.2f}  elapsed {b_elapsed:5.1f}")

    print("\n" + "=" * 74)
    print("D. WIDE RATE RANGE  ->  per-severity collision / mean elapsed s")
    print("   If no single pad is both safe at high sev AND non-over-yielding at low")
    print("   sev, while P is, then the rate-adaptivity of P is doing real work.")
    print("-" * 74)
    severities = [1, 3, 6, 9, 12, 14]
    variants = [("P", None), ("pad1.0", 1.0), ("pad1.5", 1.5), ("pad2.5", 2.5)]
    print(f"  {'sev':>4} | " + " | ".join(f"{name:^14}" for name, _ in variants))
    for severity in severities:
        cells = []
        for _, pad in variants:
            method = "P" if pad is None else "B2p"
            results = [
                run_episode(
                    cfg,
                    method,
                    severity,
                    "conflict",
                    seed,
                    fixed_pad=pad or 0.0,
                )
                for seed in range(40)
            ]
            collision = np.mean([result["collision"] for result in results])
            elapsed = np.mean([result["elapsed_time"] for result in results])
            cells.append(f"c{collision:.2f} t{elapsed:4.1f}")
        print(f"  {severity:>4} | " + " | ".join(f"{cell:^14}" for cell in cells))


if __name__ == "__main__":
    main()

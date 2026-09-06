import numpy as np
from dataclasses import dataclass


DEFAULT_PADS = (0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0)
DEFAULT_SEEDS = 30


@dataclass
class Cfg:
    dt: float = 0.1
    T_max: float = 45.0
    N: int = 3
    d0: tuple = (12.0, 13.6, 15.2)
    d0_clear: tuple = (12.0, 18.0, 24.0)
    v_nom: float = 1.2
    a_max: float = 2.5
    R_zone: float = 0.5
    H_req: float = 1.5
    sigma0: float = 0.15
    sigma_range: float = 0.45
    k_sigma: float = 1.0
    meas_noise: float = 0.05
    T_needed: float = 2.0
    slope_window: int = 8
    exit_dist: float = 8.0
    hetero_pattern: tuple = (1.0, 1.6, 0.6)


def theil_sen(ts, ys):
    ts = np.asarray(ts)
    ys = np.asarray(ys)
    if len(ts) < 2:
        return 0.0
    sl = [
        (ys[j] - ys[i]) / (ts[j] - ts[i])
        for i in range(len(ts))
        for j in range(i + 1, len(ts))
        if ts[j] != ts[i]
    ]
    return float(np.median(sl)) if sl else 0.0


def run_episode(cfg, method, sev_scale, hetero, condition, seed, pad=0.0, conv_p=1.0):
    rng = np.random.default_rng(seed)
    d0 = np.array(cfg.d0 if condition == "conflict" else cfg.d0_clear, float)
    s = d0.copy()
    v = np.full(cfg.N, cfg.v_nom)
    sev = sev_scale * (np.array(cfg.hetero_pattern) if hetero else np.ones(cfg.N))
    yielding = np.zeros(cfg.N, bool)
    yield_for = -np.ones(cfg.N, int)
    resumed = np.zeros(cfg.N, bool)
    collision = False
    Ms, Ts = [], []

    def perceive():
        TA = (s - cfg.R_zone) / np.maximum(v, 0.05)
        frac = np.clip((s - cfg.R_zone) / (d0 - cfg.R_zone), 0, 1)
        bias = sev * (frac**conv_p)
        sigma = cfg.sigma0 + cfg.sigma_range * frac
        That = TA + bias
        return That, sigma, TA

    def m_coord(active):
        That, sigma, _ = perceive()
        idx = [i for i in active if s[i] > cfg.R_zone]
        if len(idx) < 2:
            return np.inf, None
        best, pair = np.inf, None
        for a in range(len(idx)):
            for b in range(a + 1, len(idx)):
                i, j = idx[a], idx[b]
                head = (
                    abs(That[i] - That[j])
                    - cfg.k_sigma * (sigma[i] + sigma[j])
                    - cfg.H_req
                )
                if head < best:
                    best = head
                    later = i if That[i] > That[j] else j
                    pair = (i, j, later)
        return best, pair

    n = int(cfg.T_max / cfg.dt)
    for step in range(n):
        t = step * cfg.dt
        active = [i for i in range(cfg.N) if not yielding[i]]
        Mc, pair = m_coord(active)
        Mc_noisy = Mc + rng.normal(0, cfg.meas_noise) if np.isfinite(Mc) else Mc
        Ms.append(Mc_noisy if np.isfinite(Mc_noisy) else (Ms[-1] if Ms else 5.0))
        Ts.append(t)

        trigger = False
        if pair is not None:
            if method == "B0":
                That, _, _ = perceive()
                i, j, later = pair
                trigger = abs(That[i] - That[j]) < cfg.H_req
            elif method == "B2p":
                trigger = Mc_noisy <= pad
            elif method == "P":
                w = cfg.slope_window
                sl = theil_sen(Ts[-w:], Ms[-w:]) if len(Ms) >= 2 else 0.0
                T_A = (Mc_noisy / -sl) if sl < -1e-3 else np.inf
                trigger = (T_A <= cfg.T_needed) or (Mc_noisy <= 0)
        if trigger and pair is not None:
            _, _, later = pair
            earlier = pair[0] if pair[1] == later else pair[1]
            if not yielding[later]:
                yielding[later] = True
                yield_for[later] = earlier

        for i in range(cfg.N):
            if yielding[i] and not resumed[i]:
                target = 0.0
                jf = yield_for[i]
                if jf < 0 or s[jf] < -cfg.R_zone:
                    resumed[i] = True
                    target = cfg.v_nom
            else:
                target = cfg.v_nom
            dv = np.clip(target - v[i], -cfg.a_max * cfg.dt, cfg.a_max * cfg.dt)
            v[i] = max(0.0, v[i] + dv)
            s[i] -= v[i] * cfg.dt

        if np.sum(np.abs(s) < cfg.R_zone) >= 2:
            collision = True
        if np.all(s <= -cfg.exit_dist):
            break

    completed = bool(np.all(s <= -cfg.exit_dist) and not collision)
    return dict(collision=collision, completed=completed, t_done=t)


def pooled(cfg, method, hetero, pad, conv_p, sev_scales, seeds):
    coll, fin = [], []
    for sc in sev_scales:
        for s in range(seeds):
            r = run_episode(cfg, method, sc, hetero, "conflict", s, pad, conv_p)
            coll.append(r["collision"])
            fin.append(r["t_done"])
    return float(np.mean(coll)), float(np.mean(fin))


def best_safe_pad(cfg, hetero, conv_p, sev_scales, seeds, pads):
    best = None
    for pad in pads:
        c, f = pooled(cfg, "B2p", hetero, pad, conv_p, sev_scales, seeds)
        if c <= 1e-9:
            if best is None or f < best[1]:
                best = (pad, f, c)
    return best


def coordination_comparisons(cfg=None, pads=DEFAULT_PADS, seeds=DEFAULT_SEEDS):
    cfg = Cfg() if cfg is None else cfg
    cases = (
        (False, "HOMOGENEOUS rates", (2, 3), "narrow rate range"),
        (False, "HOMOGENEOUS rates", (1, 2, 3, 4, 5, 6), "wide rate range"),
        (True, "HETEROGENEOUS rates (coord-specific)", (2, 3), "narrow rate range"),
        (
            True,
            "HETEROGENEOUS rates (coord-specific)",
            (1, 2, 3, 4, 5, 6),
            "wide rate range",
        ),
    )
    for hetero, group, scales, range_name in cases:
        p_collision, p_finish = pooled(cfg, "P", hetero, 0.0, 1.0, scales, seeds)
        reactive = best_safe_pad(cfg, hetero, 1.0, scales, seeds, pads)
        yield {
            "heterogeneous": hetero,
            "group": group,
            "range": range_name,
            "scales": scales,
            "predictive_collision": p_collision,
            "predictive_finish": p_finish,
            "reactive": reactive,
        }


def main():
    cfg = Cfg()
    pads = DEFAULT_PADS
    seeds = DEFAULT_SEEDS

    print("=" * 72)
    print("LEGACY COORDINATION PROTOTYPE (3 robots, shared intersection)")
    print("P vs the BEST tuned fixed pad.  advantage = best_safe_pad_finish - P_finish")
    print("(>0 = lower mean finish time for P; compare collision rates separately)")
    print("=" * 72)

    last_group = None
    for row in coordination_comparisons(cfg, pads, seeds):
        if row["group"] != last_group:
            print(f"\n--- {row['group']} ---")
            last_group = row["group"]
        p_collision = row["predictive_collision"]
        p_finish = row["predictive_finish"]
        reactive = row["reactive"]
        if reactive is None:
            reactive_text = "no fixed pad is safe"
            advantage = "only-P-safe" if p_collision <= 1e-9 else "both fail"
        else:
            reactive_text = f"pad={reactive[0]} finish={reactive[1]:.1f}"
            advantage = (
                f"{reactive[1] - p_finish:+.1f}s"
                if p_collision <= 1e-9
                else f"P UNSAFE (coll {p_collision:.2f})"
            )
        p_safety = "safe" if p_collision <= 1e-9 else f"coll {p_collision:.2f}"
        print(
            f"  {row['range']:18} | P: {p_safety} finish {p_finish:5.1f} | "
            f"best reactive: {reactive_text:22} | advantage {advantage}"
        )

    print("\n--- degradation-shape sweep (heterogeneous, wide range) ---")
    scales = (1, 2, 3, 4, 5, 6)
    for p, label in (
        (0.3, "near-abrupt frac^0.3"),
        (1.0, "linear frac^1"),
        (2.0, "convex frac^2"),
    ):
        p_collision, p_finish = pooled(cfg, "P", True, 0.0, p, scales, seeds)
        reactive = best_safe_pad(cfg, True, p, scales, seeds, pads)
        p_safety = "safe" if p_collision <= 1e-9 else f"coll {p_collision:.2f}"
        if reactive is None:
            line = f"best reactive: none safe | advantage {'only-P-safe' if p_collision <= 1e-9 else 'both fail'}"
        elif p_collision <= 1e-9:
            line = (
                f"best reactive pad={reactive[0]} finish={reactive[1]:.1f} | "
                f"advantage {reactive[1] - p_finish:+.1f}s"
            )
        else:
            line = f"P UNSAFE coll {p_collision:.2f}"
        print(f"  {label:22} | P: {p_safety} finish {p_finish:5.1f} | {line}")


if __name__ == "__main__":
    main()

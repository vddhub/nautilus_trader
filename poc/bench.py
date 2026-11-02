"""Resource benchmark: standalone nodes vs shared-feed + tenant nodes.

Spawns node subprocesses, samples USS (true unique RAM) + CPU per process,
reports per-process and aggregate. Signal payloads do not cross the live
external bus in this wheel (see caveat), so CPU reflects node steady-state,
not heavy market-data decode. RAM footprint is faithful.
"""
import re
import subprocess
import time

import psutil


def footprint_mb(pid):
    """macOS true private memory (excludes shared libs), like USS. 0.0 if unavailable."""
    try:
        out = subprocess.run(["vmmap", "-summary", str(pid)], capture_output=True, text=True, timeout=10).stdout
        m = re.search(r"Physical footprint:\s+([\d.]+)([KMG])", out)
        if not m:
            return 0.0
        val, unit = float(m.group(1)), m.group(2)
        return val * {"K": 1e-3, "M": 1.0, "G": 1e3}[unit]
    except Exception:
        return 0.0

VENV_PY = "/tmp/nt-poc-venv/bin/python"
POC = "/tmp/nt-poc"
WARMUP_S = 6.0
SAMPLE_S = 12.0
INTERVAL = 0.5
N_TENANTS = 3


def spawn(args, log):
    f = open(log, "w")
    return subprocess.Popen([VENV_PY, *args], stdout=f, stderr=subprocess.STDOUT, cwd=POC)


def sample(procs):
    """Return dict pid -> (uss_mb, cpu_pct) averaged over the sample window."""
    ps = {p.pid: psutil.Process(p.pid) for p in procs}
    for pr in ps.values():
        pr.cpu_percent(None)  # prime
    uss = {pid: [] for pid in ps}
    cpu = {pid: [] for pid in ps}
    t_end = time.time() + SAMPLE_S
    while time.time() < t_end:
        time.sleep(INTERVAL)
        for pid, pr in ps.items():
            try:
                uss[pid].append(pr.memory_info().rss / 1e6)
                cpu[pid].append(pr.cpu_percent(None))
            except psutil.Error:
                pass
    return {pid: (sum(uss[pid]) / len(uss[pid]), sum(cpu[pid]) / len(cpu[pid])) for pid in ps if uss[pid]}


def run_scenario(name, specs):
    print(f"\n=== scenario: {name} ===")
    mem_before = psutil.virtual_memory().used
    procs = [spawn(args, f"{POC}/{tag}.log") for tag, args in specs]
    time.sleep(WARMUP_S)
    mem_after = psutil.virtual_memory().used
    sys_delta_mb = (mem_after - mem_before) / 1e6
    alive = [p for p in procs if p.poll() is None]
    if len(alive) != len(procs):
        print(f"  WARN: {len(procs)-len(alive)} node(s) died before sampling; check logs")
    stats = sample(alive)
    foot = {p.pid: footprint_mb(p.pid) for p in alive}
    for p in procs:
        p.terminate()
    for p in procs:
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
    rows = []
    tag_by_pid = {p.pid: tag for p, (tag, _) in zip(procs, specs)}
    tot_rss = tot_cpu = tot_foot = 0.0
    for pid, (rss, cpu) in stats.items():
        fp = foot.get(pid, 0.0)
        rows.append((tag_by_pid.get(pid, str(pid)), rss, fp, cpu))
        tot_rss += rss
        tot_foot += fp
        tot_cpu += cpu
    rows.sort()
    print(f"  {'node':<16}{'RSS MB':>10}{'PRIV MB':>10}{'CPU %':>8}")
    for tag, rss, fp, cpu in rows:
        print(f"  {tag:<16}{rss:>10.1f}{fp:>10.1f}{cpu:>8.1f}")
    print(f"  {'TOTAL':<16}{tot_rss:>10.1f}{tot_foot:>10.1f}{tot_cpu:>8.1f}  (n={len(rows)})")
    print(f"  (PRIV = macOS physical footprint, true private RAM per process)")
    return rows


def main():
    subprocess.run(["redis-cli", "flushall"], capture_output=True)

    # Standalone: N independent nodes, each with own synthetic feed actor.
    standalone = [(f"solo{i}", ["feed.py", f"SOLO-{i:03d}", f"solo{i}"]) for i in range(N_TENANTS)]
    s_rows = run_scenario("standalone (N self-feeding nodes)", standalone)

    subprocess.run(["redis-cli", "flushall"], capture_output=True)

    # Shared: 1 feed node + N tenant nodes consuming its external stream.
    shared = [("feed", ["feed.py", "FEED-001", "demo"])]
    shared += [(f"ten{i}", ["tenant.py", f"TEN-{i:03d}", f"ten{i}", "trader-FEED-001:demo"]) for i in range(N_TENANTS)]
    h_rows = run_scenario("shared (1 feed + N tenants)", shared)

    s_priv = sum(fp for _, _, fp, _ in s_rows)
    s_cpu = sum(c for _, _, _, c in s_rows)
    h_priv = sum(fp for _, _, fp, _ in h_rows)
    h_cpu = sum(c for _, _, _, c in h_rows)
    feed_priv = next((fp for t, _, fp, _ in h_rows if t == "feed"), 0.0)
    ten_privs = [fp for t, _, fp, _ in h_rows if t != "feed"]
    ten_avg = sum(ten_privs) / len(ten_privs) if ten_privs else 0.0
    s_avg = s_priv / len(s_rows) if s_rows else 0.0

    print("\n=== summary (PRIV = true private RAM) ===")
    print(f"  standalone {len(s_rows)} nodes:  total {s_priv:.1f} MB, {s_cpu:.1f}% CPU  -> {s_avg:.1f} MB/node")
    print(f"  shared 1 feed + {len(ten_privs)} tenants: total {h_priv:.1f} MB, {h_cpu:.1f}% CPU")
    print(f"    feed node:   {feed_priv:.1f} MB")
    print(f"    tenant avg:  {ten_avg:.1f} MB/tenant")
    print(f"  per-node RAM: standalone {s_avg:.1f} MB  vs  shared-tenant {ten_avg:.1f} MB")
    print(f"  marginal cost of +1 tenant ~= {ten_avg:.1f} MB; one-time feed overhead = {feed_priv:.1f} MB")


if __name__ == "__main__":
    main()

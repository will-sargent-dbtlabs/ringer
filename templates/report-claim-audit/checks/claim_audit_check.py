#!/usr/bin/env python3
"""Generic claim-audit check for Ringer.

Compares a worker's recomputed figures (audit.json) against an authoritative
independent recompute produced by --truth-cmd (a command that prints canonical
JSON to stdout). Every audited key must match (floats within --tol). Prints WHY
on mismatch. The worker never sees the truth command — two workers running the
same check independently is the cross-check.

  claim_audit_check.py --audit audit.json --truth-cmd 'python3 truth_recompute.py' [--tol 0.1]
"""
import argparse, json, os, shlex, subprocess, sys


def flat(d, prefix=""):
    out = {}
    for k, v in (d or {}).items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flat(v, key + "."))
        else:
            out[key] = v
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", required=True, help="worker's audit.json")
    ap.add_argument("--truth-cmd", required=True, help="shell command printing canonical truth JSON")
    ap.add_argument("--tol", type=float, default=0.1)
    a = ap.parse_args()

    if not os.path.isfile(a.audit):
        print(f"FAIL: worker audit file not found: {a.audit}"); return 1
    try:
        worker = json.load(open(a.audit))
    except Exception as e:
        print(f"FAIL: audit.json is not valid JSON: {e}"); return 1

    try:
        truth = json.loads(subprocess.check_output(shlex.split(a.truth_cmd), text=True))
    except Exception as e:
        print(f"FAIL: truth-cmd did not produce valid JSON ({e}) — fix the check, not the worker"); return 1

    T, W = flat(truth), flat(worker)
    ok = True
    for key, tv in T.items():
        if key not in W:
            print(f"FAIL: {key}: missing from worker audit (truth={tv})"); ok = False; continue
        wv = W[key]
        try:
            if isinstance(tv, float) or isinstance(wv, float):
                if abs(float(wv) - float(tv)) > a.tol:
                    print(f"FAIL: {key}: worker={wv} truth={tv} (> tol {a.tol})"); ok = False
            elif wv != tv:
                print(f"FAIL: {key}: worker={wv} truth={tv}"); ok = False
        except (TypeError, ValueError):
            print(f"FAIL: {key}: worker={wv!r} not comparable to truth={tv!r}"); ok = False

    if ok:
        print(f"PASS: all {len(T)} audited figures match the independent recompute")
        return 0
    print("truth was:", json.dumps(truth))
    return 1


if __name__ == "__main__":
    sys.exit(main())

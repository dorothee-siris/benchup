"""ops/contract_check.py -- validates a directory of tables against docs/data_contract.yaml.

Pattern adapted from the Lorraine Phase-2 Explorer's pipeline/60_deploy.py validator (see
app/docs/VENDORED.md). `check(tables_dir, contract)` returns a list of violation strings
(empty = clean). CLI prints a per-table verdict and exits 1 on any violation.

Usage:
  python ops/contract_check.py [--dir data] [--contract docs/data_contract.yaml]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]


def _read_table(path: Path) -> pd.DataFrame:
    if path.suffix == ".csv":
        return pd.read_csv(path)
    return pd.read_parquet(path)


def _load_source_schemas(tables_dir: Path) -> dict | None:
    """source_manifest.json (app/data/) or manifest.json (data/artefacts_eu/) -- either name,
    same content (verified byte-identical 2026-08-29). Returns table_schemas dict, or None if
    no manifest is present in this directory (undeclared-drop check is then skipped, not failed)."""
    for name in ("source_manifest.json", "manifest.json"):
        p = tables_dir / name
        if p.is_file():
            with open(p, encoding="utf-8") as f:
                return json.load(f).get("table_schemas", {})
    return None


def check(tables_dir: str | Path, contract: dict, resolve=None) -> list[str]:
    """Validate every file declared in contract['files']. Returns the full list of violations
    across all files (empty list = clean).

    `resolve(fname) -> Path` optionally overrides where each declared file is read from (deploy.py
    uses this at --check-only time, since the 8 parquet tables, type_overrides.csv and
    umbrella_supplement.csv are not all under one directory before deploy). Defaults to
    `tables_dir / fname` (the deployed-layout case: test_contract.py, the plain CLI). `tables_dir`
    itself is still used to locate source_manifest.json/manifest.json for the undeclared-drop check
    regardless of `resolve`.
    """
    tables_dir = Path(tables_dir)
    if resolve is None:
        resolve = lambda fname: tables_dir / fname  # noqa: E731
    policy = contract.get("policy", {})
    source_schemas = _load_source_schemas(tables_dir)
    violations: list[str] = []

    for fname, spec in contract["files"].items():
        path = resolve(fname)
        if not path.is_file():
            violations.append(f"{fname}: FILE NOT FOUND at {path}")
            continue
        try:
            df = _read_table(path)
        except Exception as exc:  # noqa: BLE001 -- report, don't crash the whole check
            violations.append(f"{fname}: could not read file ({exc})")
            continue

        declared = spec.get("columns") or []
        declared_names = [c["name"] for c in declared]

        # A. declared columns present, dtype matches
        for col in declared:
            name = col["name"]
            if name not in df.columns:
                if policy.get("fail_on_missing_column", True):
                    violations.append(f"{fname}: MISSING declared column {name!r}")
                continue
            real_dtype = str(df[name].dtype)
            if policy.get("fail_on_dtype_mismatch", True) and real_dtype != col["dtype"]:
                violations.append(
                    f"{fname}: DTYPE MISMATCH on {name!r}: declared {col['dtype']!r}, real {real_dtype!r}"
                )

        # B. keys unique and non-null
        keys = spec.get("keys") or []
        missing_keys = [k for k in keys if k not in df.columns]
        if missing_keys:
            violations.append(f"{fname}: KEY column(s) missing: {missing_keys}")
        elif keys:
            if df[keys].isna().any().any():
                violations.append(f"{fname}: KEY column(s) {keys} contain null(s)")
            n_dupes = int(df.duplicated(subset=keys).sum())
            if n_dupes and policy.get("fail_on_key_duplication", True):
                violations.append(f"{fname}: KEY {keys} not unique: {n_dupes} duplicate row(s)")

        # C. undeclared drop vs source_manifest.json table_schemas (parquet tables only --
        # csv overrides files have no table_schemas entry and are skipped by construction)
        base = Path(fname).stem
        if source_schemas is not None and base in source_schemas:
            source_cols = set(source_schemas[base].get("columns", {}).keys())
            undeclared_drop = source_cols - set(declared_names) - set(df.columns)
            # a column the SOURCE MANIFEST lists, that this contract does not declare, AND
            # that is truly absent from the built table -- distinct from B's missing-column
            # check (which only fires for columns the CONTRACT itself declares).
            still_present_undeclared = source_cols - set(declared_names)
            for col in sorted(still_present_undeclared):
                if col not in df.columns and policy.get("fail_on_undeclared_drop", True):
                    violations.append(
                        f"{fname}: UNDECLARED DROP of source column {col!r} "
                        f"(present in source_manifest.json table_schemas.{base}, "
                        f"absent from both this table and the contract)"
                    )

        # D. extra (undeclared) columns -- logged by the CLI, never fatal
        extra = [c for c in df.columns if c not in declared_names]
        if extra and policy.get("fail_on_extra_column", False):
            violations.append(f"{fname}: EXTRA undeclared column(s) present: {extra}")

    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default="data", help="directory of tables to check (default: data)")
    parser.add_argument("--contract", default=None, help="path to data_contract.yaml")
    args = parser.parse_args()

    contract_path = Path(args.contract) if args.contract else ROOT / "docs" / "data_contract.yaml"
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    tables_dir = Path(args.dir)

    print(f"contract      : {contract_path} (v{contract.get('contract_version')})")
    print(f"tables dir    : {tables_dir}")
    print()

    violations = check(tables_dir, contract)

    # per-table verdict printout
    by_file: dict[str, list[str]] = {fname: [] for fname in contract["files"]}
    for v in violations:
        fname = v.split(":", 1)[0]
        by_file.setdefault(fname, []).append(v)

    for fname in contract["files"]:
        vs = by_file.get(fname, [])
        if vs:
            print(f"--- {fname}: FAIL ({len(vs)}) ---")
            for v in vs:
                print(f"  ! {v}")
        else:
            print(f"--- {fname}: PASS ---")

    print()
    if violations:
        print(f"contract_check FAILED -- {len(violations)} violation(s)")
        return 1
    print("contract_check OK -- all declared files/columns/keys verified")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:  # pragma: no cover
        pass
    sys.exit(main())

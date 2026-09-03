"""ops/deploy.py -- validates the source tables against docs/data_contract.yaml, then copies
the contract's declared files into data/ (byte copies -- no re-serialization, so repeated runs
are byte-identical) and writes data/MANIFEST.json. Exits non-zero on ANY contract violation --
missing file, dtype/column mismatch, duplicate key, a declared file >= SIZE_LIMIT_MB (95 MB, the
GitHub 100 MB/file hard limit minus headroom), a missing/misshapen scenario file, or the whole
data/ folder over WHOLE_DIR_LIMIT_MB (700 MB) -- and prints a size-audit table (every declared
file's size + the total) on every run, check-only or not. Prints every table's verdict either
way. Pattern adapted from the Lorraine Phase-2 Explorer's pipeline/60_deploy.py (see
app/docs/VENDORED.md).

Source layout is config-driven over contract["files"] (27 files as of contract v1.5: 24 parquet
tables + 3 override csv), not hardcoded per table:
  - every parquet table comes from --source (default ../data/artefacts, relative to app/) --
    the generic fallback below, no per-table special-casing needed
  - the three overrides/*.csv (type_overrides, pool_exclusions, umbrella_supplement) are
    authored in place at app/data/overrides/ (the Annuaire-pattern locked override lists) --
    their own location IS the deploy target, so deploy is a validate-in-place no-op copy for
    all three; there is no separate override source directory in this project.
  - data/scenarios/ (the ranking engine's precomputed per-scenario substrates, contract v1.5)
    is NOT one of contract["files"] -- its members are not one-row-per-key tables, so the
    column/key machinery above does not fit them. It is validated structurally against
    docs/data_contract.yaml's `scenario_files` section (every declared path present; every
    declared array shape matches what that scenario's own meta.json records -- never
    re-derived by loading the array) and copied as a whole tree, the same way the declared
    files are copied one by one.

Usage:
  python ops/deploy.py [--source ../data/artefacts] [--check-only]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from contract_check import check  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]  # app/
SIZE_LIMIT_MB = 95   # GitHub's hard per-file limit is 100 MB; every declared/scenario file must
                      # stay strictly under 95 MB (headroom), or deploy fails non-zero.
SIZE_LIMIT_BYTES = SIZE_LIMIT_MB * 1024 * 1024
WHOLE_DIR_LIMIT_MB = 700   # contract v1.5: the deploy TARGET as a whole (declared files +
                           # data/scenarios/) must stay under 700 MB (raised from 400 MB when
                           # the scenarios folder was added -- docs/data_contract.yaml's own
                           # v1.5 changelog entry states the reason).
WHOLE_DIR_LIMIT_BYTES = WHOLE_DIR_LIMIT_MB * 1024 * 1024


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_source(fname: str, source_dir: Path) -> Path:
    """Where a declared file lives BEFORE deploy. Config-driven over the three override files
    (all three are authored in place at app/data/overrides/ -- validate-in-place, no copy);
    every other declared file (the 24 parquet tables) is source_dir/fname."""
    if fname.startswith("overrides/"):
        return ROOT / "data" / fname
    return source_dir / fname


def _scenario_root(source_dir: Path, contract: dict) -> Path:
    return source_dir / Path(contract["scenario_files"]["root"]).name


def check_scenarios(source_dir: Path, contract: dict) -> tuple[list[str], list[tuple[str, int]]]:
    """Validate data/scenarios/ against docs/data_contract.yaml's `scenario_files` section.
    Returns (violations, [(relpath, size_bytes), ...]) -- the second element feeds the size
    audit and the manifest, so a clean run only ever walks the tree once."""
    spec = contract.get("scenario_files")
    if not spec:
        return [], []
    root = _scenario_root(source_dir, contract)
    violations: list[str] = []
    size_rows: list[tuple[str, int]] = []

    def _check_file(rel: str) -> Path | None:
        p = root / rel
        size_rows.append((f"scenarios/{rel}", p.stat().st_size if p.is_file() else 0))
        if not p.is_file():
            violations.append(f"scenarios/{rel}: FILE NOT FOUND at {p}")
            return None
        if p.stat().st_size >= SIZE_LIMIT_BYTES:
            violations.append(
                f"scenarios/{rel}: FILE SIZE {p.stat().st_size:,} bytes "
                f"({p.stat().st_size / (1024 * 1024):.2f} MB) >= {SIZE_LIMIT_MB} MB hard limit")
        return p

    if not root.is_dir():
        violations.append(f"scenarios/: FOLDER NOT FOUND at {root}")
        return violations, size_rows

    for entry in spec.get("top_level", []):
        _check_file(entry["path"])

    common = spec.get("common/", {})
    for fname in common.get("files", []):
        _check_file(f"common/{fname}")

    for tree in ("original", "conservative", "bestfit"):
        for fname in ("fields_df.parquet", "subfields_df.parquet"):
            p = root / "frames_common" / tree / fname
            if p.is_file():
                size_rows.append((f"scenarios/frames_common/{tree}/{fname}", p.stat().st_size))

    scen_key = next(k for k in spec if k.startswith("<tree>_<basis>"))
    scen_spec = spec[scen_key]
    shapes = scen_spec.get("shapes", {})
    for tree_basis, want_shapes in shapes.items():
        folder = root / tree_basis
        meta_path = _check_file(f"{tree_basis}/meta.json")
        for fname in ("l0.npz", "l1.npz", "l2f.npz"):
            _check_file(f"{tree_basis}/{fname}")
        own_fields_df = folder / "fields_df.parquet"
        if own_fields_df.is_file():
            size_rows.append((f"scenarios/{tree_basis}/fields_df.parquet", own_fields_df.stat().st_size))

        if meta_path is None:
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            violations.append(f"scenarios/{tree_basis}/meta.json: could not parse ({exc})")
            continue
        arrays = meta.get("arrays", {})
        for dotted, want_shape in want_shapes.items():
            arr_name, field_name = dotted.split(".", 1)
            got_shape = arrays.get(arr_name, {}).get("shapes", {}).get(field_name)
            if got_shape != list(want_shape):
                violations.append(
                    f"scenarios/{tree_basis}/{arr_name}.npz[{field_name}]: SHAPE MISMATCH "
                    f"declared {want_shape}, meta.json says {got_shape}")

    return violations, size_rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="../data/artefacts",
                         help="directory the parquet tables and the scenarios/ folder are read from (default: ../data/artefacts)")
    parser.add_argument("--check-only", action="store_true", help="validate the source tables, do not copy/write MANIFEST")
    parser.add_argument("--contract", default=None, help="path to data_contract.yaml (default: docs/data_contract.yaml)")
    parser.add_argument("--out-dir", default=None, help="deploy target override (default: contract['deploy_target'], i.e. data/)")
    args = parser.parse_args()

    contract_path = Path(args.contract) if args.contract else ROOT / "docs" / "data_contract.yaml"
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    source_dir = (ROOT / args.source).resolve() if not Path(args.source).is_absolute() else Path(args.source)
    out_dir = Path(args.out_dir) if args.out_dir else ROOT / contract["deploy_target"]

    print(f"contract      : {contract_path} (v{contract.get('contract_version')}, snapshot {contract.get('snapshot')})")
    print(f"source dir    : {source_dir}")
    print(f"deploy target : {out_dir}")
    print(f"mode          : {'CHECK-ONLY' if args.check_only else 'VALIDATE + DEPLOY'}")
    print()

    resolver = lambda fname: resolve_source(fname, source_dir)  # noqa: E731
    violations = check(source_dir, contract, resolve=resolver)

    # size audit -- runs on every invocation, --check-only or not, since an oversized file must
    # fail the check before anything is copied, not just at copy time.
    size_rows: list[tuple[str, int]] = []
    for fname in contract["files"]:
        src = resolve_source(fname, source_dir)
        size = src.stat().st_size if src.is_file() else 0
        size_rows.append((fname, size))
        if src.is_file() and size >= SIZE_LIMIT_BYTES:
            violations.append(
                f"{fname}: FILE SIZE {size:,} bytes ({size / (1024 * 1024):.2f} MB) "
                f">= {SIZE_LIMIT_MB} MB hard limit"
            )

    scenario_violations, scenario_size_rows = check_scenarios(source_dir, contract)
    violations.extend(scenario_violations)
    size_rows.extend(scenario_size_rows)

    total_bytes = sum(s for _, s in size_rows)
    print(f"--- size audit ({SIZE_LIMIT_MB} MB/file limit, {len(contract['files'])} declared files "
          f"+ {len(scenario_size_rows)} scenario files) ---")
    for fname, size in size_rows:
        mb = size / (1024 * 1024)
        flag = "  !! OVER LIMIT" if size >= SIZE_LIMIT_BYTES else ""
        print(f"  {fname:<55} {mb:>9.2f} MB{flag}")
    total_mb = total_bytes / (1024 * 1024)
    over_whole = total_bytes >= WHOLE_DIR_LIMIT_BYTES
    print(f"  {'TOTAL':<55} {total_mb:>9.2f} MB{'  !! OVER ' + str(WHOLE_DIR_LIMIT_MB) + ' MB WHOLE-DIR LIMIT' if over_whole else ''}")
    print()
    if over_whole:
        violations.append(
            f"WHOLE DEPLOY TARGET {total_bytes:,} bytes ({total_mb:.2f} MB) >= {WHOLE_DIR_LIMIT_MB} MB limit")

    # per-file verdict (same shape as contract_check's own CLI printout)
    by_file: dict[str, list[str]] = {fname: [] for fname in contract["files"]}
    by_file["scenarios/"] = []
    for v in violations:
        key = v.split(":", 1)[0]
        if key.startswith("scenarios/") or key == "WHOLE DEPLOY TARGET":
            by_file.setdefault("scenarios/", []).append(v)
        else:
            by_file.setdefault(key, []).append(v)
    for fname in contract["files"]:
        vs = by_file.get(fname, [])
        src = resolve_source(fname, source_dir)
        if vs:
            print(f"--- {fname} (source: {src}): FAIL ({len(vs)}) ---")
            for v in vs:
                print(f"  ! {v}")
        else:
            print(f"--- {fname} (source: {src}): PASS ---")
    scen_vs = by_file.get("scenarios/", [])
    if scen_vs:
        print(f"--- scenarios/ (source: {_scenario_root(source_dir, contract)}): FAIL ({len(scen_vs)}) ---")
        for v in scen_vs:
            print(f"  ! {v}")
    else:
        print(f"--- scenarios/ (source: {_scenario_root(source_dir, contract)}): PASS ({len(scenario_size_rows)} files) ---")

    if violations:
        print(f"\nDEPLOY ABORTED -- {len(violations)} contract violation(s) found above.")
        return 1

    if args.check_only:
        print(f"\ncontract_check OK -- {len(contract['files'])} file(s) + scenarios/ "
              f"({len(scenario_size_rows)} files) verified, nothing copied (--check-only)")
        return 0

    # copy every declared file into out_dir, preserving its declared relative path
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_files: dict[str, dict] = {}
    for fname in contract["files"]:
        src = resolve_source(fname, source_dir)
        dest = out_dir / fname
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.resolve() != dest.resolve():
            shutil.copy2(src, dest)
        manifest_files[fname] = {
            "sha256": _sha256(dest),
            "n_rows": _n_rows(dest),
            "size_bytes": dest.stat().st_size,
        }
        print(f"  OK -> {dest} ({manifest_files[fname]['n_rows']:,} rows, {manifest_files[fname]['size_bytes']:,} bytes)")

    # copy the whole scenarios/ tree (not row-based tables -- no _n_rows call)
    scen_src_root = _scenario_root(source_dir, contract)
    scen_dest_root = out_dir / "scenarios"
    manifest_scenarios: dict[str, dict] = {}
    if scen_src_root.is_dir():
        for rel, _size in scenario_size_rows:
            rel_path = Path(rel[len("scenarios/"):])
            src = scen_src_root / rel_path
            dest = scen_dest_root / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            if src.resolve() != dest.resolve():
                shutil.copy2(src, dest)
            manifest_scenarios[str(rel_path.as_posix())] = {
                "sha256": _sha256(dest),
                "size_bytes": dest.stat().st_size,
            }
        print(f"  OK -> {scen_dest_root} ({len(manifest_scenarios)} files, "
              f"{sum(v['size_bytes'] for v in manifest_scenarios.values()):,} bytes)")

    manifest = {
        "deployed_at": datetime.now(timezone.utc).isoformat(),
        "snapshot": contract.get("snapshot"),
        "source_manifest_generated_at": contract.get("generated_at"),
        "contract_version": contract.get("contract_version"),
        "files": manifest_files,
        "scenarios": {
            "n_files": len(manifest_scenarios),
            "total_bytes": sum(v["size_bytes"] for v in manifest_scenarios.values()),
            "files": manifest_scenarios,
        },
        "type_overrides": {
            "sha256": manifest_files["overrides/type_overrides.csv"]["sha256"],
            "n_rows": manifest_files["overrides/type_overrides.csv"]["n_rows"],
        },
    }
    manifest_path = out_dir / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nDEPLOY OK -- {len(contract['files'])} file(s) + scenarios/ ({len(manifest_scenarios)} files) "
          f"deployed; wrote {manifest_path}")
    return 0


def _n_rows(path: Path) -> int:
    if path.suffix == ".csv":
        import pandas as pd
        return len(pd.read_csv(path))
    import pyarrow.parquet as pq
    return pq.ParquetFile(path).metadata.num_rows


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:  # pragma: no cover
        pass
    sys.exit(main())

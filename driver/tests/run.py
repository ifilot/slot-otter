#!/usr/bin/env python3
"""Run host regression tests; optionally build and test actual DOS.

Examples:
  python3 driver/tests/run.py --coverage /tmp/otter-coverage
  python3 driver/tests/run.py --build --dosbox /path/to/test-dosbox --swap \
    --boot-image /path/to/dos5.img --boot-image /path/to/dos622.img
"""
import argparse
import os
import json
import re
import pathlib
import subprocess
import sys

TESTS = pathlib.Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage", type=pathlib.Path)
    parser.add_argument("--mutations", action="store_true")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--dosbox")
    parser.add_argument("--boot-image", type=pathlib.Path, action="append", default=[])
    parser.add_argument("--max-resident", type=int, default=17632)
    parser.add_argument("--swap", action="store_true")
    args = parser.parse_args()
    if bool(args.boot_image) != bool(args.dosbox) or (args.swap and not args.dosbox):
        parser.error("DOS integration needs both --dosbox and --boot-image")
    env = dict(os.environ)
    if args.coverage:
        args.coverage = args.coverage.resolve()
        args.coverage.mkdir(parents=True, exist_ok=True)
        # Clear previous counts so coverage always describes this run.
        for file in args.coverage.rglob("*.gcda"):
            file.unlink()
        env["OTTER_TEST_COVERAGE"] = str(args.coverage)
    subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(TESTS),
                    "-p", "test_*.py", "-v"], env=env, check=True)
    if args.coverage:
        # The same model is instrumented in protocol and write-transport libraries.
        # Merge their counters so the existing model floor measures their union.
        merged=args.coverage / "combined-model"
        subprocess.run(["gcov-tool","merge",str(args.coverage / "model"),
                        str(args.coverage / "write"),"-o",str(merged)],check=True)
        import shutil
        shutil.copyfile(args.coverage / "model/slot_model.gcno",merged / "slot_model.gcno")
        # Merge identical production writer graphs from filesystem, callback,
        # and transport tests; each exercises different error paths.
        rwfs = args.coverage / "combined-rwfs"
        subprocess.run(["gcov-tool", "merge", str(args.coverage / "rwfs"),
                        str(args.coverage / "rwredir"), "-o", str(rwfs)], check=True)
        shutil.copyfile(args.coverage / "rwfs/rwfs.gcno", rwfs / "rwfs.gcno")
        rwsd = args.coverage / "combined-rwsd"
        subprocess.run(["gcov-tool", "merge", str(args.coverage / "rwsd"),
                        str(rwfs), "-o", str(rwsd)], check=True)
        shutil.copyfile(args.coverage / "rwsd/sdrw.gcno", rwsd / "sdrw.gcno")
        reports = []
        metrics = {}
        for notes in sorted(args.coverage.rglob("*.gcno")):
            result = subprocess.run(["gcov", "-b", "-c", str(notes)], cwd=notes.parent,
                                    check=True, capture_output=True, text=True)
            reports.append(result.stdout)
            for match in re.finditer(r"File '([^']+)'\nLines executed:([0-9.]+)%[^\n]*\n"
                                     r"Branches executed:[^\n]*\nTaken at least once:([0-9.]+)%",
                                     result.stdout):
                key = notes.parent.name + "/" + pathlib.Path(match[1]).name
                metrics[key] = {"lines": float(match[2]), "branch_outcomes": float(match[3])}
        metrics["model/slot_model.c"]=metrics["combined-model/slot_model.c"]
        metrics["rwfs/RWFS.C"] = metrics["combined-rwfs/RWFS.C"]
        metrics["rwsd/SDRW.C"] = metrics["combined-rwsd/SDRW.C"]
        summary = "\n".join(reports)
        (args.coverage / "summary.txt").write_text(summary)
        (args.coverage / "coverage.json").write_text(json.dumps(metrics, indent=2) + "\n")
        print(summary, flush=True)
        for key, line_floor, branch_floor in [("fat32/FAT32.C", 95, 80),
                                               ("redirector/REDIR.C", 99, 90),
                                               ("model/slot_model.c", 95, 80),
                                               ("port/PORTBODY.H", 100, 100),
                                               ("write/WFS.C", 80, 65),
                                               ("write/WSD.C", 80, 65),
                                               ("write/WTEST.C", 85, 60),
                                               ("rwfs/RWFS.C", 90, 66),
                                               ("rwsd/SDRW.C", 99, 75),
                                               ("rwredir/RWOPS.C", 95, 72),
                                               ("rwredir/REDIR.C", 88, 63)]:
            metric = metrics[key]
            if metric["lines"] < line_floor or metric["branch_outcomes"] < branch_floor:
                raise RuntimeError(f"Coverage below regression floor: {key}: {metric}")
        print(f"Coverage: {args.coverage}", flush=True)
    if args.mutations:
        subprocess.run([sys.executable, str(TESTS / "mutations.py")], check=True)
        subprocess.run([sys.executable, str(TESTS.parent / "write/sensitivity.py")], check=True)
        for name in ("rw_mutations.py", "rw_fs_mutations.py", "rw_redirector_mutations.py"):
            subprocess.run([sys.executable, str(TESTS / name)], check=True)
    if args.build:
        subprocess.run(["bash", str(TESTS / "legacy-build.sh")], check=True)
    for boot in args.boot_image:
        command = [sys.executable, str(TESTS / "integration.py"),
                   "--dosbox", args.dosbox, "--boot-image", str(boot),
                   "--max-resident", str(args.max_resident)]
        if args.swap:
            command.append("--swap")
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()

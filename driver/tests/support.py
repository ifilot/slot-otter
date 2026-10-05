"""Build strict host libraries, optionally keeping GCC coverage artifacts."""
import os
import pathlib
import subprocess

ROOT = pathlib.Path(os.environ.get("OTTER_TEST_SOURCE_ROOT",
                                  pathlib.Path(__file__).resolve().parents[1]))


def library(work, name, sources, flags=()):
    coverage = os.environ.get("OTTER_TEST_COVERAGE")
    build = pathlib.Path(coverage) / name if coverage else work / name
    build.mkdir(parents=True, exist_ok=True)
    common = ["gcc", "-x", "c", "-std=c89", "-pedantic", "-Wall", "-Wextra",
              "-Werror", "-DHOST_TEST", "-fPIC", "-I", str(ROOT), *flags]
    if coverage:
        common += ["--coverage", "-O0"]
    objects = []
    for source in sources:
        source = ROOT / source
        obj = build / (source.stem.lower() + ".o")
        subprocess.run([*common, "-c", str(source), "-o", str(obj)], check=True)
        objects.append(str(obj))
    so = build / (name + ".so")
    subprocess.run(["gcc", "-shared", *( ["--coverage"] if coverage else []),
                    *objects, "-o", str(so)], check=True)
    return so

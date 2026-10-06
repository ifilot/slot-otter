"""Boot real DOS and exercise the resident driver using DOSBox-VirtIsa.

Supply your own bootable DOS floppy; only a temporary copy is modified.
Uses the emulator's ISA SD image, not its built-in DOS filesystem.
"""
import argparse
import hashlib
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import time
from fixture import create, BIG, TEXT

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boot-image", type=pathlib.Path, required=True)
    parser.add_argument("--dosbox", required=True, help="DOSBox-VirtIsa executable")
    parser.add_argument("--toolchain", type=pathlib.Path, default=ROOT.parent / "buildenv")
    parser.add_argument("--compiler-dosbox", default="dosbox")
    parser.add_argument("--driver",type=pathlib.Path,default=ROOT/'OTTERFS.EXE',
                        help="Executable to install in read-only mode as OTTERFS.EXE")
    parser.add_argument("--timeout", type=float, default=45)
    parser.add_argument("--swap", action="store_true", help="Exercise empty slot and swapping; requires OTTER_MODEL_TEST adapter")
    parser.add_argument("--max-resident", type=int, default=17632, help="Resident DOS allocation ceiling in bytes")
    args = parser.parse_args()
    work = pathlib.Path(tempfile.mkdtemp(prefix="otterfs-integration-"))
    print(f"Test artifacts: {work}", flush=True)
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    # Compile probes independently, with CRLF and 8.3 source names.
    probes = ["PROBE", "CLIPROBE"] + (["SWAP", "SDPROBE"] if args.swap else [])
    if args.swap:
        for filename in ("OTTER.H", "SD.C", "SDCMDS.ASM"):
            content = (ROOT / filename).read_bytes().replace(b"\r\n", b"\n")
            (work / filename).write_bytes(content.replace(b"\n", b"\r\n"))
    for probe in probes:
        source = (ROOT / f"tests/{probe}.C").read_bytes().replace(b"\r\n", b"\n")
        (work / f"{probe}.C").write_bytes(source.replace(b"\n", b"\r\n"))
        commands = ["tasm /mx SDCMDS.ASM > ASM.TXT",
                    "tcc -ms -eSDPROBE.EXE SDPROBE.C SD.C SDCMDS.OBJ > BUILD.TXT"] if probe == "SDPROBE" else [f"tcc -ms -e{probe}.EXE {probe}.C > BUILD.TXT"]
        with (work / "compiler.log").open("ab") as log:
            subprocess.run([args.compiler_dosbox, "-noconsole", "-exit",
                            "-c", f'mount c "{args.toolchain.resolve()}"',
                            "-c", f'mount d "{work}"', "-c", r"set PATH=C:\TC;C:\TASM",
                            "-c", "d:", *sum((["-c", command] for command in commands), []),
                            "-c", "exit"], env=env, stdout=log, stderr=log, check=True, timeout=30)
        print((work / "BUILD.TXT").read_text(), flush=True)
        if not (work / f"{probe}.EXE").exists():
            raise RuntimeError("DOS probe compilation failed")
    image = work / "card.img"
    create(image)
    before = hashlib.sha256(image.read_bytes()).digest()
    if args.swap:
        second = work / "second.img"
        layout = create(second, spc=8)
        with second.open("r+b") as f:
            f.seek((layout["data"] + 2 * layout["spc"]) * 512)
            f.write(b"Z")
        second_hash = hashlib.sha256(second.read_bytes()).digest()
        env.update(OTTER_TEST_EMPTY="1", OTTER_TEST_IMAGE2=str(second))
    boot = work / "boot.img"
    shutil.copyfile(args.boot_image, boot)
    # Installation floppies may be almost full. Keep the boot system files,
    # but clear other root files on our private copy to make room for COPY.
    keep = {"IO.SYS", "MSDOS.SYS", "COMMAND.COM", "IBMBIO.COM", "IBMDOS.COM",
            "DRBIOS.SYS", "DRDOS.SYS", "DRVSPACE.BIN", "DBLSPACE.BIN"}
    listing = subprocess.check_output(["mdir", "-b", "-i", str(boot), "::"]).decode()
    for name in listing.splitlines():
        if name.endswith("/") or pathlib.PurePosixPath(name).name.upper() in keep:
            continue
        subprocess.run(["mdel", "-i", str(boot), name], check=True)
    (work / "CONFIG.SYS").write_bytes(b"LASTDRIVE=S\r\nFILES=40\r\nBUFFERS=10\r\n")
    (work / "AUTOEXEC.BAT").write_bytes(
        b"@echo off\r\n"
        b"otterfs /status > missing.txt\r\n"
        b"otterfs /drive:s /port:333 > args.txt\r\n"
        b"cliprobe > install.txt\r\n"
        b"otterfs /drive:s > repeat.txt\r\n" +
        (b"swap > swap.txt\r\n" if args.swap else b"otterfs /mount > mount.txt\r\n") +
        b"otterfs /status > status.txt\r\n"
        b"dir s:\\ > dir.txt\r\n"
        b"probe > result.txt\r\n"
        b"s:\\hello.com > exec.txt\r\n"
        b"copy /b s:\\readme.txt a:\\small.txt > smalllog.txt\r\n"
        b"copy /b s:\\big.bin a:\\copy.bin > copylog.txt\r\n"
        + (b"otterfs /unmount > sdprep.txt\r\nsdprobe > sdresult.txt\r\notterfs /mount > sdrestore.txt\r\n" if args.swap else b"") +
        b"echo OTTER-DONE > done.txt\r\n"
        b"dir a:\\ > flush.txt\r\n")
    subprocess.run(["mcopy","-o","-i",str(boot),str(args.driver),"::OTTERFS.EXE"],check=True)
    for source in (work / "PROBE.EXE", work / "CLIPROBE.EXE", work / "CONFIG.SYS", work / "AUTOEXEC.BAT"):
        subprocess.run(["mcopy", "-o", "-i", str(boot), str(source), "::" + source.name], check=True)
    if args.swap:
        for name in ("SWAP", "SDPROBE"):
            subprocess.run(["mcopy", "-o", "-i", str(boot), str(work / f"{name}.EXE"), f"::{name}.EXE"], check=True)
    # Clear an inherited completion marker if the supplied image was used before.
    subprocess.run(["mdel", "-i", str(boot), "::DONE.TXT"], stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
    config = work / "dosbox.conf"
    config.write_text(f"[sdl]\nfullscreen=false\n[dosbox]\nmemsize=1\nisa_sd_image={image}\n"
                      "[cpu]\ncore=normal\ncycles=fixed 15000\n[midi]\nmpu401=none\n")
    with (work / "emulator.log").open("wb") as log:
        proc = subprocess.Popen([args.dosbox, "-conf", str(config), "-c", f'boot "{boot}"'],
                                env=env, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + args.timeout
            while time.monotonic() < deadline:
                result = subprocess.run(["mtype", "-i", str(boot), "::DONE.TXT"],
                                        capture_output=True)
                if b"OTTER-DONE" in result.stdout:
                    break
                if proc.poll() is not None:
                    raise RuntimeError("Emulator exited before the test finished")
                time.sleep(0.3)
            else:
                raise RuntimeError("DOS test timed out; inspect the retained emulator log")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
    results = {}
    for name in ("INSTALL.TXT", "REPEAT.TXT", "DIR.TXT", "RESULT.TXT", "EXEC.TXT", "COPYLOG.TXT", "STATUS.TXT", "MISSING.TXT", "ARGS.TXT"):
        results[name] = subprocess.check_output(["mtype", "-i", str(boot), "::" + name])
        (work / name).write_bytes(results[name])
        print(results[name].decode("cp437"), flush=True)
    if args.swap:
        result = subprocess.check_output(["mtype", "-i", str(boot), "::SWAP.TXT"])
        (work / "SWAP.TXT").write_bytes(result)
        print(result.decode("cp437"), flush=True)
        assert b"SWAP RESULT: 0 failures" in result
        sd_result = subprocess.check_output(["mtype", "-i", str(boot), "::SDRESULT.TXT"])
        (work / "SDRESULT.TXT").write_bytes(sd_result)
        print(sd_result.decode("cp437"), flush=True)
        assert b"SD RESULT: 0 failures" in sd_result
        assert hashlib.sha256(second.read_bytes()).digest() == second_hash
    assert b"CLI RESULT: 0 failures" in results["INSTALL.TXT"]
    assert b"RESULT: 0 failures" in results["RESULT.TXT"]
    reported = re.search(rb"resident (\d+) bytes", results["INSTALL.TXT"])
    allocated = re.search(rb"RESIDENT MCB: (\d+) bytes", results["RESULT.TXT"])
    assert reported and allocated and reported[1] == allocated[1], "DOS MCB differs from reported footprint"
    assert int(allocated[1]) <= args.max_resident, "Resident allocation exceeded memory regression ceiling"
    assert b"not resident" in results["MISSING.TXT"]
    assert b"Usage:" in results["ARGS.TXT"]
    (work / "memory.txt").write_text(f"Resident DOS allocation: {int(allocated[1])} bytes\n")
    assert b"already resident" in results["REPEAT.TXT"]
    assert b"S: mounted, 0 open files, port 330" in results["STATUS.TXT"]
    assert b"EXEC OK" in results["EXEC.TXT"]
    for name, content in [("COPY.BIN", BIG), ("SMALL.TXT", TEXT)]:
        copied = subprocess.check_output(["mtype", "-i", str(boot), "::" + name])
        assert copied == content, f"DOS COPY mismatch: {name}"
    assert hashlib.sha256(image.read_bytes()).digest() == before, "SD image changed"
    print("PASS: real DOS callbacks, COPY/EXEC, duplicate install, and unchanged SD image")


if __name__ == "__main__":
    main()

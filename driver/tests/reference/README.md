# Host regression references

These historical transport/diagnostic/filesystem sources preserve the hard-won
CRC-rejection, recovery and card-behavior regressions. WSD/WFS/WTEST/HOSTIO are
compiled only into host test libraries by test_write.py. SD.C/SDCMDS.ASM are
exercised by the independent native SDPROBE. Neither set is a public driver or
hardware utility, and no build/package target produces an old executable.
The only public DOS programs are OTTERSD.EXE and HWRT.EXE.

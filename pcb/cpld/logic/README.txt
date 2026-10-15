Slot-otter ATF1504AS draft -- 2026-10-15

Source: slototter.pld. Target: 5 V ATF1504AS, 44-pin PLCC, with JTAG ON.
Pin assignments match U1 in ../cpld.kicad_sch and ../cpld.kicad_pcb.
Keep the external 74HCT688, 74LVC125, regulator and 16 MHz oscillator.
No schematic, PCB, driver or installed WinCUPL files are changed by the build.
This is a functional hardware draft, not a bench-validated release image.

BUILD ON WINDOWS

From this directory, run:
    build.cmd

The default compiler installation is C:\Wincupl. To override it:
    set "SLOTOTTER_CUPL_ROOT=C:\your\WinCUPL"
    build.cmd

For the functional simulation as well, with Python 3 installed:
    build.cmd test

The test command prefers the Windows 'py -3' launcher, falling back to
'python'. Alternatively generate vectors from WSL with:
    python3 generate_vectors.py
Then use WinCUPL's simulation option on build\slototter.pld.

The script copies the source into build\ and runs the installed compiler
with explicit device-library selection. Generated files stay in build\:
    slototter.jed  Programming image
    slototter.fit  Fitter utilization, placement and fitted equations
    slototter.pin  Assigned pin/node list
    slototter.doc  Compiler equations
    slototter.si   Generated test stimulus (test build)
    slototter.so   Simulation results (test build)
    compile.log   Compiler/simulator output

To use the GUI, open slototter.pld, select device-dependent compilation,
and enable JEDEC/absolute/documentation outputs. Retain the device declared
in the source: f1504ispplcc44. Source and command files use CRLF endings.
Do not program hardware from a failed build or an old JEDEC image.

PINOUT (PLCC44)

43 oscillator; 44 /PORTSEL; 16 /IOR; 17 /IOW; 18 A0; 19 A1.
DB0..DB7: 29,31,33,34,36,37,39,40.
24 MOSI; 25 MISO; 26 MISO weak-pull control via R1; 27 /CS; 28 SCK.
JTAG: 7 TDI, 13 TMS, 32 TCK, 38 TDO. Supply pins remain as drawn.
/PORTSEL comes from the external comparator, including AEN qualification.

PORT BEHAVIOUR

OUT base+0: capture DB, then transmit a byte and receive a byte.
OUT base+1: clock another byte without reloading TX; OUT data is ignored.
 IN base+0: read the completed RX byte without clocking SPI.
 IN base+1: read the completed RX byte, then clock another byte AFTER /IOR
            rises. Holding /IOR low must not start or repeat a transfer.
OUT base+2: release /CS (high).
OUT base+3: assert /CS (low).
 IN base+2: set the MISO weak-pull control low; DB remains high impedance.
 IN base+3: set the MISO weak-pull control high; DB remains high impedance.

The transmit shift register fills with ones, matching the original 74HC165
with its serial input tied high. Clock-only commands after a completed
transfer send FF, rather than retransmitting the last loaded byte.

The RX holding register updates on the eighth falling SCK edge. The data
bus drives only during selected reads of offsets 0/1, with /IOW inactive.
It is high impedance for other addresses, writes and control-port reads.
Reads during an unfinished earlier burst are not guaranteed to return a
complete new byte. The existing driver's repeated base reads allow settling.

CLOCKING AND LIMITS

SPI mode 0, MSB first, nominal 8 MHz SCK from a 16 MHz oscillator. MOSI is
prepared before the first rising SCK, changes on falling SCK, and MISO is
sampled on rising SCK. Eight rising and eight falling edges form a burst;
SCK idles low. No register is clocked by the generated SPI clock.

ISA writes capture on rising /IOW; read side effects capture on rising
/IOR. Those raw strobes use local product-term register clocks. Address,
/PORTSEL and write data must meet the fitted setup/hold requirements at
strobe release. Only request toggles cross into the oscillator domain,
through two flip-flops plus history. The captured write byte and mode must
remain stable until the request has been consumed. Do not overlap requests.

A transfer begins 2-3 oscillator periods (125-187.5 ns) after strobe release
and finishes 16 periods (1 us) later. Allow at least 1.5 us from strobe
release before requesting another transfer or relying on the new RX byte.
There is no queue, busy status register or connected ISA wait-state output.
Events consumed while the engine is busy are discarded. Multiple events
before synchronization can also cancel. This does not reproduce the old
discrete circuit's behaviour for overlapping transfers.

This extra synchronization delay and trailing-edge launch are deliberate
changes from the discrete timing. Existing DOS software may already provide
enough delay, but compatibility must be measured on the target PCs. Do not
assume the existing settling reads guarantee it on every ISA implementation.

Power-up reset initializes internal registers to zero: /CS is deasserted,
SCK is low, the weak pull is low and RX reads zero. MOSI initially reads low;
software should load FF before sending initialization clock-only bursts.
There is no connected ISA RESET input on the present board. The device's
power-up reset and oscillator start-up behaviour need hardware verification.

VALIDATION PERFORMED

Installed CUPL 5.0 toolchain and ATF1504AS fitter 1.8.7.8:
    Device-dependent compilation and fitting passed, JTAG ON.
    52/64 logic cells; 48/64 flip-flops; 12/64 foldback terms.
    The report's combined nodes-plus-foldbacks count is 64/64, so the fit
    does not imply substantial room for additional functionality.
    31,879 functional vectors passed, comprising 258 byte transfers.
    All 256 transmitted values and all 256 received values were exercised.
    Vectors check MSB order, eight-clock bursts, idle polarity, captured
    write data, FF serial fill, clock-only requests, repeated side-effect-
    free reads, a long read+clock cycle, CS/pull controls, unselected
    accesses, and high-impedance DB states between reads.
    An intentionally incorrect SCK expectation was rejected by the simulator.

The integrated simulator emits 0033sa notices about undefined pin numbers
for internal nodes when preparing JEDEC test vectors. These are not vector
mismatches; check the final compiler/simulator exit status as well. The
simulation build appends test vectors to the JEDEC file. A plain build
regenerates the programming image without those vectors.

These are compiler-equation functional simulations, not post-route timing
signoff or metastability analysis. Before using an SD card, check the fitted
pinout and equations, setup/hold on ISA strobes, synchronizer placement,
oscillator-period timing, pad drive strength, DB release and round-trip SPI
timing through the external LVC125 and series resistors for your exact
ATF1504AS speed grade. No bench or DOS compatibility test has been run.

Suggested first bench checks:
  1. Without an SD card, verify idle /CS high, SCK low and DB high impedance.
  2. Transmit A5 and 96 and verify MOSI order and exactly eight SCK pulses.
  3. With MISO driven at a valid logic level, verify RX byte assembly.
  4. Verify repeated IN base+0 never clocks SPI and IN base+1 starts only
     after /IOR release. Check /CS and pull control separately.
  5. Measure time from /IOW release to last SCK edge and the driver's first
     useful RX read on both slow and fast target PCs.
  6. Check /CS-low initialization and normal card initialization, then run
     read-only driver tests before enabling writes.

References:
  Microchip ATF1504AS(L) datasheet:
  https://ww1.microchip.com/downloads/en/DeviceDoc/ATF1504AS(L)-5V-64-Macrocell-CPLD-Data-Sheet-20006580A.pdf
  Microchip WinCUPL user guide:
  https://www.microchip.com/content/dam/mchp/documents/OTH/ProductDocuments/UserGuides/doc0737.pdf

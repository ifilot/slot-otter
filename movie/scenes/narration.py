"""Voice-over script.

For every scene: a list of lines (t, subtitle, spoken). `t` is the scene
time (of the silent cut) at which the line starts; the voice-over cut slows
the scene clock where a spoken line needs more room (see otter/voiceover.py).
`subtitle` is what is shown on screen (written form, as in the captions);
`spoken` is what the voice says, with numbers and part names spelled out
for the speech synthesiser.

Keep the tone calm and plain: one idea per line, short sentences.
"""

NARRATION = {
    's01_title': [
        (1.6, 'Slot-otter Classic.',
         'Slot-otter Classic.'),
        (6.0, 'An 8-bit ISA card that turns an SD card into an ordinary DOS drive.',
         'An eight-bit I-S-A card that turns an S-D card into an ordinary DOS drive.'),
    ],
    's02_xray': [
        (3.2, 'No microcontroller, no firmware: fourteen 74-series chips, an oscillator and a regulator.',
         'There is no microcontroller, and no firmware. Just fourteen seventy-four series logic chips, an oscillator, and a regulator.'),
    ],
    's03_edge': [
        (1.0, 'The CPU executes one instruction: write the byte 51h to I/O port 330h.',
         'Let us follow one instruction. The CPU writes the byte fifty-one hex to I/O port three-thirty hex.'),
        (6.0, 'For a moment the bus carries an address and a byte…',
         'For a moment, the bus carries an address, and a byte.'),
        (10.0, '51h is not random: it starts the SD command "read one block".',
         'Fifty-one hex is not a random choice. It is the first byte of the S-D command: read one block.'),
        (13.8, '…and a "write" strobe, /IOW, on the back of the card.',
         'And on the back of the card, a write strobe: I-O-W.'),
        (17.8, 'A slash means "active low": /IOW acts when its wire is at 0 V.',
         'The slash means active low. I-O-W does its job when its wire is at zero volts.'),
        (21.8, 'AEN low means the CPU, not DMA, is driving the bus.',
         'A-E-N is low too. That means the CPU, not D-M-A, is driving the bus.'),
    ],
    's04_comparator': [
        (0.8, 'Address lines A9 to A2 run to a 74HCT688, an 8-bit equality comparator.',
         'Address lines A-nine down to A-two run to a seventy-four H-C-T six eighty-eight: an eight-bit equality comparator.'),
        (5.5, "The DIP switch sets the card's address: ON means 1.",
         "The DIP switch holds the card's address. A switch that is on, means a one."),
        (10.8, 'All bits match and AEN is low: /PORTSEL goes low.',
         'All bits match, and A-E-N is low. So port-select goes low.'),
        (13.8, 'Any other address leaves /PORTSEL high, and the card ignores it.',
         'Any other address leaves port-select high, and the card simply ignores it.'),
        (17.8, "A1 and A0 aren't compared: the card owns four ports, 330h to 333h.",
         'A-one and A-zero are not compared. So the card owns four ports: three-thirty to three-thirty-three hex.'),
    ],
    's05_registers': [
        (1.0, 'Both signals are active low, so an OR gate means "this card AND write".',
         'Both signals are active low. So here, an OR gate really means: this card, and write.'),
        (7.0, 'A1 and A0 select one of four actions. Reads and writes each have their own decoder.',
         'A-one and A-zero then select one of four actions. Reads and writes each have their own decoder.'),
        (13.0, 'OUT 330h: load a byte and send it.',
         'Writing to three-thirty means: load a byte, and send it.'),
        (17.0, 'A NAND latch remembers whether the SD card is selected.',
         'And a small NAND latch remembers whether the S-D card is selected.'),
    ],
    's06_select': [
        (0.4, 'Earlier, the driver selected the card by reading port 333h.',
         'Earlier, the driver selected the card by reading port three-thirty-three.'),
        (4.4, 'The read is just a trigger: the latch now holds /CS low.',
         'The read is only a trigger. The latch now holds chip-select low.'),
    ],
    's07_load': [
        (1.0, 'A 74HCT245 opens the gate to the inside of the card. Its direction depends on read or write.',
         'Back to our byte. A seventy-four H-C-T two forty-five opens the gate to the inside of the card. Its direction depends on whether the CPU reads or writes.'),
        (9.0, 'While /IOW is low, the 165 copies all eight bits at once.',
         'While I-O-W is low, the one-sixty-five shift register copies all eight bits at once.'),
        (13.4, 'Bit 7 is already on MOSI, waiting for the first clock.',
         'Bit seven is already waiting on the Mosi line, for the first clock.'),
        (17.8, 'Its serial input is tied to 5 V: once the byte is out, MOSI rests high.',
         'Its serial input is tied to five volts. So once the byte has gone, Mosi rests high.'),
    ],
    's08_edge_detect': [
        (0.8, 'Clocking must wait until the CPU releases /IOW. Only then is the byte final.',
         'The clock must wait until the CPU releases I-O-W. Only then is the byte final.'),
        (6.0, 'Two flip-flops follow the strobe one to two ticks late. "Released" AND "not yet seen" gives a short pulse.',
         'Two flip-flops follow the strobe, one or two clock ticks late. Released, and not yet seen, gives a short pulse.'),
        (12.8, 'The pulse starts the moment the strobe is released and lasts about 100 ns. It becomes /CLKSTART.',
         'The pulse starts the moment the strobe is released, and lasts about a hundred nanoseconds. It becomes clock-start.'),
    ],
    's09_counter': [
        (0.6, '/CLKSTART sets a latch, which releases a 4-bit counter.',
         'Clock-start sets a latch, which releases a four-bit counter.'),
        (4.2, "The counter's lowest bit flips on every 16 MHz tick: an 8 MHz clock, called SCK.",
         "The counter's lowest bit flips on every tick of the sixteen megahertz oscillator. That makes an eight megahertz clock, called S-C-K."),
        (11.6, 'At 15, "terminal count" resets the latch; the counter clears and stops.',
         'At fifteen, the terminal count output resets the latch. The counter clears, and stops.'),
        (16.0, 'Eight clock pulses, then silence. One byte takes one microsecond.',
         'Eight clock pulses, then silence. One byte takes one microsecond.'),
        (20.4, 'The last NAND gate inverts the clock: the 165 shifts on the falling edge.',
         'The last NAND gate inverts the clock, because the one-sixty-five shifts on the falling edge.'),
    ],
    's10_spi_wires': [
        (0.6, 'The SD card runs on 3.3 V, from a regulator; a 74LVC125 drives its pins.',
         'The S-D card runs on three point three volts, from a regulator. A seventy-four L-V-C one twenty-five drives its pins.'),
        (6.2, 'SPI uses four wires: a clock (SCK), data out (MOSI), data in (MISO) and select (/CS).',
         'The card speaks S-P-I, over four wires: a clock, data out called Mosi, data in called Miso, and chip-select.'),
    ],
    's11_shift': [
        (1.6, 'On each rising edge the SD card reads a bit from MOSI, and the 595 a bit from MISO.',
         'Now, in slow motion. On each rising edge, the S-D card reads one bit from Mosi, and the five-ninety-five reads one bit from Miso.'),
        (8.2, 'On each falling edge the 165 moves the next bit into place. Most significant bit first.',
         'On each falling edge, the one-sixty-five moves the next bit into place. The most significant bit goes first.'),
        (14.0, 'While a command goes out, the card has nothing to say: it answers with ones.',
         'While a command goes out, the card has nothing to say. It answers with ones.'),
        (23.6, 'Sending and receiving are the same eight clocks. SPI simply swaps two bytes.',
         'Sending and receiving happen in the same eight clocks. S-P-I simply swaps two bytes.'),
    ],
    's12_answer': [
        (0.4, 'Next comes the sector number, 2048, where a partition usually starts, then a checksum.',
         'Next comes the sector number: twenty forty-eight, where a partition usually starts. Then a checksum.'),
        (5.8, 'To listen, the driver simply sends FFh.',
         'To listen, the driver simply sends F-F.'),
        (9.0, 'The card answers 00h (OK), then FEh (data starts now).',
         'The card answers zero zero, meaning OK. Then F-E: the data starts now.'),
        (12.2, "Out comes the sector's first byte, EBh, the start of a FAT boot sector.",
         "Out comes the sector's first byte: E-B hex, the start of a FAT boot sector."),
        (22.0, "The byte now waits in the 595's output latch.",
         "The byte now waits in the five-ninety-five's output latch."),
    ],
    's13_readback': [
        (0.5, 'The CPU reads port 330h. The read decoder pulls /SER_RD low.',
         'The CPU reads port three-thirty. The read decoder pulls serial-read low.'),
        (5.2, 'The 595 drives the internal bus, and the 245 turns around to face the CPU.',
         'The five-ninety-five drives the internal bus, and the two forty-five turns around to face the CPU.'),
        (12.0, 'EBh arrives in register AL.',
         'E-B hex arrives in register A-L.'),
        (16.2, 'OTTERSD repeats this for every byte: send FFh, then read the answer.',
         'The Otter-S-D driver repeats this for every byte. Send F-F, then read the answer.'),
    ],
    's14_sector': [
        (0.2, 'A complete read: six bytes out, a short wait, a start token, 512 data bytes and a checksum.',
         'A complete read is six bytes out, a short wait, a start token, five hundred and twelve data bytes, and a checksum.'),
        (14.6, 'Every one of them takes the path you have just seen.',
         'Every one of them takes the path you have just seen.'),
    ],
    's15_outro': [
        (3.6, 'Slot-otter: open hardware, eight clocks at a time.',
         'Slot-otter. Open hardware, eight clocks at a time.'),
    ],
}


# --------------------------------------------------------------------------
# Subtitles for the voice-over cut: the spoken words, in written form.
# --------------------------------------------------------------------------
import re as _re

_WRITTEN = [
    ('The Otter-S-D driver', 'The OTTERSD driver'), ('Otter-S-D', 'OTTERSD'), ('Fifty-one hex', '51h'),
    ('seventy-four H-C-T six eighty-eight', '74HCT688'), ('seventy-four H-C-T two forty-five', '74HCT245'),
    ('seventy-four L-V-C one twenty-five', '74LVC125'), ('seventy-four series', '74-series'),
    ('three-thirty-three hex', '333h'), ('three-thirty-three', '333h'),
    ('three-thirty to three-thirty-three hex', '330h to 333h'),
    ('three-thirty hex', '330h'), ('three-thirty', '330h'), ('fifty-one hex', '51h'),
    ('five hundred and twelve', '512'), ('twenty forty-eight', '2048'),
    ('sixteen megahertz', '16 MHz'), ('eight megahertz', '8 MHz'), ('three point three volts', '3.3 V'),
    ('five volts', '5 V'), ('zero volts', '0 V'), ('a hundred nanoseconds', '100 ns'),
    ('one microsecond', '1 µs'),
    ('eight-bit', '8-bit'), ('four-bit', '4-bit'), ('one-sixty-five', '165'), ('five-ninety-five', '595'),
    ('two forty-five', '245'), ('E-B hex', 'EBh'), ('F-F', 'FFh'), ('F-E', 'FEh'), ('zero zero', '00h'),
    ('I-O-W', '/IOW'), ('A-E-N', 'AEN'), ('I-S-A', 'ISA'), ('S-D', 'SD'), ('S-P-I', 'SPI'), ('S-C-K', 'SCK'),
    ('D-M-A', 'DMA'), ('A-L', 'AL'), ('A-nine', 'A9'), ('A-two', 'A2'), ('A-one', 'A1'), ('A-zero', 'A0'),
    ('Otter-S-D', 'OTTERSD'), ('port-select', '/PORTSEL'), ('Port-select', '/PORTSEL'),
    ('chip-select', '/CS'), ('clock-start', '/CLKSTART'), ('Clock-start', '/CLKSTART'),
    ('serial-read', '/SER_RD'), ('Mosi', 'MOSI'), ('Miso', 'MISO'),
]


def written(spoken):
    s = spoken
    for a, b in _WRITTEN:
        s = s.replace(a, b)
    s = _re.sub(r'\bport (330h|333h)\b', r'port \1', s)
    return s


def subtitle(scene, i):
    """Subtitle for line i of a scene in the voice-over cut (None = no subtitle)."""
    t, sub, spoken = NARRATION[scene][i]
    if scene == 's01_title' and i == 0:
        return None                      # the title card already says it
    return written(spoken)

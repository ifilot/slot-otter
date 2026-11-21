"""Narration: the leading text of the movie (see STORY.md).

For every scene: a list of lines (t, written, spoken).
- `t` is the scene time at which the line starts. The scene clock slows down
  where a spoken line needs more room (otter/voiceover.py), so `t` marks the
  visual moment the line belongs to.
- `written` is the subtitle (burned in, and in the SRT/VTT files).
- `spoken` is what the voice says: numbers and part names spelled out for the
  speech synthesiser ("the 595" -> "the five ninety-five", "MOSI" -> "Mosi").
  Keep its punctuation the same as the written form: every extra full stop is
  an extra pause.

Tone: calm and plain, but told as one story. Each line follows on from the one
before, sentences vary in length, and each scene opens by linking back to where
the last one left off.
"""

NARRATION = {
    # -- Act 1: what the card does ---------------------------------------------
    's01_title': [
        (1.6, None,
         'Slot-otter Classic.'),
        (6.0, 'It is an 8-bit ISA card that lets an old PC, even one of the very first 8088 machines, '
              'use an SD card as an ordinary DOS drive.',
         'It is an eight-bit I-S-A card that lets an old PC, even one of the very first eighty eighty-eight '
         'machines, use an S-D card as an ordinary DOS drive.'),
        (16.0, 'To the PC, the card is simply a set of I/O ports. An 8088 or 8086 talks to its hardware '
               'through such ports: with one instruction it writes a byte to a port, and with another it '
               'reads a byte back.',
         'To the PC, the card is simply a set of I-O ports. An eighty eighty-eight or eighty eighty-six talks to '
         'its hardware through such ports: with one instruction it writes a byte to a port, and with another '
         'it reads a byte back.'),
        (30.5, 'The SD card knows nothing about ports. In the simple mode used here, it speaks SPI: data '
               'travels one bit at a time, in step with a clock signal.',
         'The S-D card knows nothing about ports. In the simple mode used here, it speaks S-P-I: data '
         'travels one bit at a time, in step with a clock signal.'),
        (42.0, 'Slot-otter sits in between. Every byte the PC writes becomes a stream of bits for the SD card, '
               'and the bits that come back are gathered into a byte the PC can read.',
         'Slot-otter sits in between. Every byte the PC writes becomes a stream of bits for the S-D card, '
         'and the bits that come back are gathered into a byte the PC can read.'),
    ],
    's02_xray': [
        (3.0, 'What makes this card unusual is how it does that. There is no microcontroller on it and no '
              'firmware, just fourteen 74-series logic chips, an oscillator and a voltage regulator.',
         'What makes this card unusual is how it does that. There is no microcontroller on it and no '
         'firmware, just fourteen seventy-four series logic chips, an oscillator and a voltage regulator.'),
        (14.0, 'So how can a handful of logic chips talk to an SD card? To find out, we will follow a single '
               'byte from the PC to the SD card, and another one on its way back, and meet each of these '
               'chips along the way.',
         'So how can a handful of logic chips talk to an S-D card? To find out, we will follow a single '
         'byte from the PC to the S-D card, and another one on its way back, and meet each of these '
         'chips along the way.'),
    ],
    's03_worlds': [
        (0.4, "But first, let's take a closer look at both sides, starting with the PC.",
         "But first, let's take a closer look at both sides, starting with the PC."),
        (4.4, 'On the ISA bus, the PC puts all eight bits of a byte on eight wires at once, together with an '
              'address that says where the byte should go.',
         'On the I-S-A bus, the PC puts all eight bits of a byte on eight wires at once, together with an '
         'address that says where the byte should go.'),
        (15.2, 'The SD card, by contrast, takes in one bit at a time, on a single wire called MOSI.',
         'The S-D card, by contrast, takes in one bit at a time, on a single wire called Mosi.'),
        (21.8, 'A second wire, the clock SCK, tells the card when to read each bit, so eight clock pulses '
               'carry one byte.',
         'A second wire, the clock S-C-K, tells the card when to read each bit, so eight clock pulses '
         'carry one byte.'),
        (28.8, "The card's answers come back the same way, bit by bit, on a third wire called MISO.",
         "The card's answers come back the same way, bit by bit, on a third wire called Miso."),
        (34.4, 'And a fourth wire, chip select, has to be held low, at zero volts, for the card to listen at all.',
         'And a fourth wire, chip select, has to be held low, at zero volts, for the card to listen at all.'),
        (40.4, 'That is the translation this card performs: bytes into bits, and bits back into bytes.',
         'That is the translation this card performs: bytes into bits, and bits back into bytes.'),
                (45.8, 'On the board, bytes arrive at the card edge, and leave as bits through the SD socket.',
         'On the board, bytes arrive at the card edge, and leave as bits through the S-D socket.'),
    ],
    # -- Act 2: is this for me? ----------------------------------------------
    's04_edge': [
        (1.0, "Now let's follow our byte. The CPU writes 51h to I/O port 330h.",
         "Now let's follow our byte. The CPU writes fifty-one hex to I-O port three-thirty hex."),
        (6.4, "That value is no accident: 51h is the first byte of the SD card's command to read one block.",
         "That value is no accident: fifty-one hex is the first byte of the S-D card's command to read "
         "one block."),
        (13.8, 'For a brief moment, the bus carries both the address and the byte.',
         'For a brief moment, the bus carries both the address and the byte.'),
        (17.2, 'At the same time, the CPU pulls a wire called /IOW low. The slash means the wire is active when '
               'it is low, and here it tells the cards on the bus that this is a write.',
         'At the same time, the CPU pulls a wire called I-O-W low. The slash means the wire is active when '
         'it is low, and here it tells the cards on the bus that this is a write.'),
    ],
    's05_comparator': [
        (0.6, 'Every card in the PC sees this address, so our card first has to ask: is this meant for me?',
         'Every card in the PC sees this address, so our card first has to ask: is this meant for me?'),
        (6.6, 'I/O addresses use ten lines. Eight of them, A9 down to A2, run to a 74HCT688, a chip that '
              'compares two 8-bit numbers.',
         'I-O addresses use ten lines. Eight of them, A-nine down to A-two, run to a seventy-four H-C-T '
         'six eighty-eight, a chip that compares two eight-bit numbers.'),
        (16.8, 'Its second number comes from a DIP switch, where you set the address the card should answer to.',
         'Its second number comes from a dip switch, where you set the address the card should answer to.'),
        (22.0, 'When all eight bits match, the card knows it is being addressed.',
         'When all eight bits match, the card knows it is being addressed.'),
                (25.4, 'Any other address fails, and the card ignores it.',
         'Any other address fails, and the card ignores it.'),
                (28.8, 'A1 and A0 are not compared at all, so the card answers to four ports in a row: 330h to 333h.',
         'A-one and A-zero are not compared at all, so the card answers to four ports in a row: '
         'three-thirty to three-thirty-three hex.'),
    ],
    's06_registers': [
        (1.0, 'Next, the card works out what the CPU wants: a read or a write, and on which of its four ports.',
         'Next, the card works out what the CPU wants: a read or a write, and on which of its four ports.'),
        (6.4, 'A decoder combines A1 and A0 with the read and write signals, and turns them into a single action.',
         'A decoder combines A-one and A-zero with the read and write signals, and turns them into a single '
         'action.'),
        (12.6, 'Only two of these actions matter for our story. Writing to 330h sends a byte to the SD card,',
         'Only two of these actions matter for our story. Writing to three-thirty sends a byte to the S-D card,'),
        (18.8, "and reading from the same port fetches the card's reply.",
         "and reading from the same port fetches the card's reply."),
                (22.2, 'The other ports handle housekeeping.',
         'The other ports handle housekeeping.'),
    ],
    # -- Act 3: from byte to bits --------------------------------------------
    's07_load': [
        (1.0, "First, the byte has to get onto the card. It enters through a 74HCT245, the card's gate to the "
              "bus, which lets data in when the CPU writes, and out when it reads.",
         "First, the byte has to get onto the card. It enters through a seventy-four H-C-T two forty-five, "
         "the card's gate to the bus, which lets data in when the CPU writes, and out when it reads."),
        (12.4, 'Behind the gate, the actual translation is done by two shift registers.',
         'Behind the gate, the actual translation is done by two shift registers.'),
        (16.6, 'The first, a 74HC165, has eight cells that load a whole byte at once and then hand it out one '
               'bit at a time. While /IOW is still low, our byte is copied in.',
         'The first, a seventy-four H-C one sixty-five, has eight cells that load a whole byte at once and '
         'then hand it out one bit at a time. While I-O-W is still low, our byte is copied in.'),
        (29.2, 'Every clock pulse then pushes the next bit onto MOSI. Bit 7 goes first, and it is already '
               'waiting there.',
         'Every clock pulse then pushes the next bit onto Mosi. Bit seven goes first, and it is already '
         'waiting there.'),
        (36.6, 'Next to it sits its mirror image, a 74HCT595, which collects the bits coming back from the SD '
               'card one at a time, and holds them as a byte.',
         'Next to it sits its mirror image, a seventy-four H-C-T five ninety-five, which collects the bits '
         'coming back from the S-D card one at a time, and holds them as a byte.'),
        (46.8, "Both registers need clock pulses, and the PC doesn't provide them. The card has to make its "
               "own clock, and it has to know exactly when to start.",
         "Both registers need clock pulses, and the PC doesn't provide them. The card has to make its "
         "own clock, and it has to know exactly when to start."),
    ],
    's08_edge_detect': [
        (0.8, 'Starting too early would spoil everything: as long as /IOW is low, the 165 keeps loading, and '
              'cannot shift.',
         'Starting too early would spoil everything: as long as I-O-W is low, the one sixty-five keeps '
         'loading, and cannot shift.'),
        (9.0, 'So the card waits for the CPU to let go. Two flip-flops watch /IOW, and the moment it is '
              'released, they produce a single short pulse.',
         'So the card waits for the CPU to let go. Two flip-flops watch I-O-W, and the moment it is '
         'released, they produce a single short pulse.'),
        (18.6, 'That pulse is what starts the clock.',
         'That pulse is what starts the clock.'),
    ],
    's09_counter': [
        (0.6, 'The clock itself comes from a 16 MHz oscillator and a 4-bit counter, which starts to run as soon '
              'as that pulse arrives.',
         'The clock itself comes from a sixteen megahertz oscillator and a four-bit counter, which starts to '
         'run as soon as that pulse arrives.'),
        (9.0, "The counter's lowest bit flips between 0 and 1 on every tick of the oscillator, which gives an "
              "8 MHz clock, SCK. Sixteen ticks make eight pulses.",
         "The counter's lowest bit flips between zero and one on every tick of the oscillator, which gives an "
         "eight megahertz clock, S-C-K. Sixteen ticks make eight pulses."),
        (19.4, 'When the count reaches fifteen, the counter stops itself: eight clock pulses, and then silence.',
         'When the count reaches fifteen, the counter stops itself: eight clock pulses, and then silence.'),
        (25.4, 'Each pulse has two edges, one where the clock goes up and one where it comes down again, and as '
               'we will see, the card uses both.',
         'Each pulse has two edges, one where the clock goes up and one where it comes down again, and as '
         'we will see, the card uses both.'),
        (32.6, 'Before those pulses can reach the SD card, though, there is one more problem to solve.',
         'Before those pulses can reach the S-D card, though, there is one more problem to solve.'),
    ],
    # -- Act 4: the exchange -------------------------------------------------
    's10_spi_wires': [
        (0.6, "The SD card runs on 3.3 V, and the PC's 5 V signals would damage it.",
         "The S-D card runs on three point three volts, and the PC's five volt signals would damage it."),
        (7.0, 'That is why a 74LVC125 buffer sits in between. It runs on 3.3 V itself but accepts 5 V inputs, '
              'so the card only ever sees 3.3 V.',
         'That is why a seventy-four L-V-C one twenty-five buffer sits in between. It runs on three point '
         'three volts itself but accepts five volt inputs, so the card only ever sees three point three volts.'),
        (20.2, 'In the other direction, MISO comes back at 3.3 V, which the 595 still reads as a 1.',
         'In the other direction, Miso comes back at three point three volts, which the five ninety-five '
         'still reads as a one.'),
        (26.4, 'And chip select is already low: the driver set it once at start-up, by reading port 333h.',
         'And chip select is already low: the driver set it once at start-up, by reading port '
         'three-thirty-three.'),
    ],
    's11_shift': [
                (0.4, 'Now the eight clocks run, and bits move both ways at once.',
         'Now the eight clocks run, and bits move both ways at once.'),
        (4.4, 'Each time the clock goes up, the SD card reads a bit from MOSI, and the 595 picks up a bit from '
              'MISO.',
         'Each time the clock goes up, the S-D card reads a bit from Mosi, and the five ninety-five picks up a '
         'bit from Miso.'),
        (11.6, 'And each time it comes down, the 165 moves its next bit into place, so a bit never changes '
               'while someone is reading it.',
         'And each time it comes down, the one sixty-five moves its next bit into place, so a bit never changes '
         'while someone is reading it.'),
        (20.0, 'While a command is going out, the card has nothing to say yet, so it simply answers with ones.',
         'While a command is going out, the card has nothing to say yet, so it simply answers with ones.'),
        (25.4, "After eight clocks, the SD card has our byte, 51h, and the 595 holds the card's reply. Sending "
               "and receiving happen on the very same clocks: SPI simply swaps two bytes.",
         "After eight clocks, the S-D card has our byte, fifty-one hex, and the five ninety-five holds the "
         "card's reply. Sending and receiving happen on the very same clocks: S-P-I simply swaps two bytes."),
        (39.4, 'And all of this takes just one microsecond.',
         'And all of this takes just one microsecond.'),
    ],
    # -- Act 5: the answer ---------------------------------------------------
    's12_answer': [
        (0.4, 'The rest of the command follows in exactly the same way: five more bytes, which include the '
              'number of the block to read.',
         'The rest of the command follows in exactly the same way: five more bytes, which include the '
         'number of the block to read.'),
        (7.5, 'The card then needs a moment. To hear its answer, the driver keeps sending FFh, a byte of all '
              'ones, and reads port 330h after each one to see what came back.',
         'The card then needs a moment. To hear its answer, the driver keeps sending F-F hex, a byte of all '
         'ones, and reads port three-thirty after each one to see what came back.'),
        (17.9, 'First the card replies "OK", and then "here comes the data".',
         'First the card replies: OK, and then: here comes the data.'),
        (22.3, 'Then the first byte of the block arrives: EBh, the start of a FAT boot sector.',
         'Then the first byte of the block arrives: E-B hex, the start of a FAT boot sector.'),
        (31.2, 'It now waits in the 595, ready for the CPU to collect.',
         'It now waits in the five ninety-five, ready for the CPU to collect.'),
    ],
    's13_readback': [
        (0.5, "To collect it, the CPU reads port 330h. The decoder recognises the read, and the 595 puts its "
              "byte onto the card's internal bus.",
         "To collect it, the CPU reads port three-thirty. The decoder recognises the read, and the five "
         "ninety-five puts its byte onto the card's internal bus."),
        (9.9, 'The 245, our gate, now turns around to face the CPU, and the byte flows out onto the ISA bus.',
         'The two forty-five, our gate, now turns around to face the CPU, and the byte flows out onto the '
         'I-S-A bus.'),
        (16.9, "And there it is: EBh, in the CPU's register AL.",
         "And there it is: E-B hex, in the CPU's register A-L."),
    ],
    # -- Act 6: scale --------------------------------------------------------
    's14_sector': [
        (0.2, 'That was a single byte. A block, or sector, holds 512 of them, plus a few extra bytes for the '
              'command, the replies and a checksum.',
         'That was a single byte. A block, or sector, holds five hundred and twelve of them, plus a few extra '
         'bytes for the command, the replies and a checksum.'),
        (9.0, "Every one of them takes the path you have just seen, eight clocks at a time. Including the work "
              "the PC itself has to do, that adds up to about 38 kilobytes per second.",
         "Every one of them takes the path you have just seen, eight clocks at a time. Including the work "
         "the PC itself has to do, that adds up to about thirty-eight kilobytes per second."),
        (19.4, 'A file, in the end, is just a list of sectors, and the driver turns them into an ordinary DOS '
               'drive.',
         'A file, in the end, is just a list of sectors, and the driver turns them into an ordinary DOS '
         'drive.'),
    ],
    # -- Act 7: the whole card -----------------------------------------------
    's15_recap': [
        (0.6, "Now that we know what every part does, let's look at the card one last time.",
         "Now that we know what every part does, let's look at the card one last time."),
        (4.8, 'The 688, the 32 and the 139 listen to the bus: together they recognise our address and work out '
              'what the CPU wants, while a small latch next to them holds chip select.',
         'The six eighty-eight, the thirty-two and the one thirty-nine listen to the bus: together they '
         'recognise our address and work out what the CPU wants, while a small latch next to them holds '
         'chip select.'),
        (16.4, 'The 245 is the gate that lets bytes in and out.',
         'The two forty-five is the gate that lets bytes in and out.'),
        (20.6, 'The 165 and the 595 are the translators, turning bytes into bits and bits back into bytes.',
         'The one sixty-five and the five ninety-five are the translators, turning bytes into bits and bits '
         'back into bytes.'),
        (27.2, 'Two flip-flops, a counter and a few gates make the clock: exactly eight pulses, started at '
               'exactly the right moment.',
         'Two flip-flops, a counter and a few gates make the clock: exactly eight pulses, started at '
         'exactly the right moment.'),
        (35.0, "And the 125 is the bridge to the SD card's 3.3 V world.",
         "And the one twenty-five is the bridge to the S-D card's three point three volt world."),
        (40.2, 'Fourteen chips, five jobs.',
         'Fourteen chips, five jobs.'),
    ],
    's16_outro': [
        (1.0, 'No processor and no firmware: just logic, turning bytes into bits and bits back into bytes.',
         'No processor and no firmware: just logic, turning bytes into bits and bits back into bytes.'),
        (7.4, 'Slot-otter is open hardware, and its schematics, board and driver are all on GitHub.',
         'Slot-otter is open hardware, and its schematics, board and driver are all on GitHub.'),
    ],
}


def subtitle(scene, i):
    """Subtitle for line i of a scene (None = no subtitle, e.g. the title card says it)."""
    return NARRATION[scene][i][1]

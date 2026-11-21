# Slot-otter Classic — the story (draft 4)

**Premise.** A retro PC wants to read a file from an SD card. The PC speaks in
*bytes*, on a parallel bus. The SD card speaks in *bits*, over SPI. Fourteen logic
chips translate between the two. We follow one byte on its way to the SD card, and
one byte on its way back.

**Audience.** Retro-computing hobbyists: they know what a bit, a byte and an I/O
port are, and have seen a logic chip, but are not digital designers.

**Rules.** The narration leads; the visuals follow it. Every scene answers one
question the viewer has at that moment. A part number is named only when that chip's
job is the point of the sentence; a signal name only when it is on screen and comes
back later. Narration is given here in written form; the spoken form (numbers spelled
out, etc.) is derived from it.

**Voice.** Tell it as one story, not as a list of facts. Each line follows on from the
one before, sentences vary in length, and every scene opens by picking up where the
last one ended. The intro starts high-level (what the card is for, and what each side
speaks) before the film goes down to wires and chips.

Format: `[on screen]` notes, then the narration, one paragraph per spoken line.

---

## Act 1 — What the card does

*What does this card do, and why is that hard?*

### 1. Title and overview
[Photo of the card fades in under the title card. Then, with the card in the middle
of the WIDE shot: on the left a PC panel (8088 / 8086 CPU; `OUT DX, AL` = write a
byte, `IN AL, DX` = read a byte; port 330h) wired to the card edge, which lights up;
51h travels to the card on OUT and EBh comes back on IN. On the right an SD-card
panel (speaks SPI: a clock and bits travelling one at a time) wired to the SD socket.
Finally a "Slot-otter: bytes ⇄ bits" label in the middle while bytes and bits move on
both sides. The panels fade and the camera pushes in to the FULL shot of scene 2.]

> Slot-otter Classic.

> It is an 8-bit ISA card that lets an old PC, even one of the very first 8088
> machines, use an SD card as an ordinary DOS drive.

> To the PC, the card is simply a set of I/O ports. An 8088 or 8086 talks to its
> hardware through such ports: with one instruction it writes a byte to a port, and
> with another it reads a byte back.

> The SD card knows nothing about ports. In the simple mode used here, it speaks SPI:
> data travels one bit at a time, in step with a clock signal.

> Slot-otter sits in between. Every byte the PC writes becomes a stream of bits for
> the SD card, and the bits that come back are gathered into a byte the PC can read.

### 2. The x-ray
[Photo cross-fades to the x-ray. The chips outline themselves in five groups, in
neutral white and without names: the same five sets that scene 15 will name and
colour. For now they are a puzzle.]

> What makes this card unusual is how it does that. There is no microcontroller on it
> and no firmware, just fourteen 74-series logic chips, an oscillator and a voltage
> regulator.

> So how can a handful of logic chips talk to an SD card? To find out, we will follow
> a single byte from the PC to the SD card, and another one on its way back, and meet
> each of these chips along the way.

### 3. Two worlds, up close
[Board dimmed. Left: the PC side — eight parallel data wires and an address bus; the
byte 51h appears on all eight wires at once. Right: the SD-card side — four wires;
a clock ticks, the bits of 51h travel one by one on MOSI; replies come back on MISO;
chip select sits low. Finally the two sides map onto the real board: card edge =
bytes, microSD socket = bits, the logic in between glows faintly.]

> But first, let's take a closer look at both sides, starting with the PC.

> On the ISA bus, the PC puts all eight bits of a byte on eight wires at once,
> together with an address that says where the byte should go.

> The SD card, by contrast, takes in one bit at a time, on a single wire called MOSI.

> A second wire, the clock SCK, tells the card when to read each bit, so eight clock
> pulses carry one byte.

> The card's answers come back the same way, bit by bit, on a third wire called MISO.

> And a fourth wire, chip select, has to be held low, at zero volts, for the card to
> listen at all.

> That is the translation this card performs: bytes into bits, and bits back into
> bytes.

> On the board, bytes arrive at the gold contacts, and leave as bits through the SD
> socket.

---

## Act 2 — Is this for me?

*How does the card know the CPU is talking to it, and what it wants?*

### 4. The card edge
[Gold fingers. CPU card: `MOV DX,330h / MOV AL,51h / OUT DX,AL`. Bit tokens appear
on the address and data fingers; then /IOW lights up on the back row.]

> Now let's follow our byte. The CPU writes 51h to I/O port 330h.

> That value is no accident: 51h is the first byte of the SD card's command to read
> one block.

> For a brief moment, the bus carries both the address and the byte.

> At the same time, the CPU pulls a wire called /IOW low. The slash means the wire is
> active when it is low, and here it tells the cards on the bus that this is a write.

### 5. Is this for me?
[Address lines A9..A2 travel to the 74HCT688; the DIP switch is drawn as slide
switches; column-by-column match; then a "what if: 300h" counter-example.]

> Every card in the PC sees this address, so our card first has to ask: is this meant
> for me?

> I/O addresses use ten lines. Eight of them, A9 down to A2, run to a 74HCT688, a chip
> that compares two 8-bit numbers.

> Its second number comes from a DIP switch, where you set the address the card should
> answer to.

> When all eight bits match, the card knows it is being addressed.

> Any other address fails, and the card ignores it.

> A1 and A0 are not compared at all, so the card answers to four ports in a row: 330h
> to 333h.

### 6. What does the CPU want?
[The decoder lights up; a port table builds: 330h / 331h / 332h / 333h × read / write.
"330h, write: send a byte" glows; then "330h, read: fetch the reply" glows; the
other rows stay dim.]

> Next, the card works out what the CPU wants: a read or a write, and on which of its
> four ports.

> A decoder combines A1 and A0 with the read and write signals, and turns them into a
> single action.

> Only two of these actions matter for our story. Writing to 330h sends a byte to the
> SD card,

> and reading from the same port fetches the card's reply.

> The other ports handle housekeeping.

---

## Act 3 — From byte to bits

*How does a byte become a row of bits, and who decides when?*

### 7. Two shift registers
[Bits of 51h flow from the fingers through the 74HCT245 into the card. Panel: the byte
splits into the eight cells of the 74HC165; bit 7 lights up on MOSI. Then the 74HCT595
is outlined next to it, its eight cells empty.]

> First, the byte has to get onto the card. It enters through a 74HCT245, the card's
> gate to the bus, which lets data in when the CPU writes, and out when it reads.

> Behind the gate, the actual translation is done by two shift registers.

> The first, a 74HC165, has eight cells that load a whole byte at once and then hand
> it out one bit at a time. While /IOW is still low, our byte is copied in.

> Every clock pulse then pushes the next bit onto MOSI. Bit 7 goes first, and it is
> already waiting there.

> Next to it sits its mirror image, a 74HCT595, which collects the bits coming back
> from the SD card one at a time, and holds them as a byte.

> Both registers need clock pulses, and the PC doesn't provide them. The card has to
> make its own clock, and it has to know exactly when to start.

### 8. Waiting for the CPU to let go
[Two flip-flops highlighted; a small timing diagram: /IOW rises, a short pulse appears.]

> Starting too early would spoil everything: as long as /IOW is low, the 165 keeps
> loading, and cannot shift.

> So the card waits for the CPU to let go. Two flip-flops watch /IOW, and the moment
> it is released, they produce a single short pulse.

> That pulse is what starts the clock.

### 9. Exactly eight clocks
[The 74HC163 counter: lamps Q3..Q0, a count, a timing panel with the oscillator, SCK
and "stop". The count runs 0..15, then stops. On screen the word is "stop" too.]

> The clock itself comes from a 16 MHz oscillator and a 4-bit counter, which starts to
> run as soon as that pulse arrives.

> The counter's lowest bit flips between 0 and 1 on every tick of the oscillator,
> which gives an 8 MHz clock, SCK. Sixteen ticks make eight pulses.

> When the count reaches fifteen, the counter stops itself: eight clock pulses, and
> then silence.

> Each pulse has two edges, one where the clock goes up and one where it comes down
> again, and as we will see, the card uses both.

> Before those pulses can reach the SD card, though, there is one more problem to
> solve.

---

## Act 4 — The exchange

*What actually happens on the four wires?*

### 10. Into the 3.3 V world
[SD corner. Regulator, 74LVC125 and socket outlined; the four SPI lanes light up; a
panel shows each buffer's direction and voltage.]

> The SD card runs on 3.3 V, and the PC's 5 V signals would damage it.

> That is why a 74LVC125 buffer sits in between. It runs on 3.3 V itself but accepts 5
> V inputs, so the card only ever sees 3.3 V.

> In the other direction, MISO comes back at 3.3 V, which the 595 still reads as a 1.

> And chip select is already low: the driver set it once at start-up, by reading port
> 333h.

### 11. Bits out, bits in *(centrepiece)*
[The SPI ring: 74HC165 → MOSI → SD card → MISO → 74HCT595, with the clock on top. Slow
motion for the first clocks, faster later.]

> Now the eight clocks run, and bits move both ways at once.

> Each time the clock goes up, the SD card reads a bit from MOSI, and the 595 picks up
> a bit from MISO.

> And each time it comes down, the 165 moves its next bit into place, so a bit never
> changes while someone is reading it.

> While a command is going out, the card has nothing to say yet, so it simply answers
> with ones.

> After eight clocks, the SD card has our byte, 51h, and the 595 holds the card's
> reply. Sending and receiving happen on the very same clocks: SPI simply swaps two
> bytes.

> And all of this takes just one microsecond.

---

## Act 5 — The answer

*How does data come back to the CPU?*

### 12. The card answers
[The same ring. The rest of the command goes out quickly; then FFh goes out and the
replies come back: OK, data token, then EBh in slow motion.]

> The rest of the command follows in exactly the same way: five more bytes, which
> include the number of the block to read.

> The card then needs a moment. To hear its answer, the driver keeps sending FFh, a
> byte of all ones, and reads port 330h after each one to see what came back.

> First the card replies "OK", and then "here comes the data".

> Then the first byte of the block arrives: EBh, the start of a FAT boot sector.

> It now waits in the 595, ready for the CPU to collect.

### 13. Back to the CPU
[CPU card: `IN AL, DX`. The 595's outputs switch on, the 245 turns around, bit tokens
flow back to the fingers; `AL = EBh`.]

> To collect it, the CPU reads port 330h. The decoder recognises the read, and the 595
> puts its byte onto the card's internal bus.

> The 245, our gate, now turns around to face the CPU, and the byte flows out onto the
> ISA bus.

> And there it is: EBh, in the CPU's register AL.

---

## Act 6 — Scale

*And a whole file?*

### 14. A whole sector
[Wide view. A strip: command · OK · token · 512 data bytes · checksum. Bytes stream in,
ever faster: one comet on MISO, eight on the data lines; a counter runs to 512.]

> That was a single byte. A block, or sector, holds 512 of them, plus a few extra
> bytes for the command, the replies and a checksum.

> Every one of them takes the path you have just seen, eight clocks at a time.
> Including the work the PC itself has to do, that adds up to about 38 kilobytes per
> second.

> A file, in the end, is just a list of sectors, and the driver turns them into an
> ordinary DOS drive.

---

## Act 7 — The whole card

*Now that we know every part: what does the board look like?*

### 15. Fourteen chips, five jobs
[Wide x-ray, the same view as scene 2. The five groups from scene 2 return; one by
one each lights up in its own colour with a short label as its line is spoken, then
stays lit in a softer tone, until the board is a colour map of the five jobs. The
oscillator and the regulator glow with their groups but are not counted.]

| Set | Chips | Label |
| --- | --- | --- |
| Listeners | 74HCT688 (U8), 74HCT32 (U2), 74HCT139 (U3), 74HC00 chip-select latch (U5) | *listen to the bus* |
| Gate | 74HCT245 (U9) | *the gate* |
| Translators | 74HC165 (U6), 74HCT595 (U7) | *bytes ⇄ bits* |
| Clock makers | 74HC74 ×2 (U13, U10), 74HC08 (U11), 74HCT04 (U12), 74HC00 (U1), 74HC163 (U4) + 16 MHz oscillator | *exactly eight clocks* |
| Bridge | 74LVC125 (U21) + 3.3 V regulator | *to 3.3 V* |

4 + 1 + 2 + 6 + 1 = 14 logic chips. Chips that do an odd job elsewhere (one 74HCT04
gate helps start the clock, the others drive the status LEDs) are shown in their main
set.

> Now that we know what every part does, let's look at the card one last time.

> The 688, the 32 and the 139 listen to the bus: together they recognise our address
> and work out what the CPU wants, while a small latch next to them holds chip select.

> The 245 is the gate that lets bytes in and out.

> The 165 and the 595 are the translators, turning bytes into bits and bits back into
> bytes.

> Two flip-flops, a counter and a few gates make the clock: exactly eight pulses,
> started at exactly the right moment.

> And the 125 is the bridge to the SD card's 3.3 V world.

> Fourteen chips, five jobs.

### 16. Outro
[X-ray back to photo. End card: Slot-otter · github.com/ifilot/slot-otter · licences.]

> No processor and no firmware: just logic, turning bytes into bits and bits back into
> bytes.

> Slot-otter is open hardware, and its schematics, board and driver are all on GitHub.
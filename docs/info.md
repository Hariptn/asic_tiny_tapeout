<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

This project implements a direct-mapped cache with a simple CPU-facing interface, backed by an internal main memory.

The design has two main parts:

- **CPU input FSM**: reads three bytes over `ui_in`, one per clock cycle, to form a request — first the address, then the write data, then a control byte. The control byte's bit 0 selects write vs. read, and bit 1 signals the request is valid. Once valid, the request is passed to the cache and the FSM waits until the cache signals it's ready before accepting a new request.

- **Direct-mapped cache**: 16 cache lines, each holding 4 bytes (32 bits) with a 2-bit tag and a valid bit. The requested address is split into a 2-bit tag, a 4-bit index, and a 2-bit byte offset. On a read hit, the requested byte is returned immediately. On a read miss, the cache fetches the full 4-byte line from the internal main memory (32 words × 32 bits) and stores it before returning the byte. Writes are write-through: they always update main memory, and update the cache line too if that line is already cached (no-write-allocate on a write miss).

Status signals — cache ready to accept a new request, and read data valid — are exposed on the bidirectional output pins.

## How to test

To issue a request, drive `ui_in` over three consecutive clock cycles:

1. **Cycle 1** — address byte
2. **Cycle 2** — write data byte (ignored for reads, but still consumed)
3. **Cycle 3** — control byte: bit 0 = write enable (1 = write, 0 = read), bit 1 = request valid (must be 1 to trigger the request)

After the control cycle, wait for `uio_out[0]` (cache ready) to go high again before the read result is valid — `uo_out` holds the read byte, and `uio_out[1]` pulses high when that data is valid.

Example: to write `0xAB` to address `0x00`, then read it back —
1. Drive `ui_in = 0x00` (address), one cycle
2. Drive `ui_in = 0xAB` (data), one cycle
3. Drive `ui_in = 0b11` (write + valid), one cycle
4. Wait for `uio_out[0]` to pulse
5. Drive `ui_in = 0x00` (address), one cycle
6. Drive `ui_in = 0x00` (unused for read), one cycle
7. Drive `ui_in = 0b10` (read + valid), one cycle
8. Wait for `uio_out[0]`/`uio_out[1]`, then check `uo_out == 0xAB`

## External hardware

None — this project only uses the dedicated Tiny Tapeout I/O pins (`ui_in`, `uo_out`, `uio_in`/`uio_out`) and requires no external hardware.
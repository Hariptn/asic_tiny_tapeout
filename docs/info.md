<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

This project implements a direct-mapped cache with a one-cycle CPU-facing interface, backed by an internal 16-byte main memory.

The design has two main parts:

- **CPU interface**: accepts one request directly from the input pins when `request_valid` is high and `cache_ready` is high. The 4-bit address is carried on `ui_in[3:0]`; write data is carried on `ui_in[7:4]` and `uio_in[3:0]`; `uio_in[4]` selects writes and `uio_in[5]` is `request_valid`.

- **Direct-mapped cache**: 4 cache lines, each holding 2 bytes (16 bits), with a 1-bit tag and a valid bit. The 4-bit address is split into a 1-bit tag (`addr[3]`), a 2-bit index (`addr[2:1]`), and a 1-bit byte offset (`addr[0]`). On a read hit, the requested byte is returned immediately. On a read miss, the cache fetches both bytes of the line from main memory before returning the requested byte. Writes are write-through: they always update main memory, and update the cached line when the address is already a cache hit; write misses do not allocate a cache line.

Status signals are exposed on the bidirectional output pins: `uio_out[6]` is `cache_ready` and `uio_out[7]` is `read_data_valid`. The output-enable pins drive only `uio[7:6]`; `uio[5:0]` remain inputs.

## How to test

To issue a request, first wait for `uio_out[6]` (`cache_ready`) to be high, then drive the request pins for one clock cycle:

1. `ui_in[3:0]` — 4-bit address (`ui_in[7:4]` is the upper write-data nibble)
2. `uio_in[3:0]` — lower write-data nibble
3. `uio_in[4]` — `write_enable` (1 = write, 0 = read)
4. `uio_in[5]` — `request_valid` (must be 1 to trigger the request)

After the request is accepted, wait for `uio_out[6]` to go high again. For reads, `uo_out` holds the read byte and `uio_out[7]` pulses high when that data is valid.

Example: to write `0xAB` to address `0x00`, then read it back —
1. Drive `ui_in = 0xA0` and `uio_in = 0x3B` (address `0x0`, data `0xAB`, write + valid), one cycle.
2. Wait for `uio_out[6]` (`cache_ready`) to go high.
3. Drive `ui_in = 0x00` and `uio_in = 0x20` (address `0x0`, read + valid), one cycle.
4. Wait for `uio_out[7]` (`read_data_valid`), then check `uo_out == 0xAB`.

## External hardware

None — this project only uses the dedicated Tiny Tapeout I/O pins (`ui_in`, `uo_out`, `uio_in`/`uio_out`) and requires no external hardware.
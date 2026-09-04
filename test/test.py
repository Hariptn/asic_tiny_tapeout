# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

"""
Cocotb testbench for tt_um_tpmdle: a direct-mapped cache in front of a
16-byte main memory, controlled over a ready/valid CPU-style bus.

Bus protocol (see RTL comments):
    ui_in[3:0]  = address[3:0]
    ui_in[7:4]  = write data[7:4]
    uio_in[3:0] = write data[3:0]
    uio_in[4]   = write enable
    uio_in[5]   = request valid
    uio_out[6]  = cache ready  (uio_oe marks uio[7:6] as outputs)
    uio_out[7]  = read-data valid
    uo_out[7:0] = read data

Address layout (4 bits): [3]=tag, [2:1]=index (4 lines), [0]=byte offset.
Cache is write-through, no-write-allocate, direct-mapped, 4 lines x 2 bytes.
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge

READY_BIT = 1 << 6   # uio_out[6] = cpu_req_ready
RVALID_BIT = 1 << 7  # uio_out[7] = cpu_rdata_valid

CLOCK_PERIOD = 10  # us, matches the default TT clock convention
TIMEOUT_CYCLES = 50


async def reset_dut(dut):
    """Apply a clean reset with ena held high throughout."""
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)


async def wait_for_bit(dut, bitmask, timeout_cycles=TIMEOUT_CYCLES):
    """Wait until uio_out has `bitmask` set. Returns cycles waited, or -1 on timeout."""
    for cycle in range(1, timeout_cycles + 1):
        await RisingEdge(dut.clk)
        if int(dut.uio_out.value) & bitmask:
            return cycle
    return -1


async def wait_ready(dut, timeout_cycles=TIMEOUT_CYCLES):
    cycles = await wait_for_bit(dut, READY_BIT, timeout_cycles)
    assert cycles != -1, "Timeout waiting for cache ready"
    return cycles


async def cache_write(dut, addr, data):
    """Issue a write request once the cache is ready, then wait for completion."""
    await wait_ready(dut)

    dut.ui_in.value = ((data & 0xF0) | (addr & 0x0F))
    dut.uio_in.value = (data & 0x0F) | (1 << 5) | (1 << 4)  # req_valid=1, we=1
    await RisingEdge(dut.clk)  # request sampled/accepted on this edge
    dut.uio_in.value = 0
    dut.ui_in.value = 0

    cycles = await wait_for_bit(dut, READY_BIT)
    assert cycles != -1, f"Timeout waiting for write completion (addr={addr:#x})"
    return cycles


async def cache_read(dut, addr):
    """Issue a read request once the cache is ready, then wait for the data."""
    await wait_ready(dut)

    dut.ui_in.value = (addr & 0x0F)
    dut.uio_in.value = (1 << 5)  # req_valid=1, we=0
    await RisingEdge(dut.clk)  # request sampled/accepted on this edge
    dut.uio_in.value = 0
    dut.ui_in.value = 0

    cycles = await wait_for_bit(dut, RVALID_BIT)
    assert cycles != -1, f"Timeout waiting for read data (addr={addr:#x})"
    data = int(dut.uo_out.value)
    return data, cycles


@cocotb.test()
async def test_reset_and_ready(dut):
    """After reset, the cache should come up idle and assert ready."""
    dut._log.info("Start clock")
    clock = Clock(dut.clk, CLOCK_PERIOD, units="us")
    cocotb.start_soon(clock.start())

    await reset_dut(dut)

    cycles = await wait_for_bit(dut, READY_BIT)
    assert cycles != -1, "cpu_req_ready never asserted after reset"
    dut._log.info(f"Ready asserted {cycles} cycle(s) after reset")


@cocotb.test()
async def test_single_write_then_read(dut):
    """A byte written to an address should read back correctly (cold miss then fill)."""
    clock = Clock(dut.clk, CLOCK_PERIOD, units="us")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    addr, data = 0x3, 0xAB
    await cache_write(dut, addr, data)

    readback, _ = await cache_read(dut, addr)
    assert readback == data, f"addr={addr:#x}: expected {data:#x}, got {readback:#x}"


@cocotb.test()
async def test_read_miss_then_hit_is_faster(dut):
    """A repeat read of the same address (now cached) should complete in fewer
    cycles than the original cold miss that had to fetch from main memory."""
    clock = Clock(dut.clk, CLOCK_PERIOD, units="us")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    addr, data = 0x5, 0x7E
    await cache_write(dut, addr, data)

    miss_data, miss_cycles = await cache_read(dut, addr)  # cache empty -> miss, fetch from mem
    hit_data, hit_cycles = await cache_read(dut, addr)    # now cached -> hit

    assert miss_data == data
    assert hit_data == data
    dut._log.info(f"Miss took {miss_cycles} cycles, hit took {hit_cycles} cycles")
    assert hit_cycles < miss_cycles, "Cache hit should resolve faster than a cold miss"


@cocotb.test()
async def test_write_hit_updates_cache(dut):
    """Writing to a cached address must update the cache, not just memory."""
    clock = Clock(dut.clk, CLOCK_PERIOD, units="us")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    addr = 0x5
    await cache_write(dut, addr, 0x11)
    await cache_read(dut, addr)          # miss -> now cached

    await cache_write(dut, addr, 0x22)   # write-hit: line is resident
    readback, cycles = await cache_read(dut, addr)  # should HIT with new data
    assert readback == 0x22, f"stale cache data after write-hit: got {readback:#x}"


@cocotb.test()
async def test_cache_aliasing_and_writethrough(dut):
    """Addresses that alias to the same cache line (same index, different tag)
    must evict each other but still read correctly, since writes are
    write-through and always land in main memory."""
    clock = Clock(dut.clk, CLOCK_PERIOD, units="us")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    # index = addr[2:1]. addr 0x0 and 0x8 share index 0 but differ in tag (bit 3).
    addr_a, data_a = 0x0, 0x11
    addr_b, data_b = 0x8, 0x22

    await cache_write(dut, addr_a, data_a)
    await cache_write(dut, addr_b, data_b)

    # Read addr_a: forces the shared line to reload from main memory,
    # which must still hold the correct write-through value.
    read_a, _ = await cache_read(dut, addr_a)
    assert read_a == data_a, f"addr={addr_a:#x}: expected {data_a:#x}, got {read_a:#x}"

    # Read addr_b: this evicts addr_a's line again; value must still be correct.
    read_b, _ = await cache_read(dut, addr_b)
    assert read_b == data_b, f"addr={addr_b:#x}: expected {data_b:#x}, got {read_b:#x}"

    # Re-read addr_a once more to confirm the alias round-trips cleanly.
    read_a2, _ = await cache_read(dut, addr_a)
    assert read_a2 == data_a, f"addr={addr_a:#x}: expected {data_a:#x}, got {read_a2:#x}"


@cocotb.test()
async def test_full_memory_sweep(dut):
    """Write a distinct byte to every one of the 16 memory addresses, then
    read every address back in reverse order to exercise every cache line
    and every possible eviction, checking write-through correctness."""
    clock = Clock(dut.clk, CLOCK_PERIOD, units="us")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    expected = {addr: (addr * 7 + 3) & 0xFF for addr in range(16)}

    for addr, data in expected.items():
        await cache_write(dut, addr, data)

    for addr in reversed(range(16)):
        data, _ = await cache_read(dut, addr)
        assert data == expected[addr], (
            f"addr={addr:#x}: expected {expected[addr]:#x}, got {data:#x}"
        )


@cocotb.test()
async def test_ena_gates_operation(dut):
    """While ena is low, the cache must hold in idle and never assert ready."""
    clock = Clock(dut.clk, CLOCK_PERIOD, units="us")
    cocotb.start_soon(clock.start())
    await reset_dut(dut)

    # Confirm normal operation first.
    await cache_write(dut, 0x1, 0x99)

    # Disable and hold for a few cycles; ready must stay low.
    dut.ena.value = 0
    await ClockCycles(dut.clk, 5)
    assert int(dut.uio_out.value) & READY_BIT == 0, "ready must be low while ena=0"

    # Re-enable and confirm the cache resumes normal operation.
    dut.ena.value = 1
    await wait_ready(dut)
    readback, _ = await cache_read(dut, 0x1)
    assert readback == 0x99, f"expected 0x99 after re-enable, got {readback:#x}"
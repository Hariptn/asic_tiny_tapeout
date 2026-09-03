# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles


async def cache_write(dut, addr, data):
    """Drive the 3-cycle CPU write protocol: address, data, control."""
    dut.ui_in.value = addr
    await ClockCycles(dut.clk, 1)
    dut.ui_in.value = data
    await ClockCycles(dut.clk, 1)
    dut.ui_in.value = 0b11  # bit0=we=1, bit1=valid=1
    await ClockCycles(dut.clk, 1)
    dut.ui_in.value = 0  # stop driving further requests
    # Wait for cpu_req_ready to pulse high again (uio_out bit 0)
    for _ in range(20):
        await ClockCycles(dut.clk, 1)
        if dut.uio_out.value & 0x1:
            break


async def cache_read(dut, addr):
    """Drive the 3-cycle CPU read protocol: address, (dummy), control."""
    dut.ui_in.value = addr
    await ClockCycles(dut.clk, 1)
    dut.ui_in.value = 0
    await ClockCycles(dut.clk, 1)
    dut.ui_in.value = 0b10  # bit0=we=0, bit1=valid=1
    await ClockCycles(dut.clk, 1)
    dut.ui_in.value = 0
    for _ in range(20):
        await ClockCycles(dut.clk, 1)
        if dut.uio_out.value & 0x1:
            break


@cocotb.test()
async def test_project(dut):
    dut._log.info("Start")

    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    dut._log.info("Reset")
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)

    dut._log.info("Write 0xAB to address 0x00")
    await cache_write(dut, 0x00, 0xAB)

    dut._log.info("Read back address 0x00")
    await cache_read(dut, 0x00)

    assert dut.uo_out.value == 0xAB, f"Expected 0xAB, got {dut.uo_out.value}"

    dut._log.info("Test passed")
```python
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


# ============================================================
# Helper: Reset DUT
# ============================================================

async def reset_dut(dut):
    """Apply active-low reset."""

    dut.rst_n.value = 0
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.ena.value = 1

    # Hold reset for a few clock cycles
    for _ in range(3):
        await RisingEdge(dut.clk)

    dut.rst_n.value = 1

    # Allow design to leave reset
    for _ in range(2):
        await RisingEdge(dut.clk)


# ============================================================
# Helper: Read UIO status
# ============================================================

def cache_ready(dut):
    """
    uio_out[0] = cache ready
    uio_out[1] = read data valid
    """
    return int(dut.uio_out.value) & 0x01


def read_data_valid(dut):
    return (int(dut.uio_out.value) >> 1) & 0x01


# ============================================================
# Helper: Wait until cache is ready
# ============================================================

async def wait_cache_ready(dut, timeout=30):

    for _ in range(timeout):

        if cache_ready(dut):
            return

        await RisingEdge(dut.clk)

    raise AssertionError("Timeout waiting for cache ready")


# ============================================================
# Helper: CPU WRITE
# ============================================================

async def cpu_write(dut, address, data):
    """
    CPU write protocol:

    Cycle 0 -> address
    Cycle 1 -> write data
    Cycle 2 -> control
                 ui_in[0] = 1  -> WRITE
                 ui_in[1] = 1  -> REQUEST VALID
    """

    address &= 0xFF
    data &= 0xFF

    print(f"WRITE: address=0x{address:02X}, data=0x{data:02X}")

    # Wait until cache can accept request
    await wait_cache_ready(dut)

    # --------------------------------------------------------
    # Cycle 0: Address
    # --------------------------------------------------------

    dut.ui_in.value = address
    await RisingEdge(dut.clk)

    # --------------------------------------------------------
    # Cycle 1: Write data
    # --------------------------------------------------------

    dut.ui_in.value = data
    await RisingEdge(dut.clk)

    # --------------------------------------------------------
    # Cycle 2: Control
    #
    # bit 0 = write enable
    # bit 1 = request valid
    # --------------------------------------------------------

    dut.ui_in.value = 0b00000011
    await RisingEdge(dut.clk)

    # Release request
    dut.ui_in.value = 0

    # Wait for write-through transaction to complete
    await wait_cache_ready(dut)

    # Give one extra cycle for signals to settle
    await RisingEdge(dut.clk)

    print("WRITE COMPLETE")


# ============================================================
# Helper: CPU READ
# ============================================================

async def cpu_read(dut, address, expected=None):
    """
    CPU read protocol:

    Cycle 0 -> address
    Cycle 1 -> dummy data
    Cycle 2 -> control
                 ui_in[0] = 0 -> READ
                 ui_in[1] = 1 -> REQUEST VALID

    Returns the 8-bit read data.
    """

    address &= 0xFF

    print(f"READ: address=0x{address:02X}")

    # Wait until cache is ready
    await wait_cache_ready(dut)

    # --------------------------------------------------------
    # Cycle 0: Address
    # --------------------------------------------------------

    dut.ui_in.value = address
    await RisingEdge(dut.clk)

    # --------------------------------------------------------
    # Cycle 1: Dummy data
    #
    # Data is ignored for READ operations.
    # --------------------------------------------------------

    dut.ui_in.value = 0
    await RisingEdge(dut.clk)

    # --------------------------------------------------------
    # Cycle 2: Control
    #
    # bit 0 = 0 -> READ
    # bit 1 = 1 -> REQUEST VALID
    # --------------------------------------------------------

    dut.ui_in.value = 0b00000010
    await RisingEdge(dut.clk)

    # Release request
    dut.ui_in.value = 0

    # --------------------------------------------------------
    # Wait for read data valid
    # --------------------------------------------------------

    for _ in range(50):

        await RisingEdge(dut.clk)

        if read_data_valid(dut):

            value = int(dut.uo_out.value) & 0xFF

            print(
                f"READ COMPLETE: "
                f"address=0x{address:02X}, "
                f"data=0x{value:02X}"
            )

            if expected is not None:

                assert value == expected, (
                    f"READ ERROR at address 0x{address:02X}: "
                    f"expected 0x{expected:02X}, "
                    f"got 0x{value:02X}"
                )

                print(
                    f"PASS: address=0x{address:02X}, "
                    f"data=0x{value:02X}"
                )

            return value

    raise AssertionError(
        f"Timeout waiting for read data "
        f"at address 0x{address:02X}"
    )


# ============================================================
# TEST 1
# Reset Test
# ============================================================

@cocotb.test()
async def test_reset(dut):

    print("\n========================================")
    print("TEST 1: RESET")
    print("========================================")

    # Start clock
    cocotb.start_soon(
        Clock(dut.clk, 10, units="ns").start()
    )

    await reset_dut(dut)

    # Cache should become ready after reset
    await wait_cache_ready(dut)

    print("PASS: Cache reset successfully")
    print("========================================\n")


# ============================================================
# TEST 2
# Write then Read
# ============================================================

@cocotb.test()
async def test_write_read(dut):

    print("\n========================================")
    print("TEST 2: WRITE -> READ")
    print("========================================")

    cocotb.start_soon(
        Clock(dut.clk, 10, units="ns").start()
    )

    await reset_dut(dut)

    address = 0x10
    data = 0xAB

    # Write data
    await cpu_write(dut, address, data)

    # Read the same address
    result = await cpu_read(
        dut,
        address,
        expected=data
    )

    assert result == data

    print("PASS: Write followed by read")
    print("========================================\n")


# ============================================================
# TEST 3
# Read Hit
# ============================================================

@cocotb.test()
async def test_read_hit(dut):

    print("\n========================================")
    print("TEST 3: READ HIT")
    print("========================================")

    cocotb.start_soon(
        Clock(dut.clk, 10, units="ns").start()
    )

    await reset_dut(dut)

    address = 0x20
    data = 0x5A

    # First write
    await cpu_write(dut, address, data)

    # First read
    await cpu_read(
        dut,
        address,
        expected=data
    )

    # Second read
    #
    # The cache line should already be present,
    # therefore this should be a CACHE HIT.
    result = await cpu_read(
        dut,
        address,
        expected=data
    )

    assert result == data

    print("PASS: Read hit")
    print("========================================\n")


# ============================================================
# TEST 4
# Byte Offset Test
# ============================================================

@cocotb.test()
async def test_byte_offsets(dut):

    print("\n========================================")
    print("TEST 4: BYTE OFFSET TEST")
    print("========================================")

    cocotb.start_soon(
        Clock(dut.clk, 10, units="ns").start()
    )

    await reset_dut(dut)

    # Same cache line:
    #
    # Address 0x00 -> offset 00
    # Address 0x01 -> offset 01
    # Address 0x02 -> offset 10
    # Address 0x03 -> offset 11

    test_data = {
        0x00: 0x11,
        0x01: 0x22,
        0x02: 0x33,
        0x03: 0x44
    }

    # Write all four bytes
    for address, data in test_data.items():

        await cpu_write(
            dut,
            address,
            data
        )

    # Read all four bytes
    for address, expected in test_data.items():

        result = await cpu_read(
            dut,
            address,
            expected=expected
        )

        assert result == expected

    print("PASS: All four byte offsets")
    print("========================================\n")


# ============================================================
# TEST 5
# Cache Miss / Allocation
# ============================================================

@cocotb.test()
async def test_cache_miss_allocate(dut):

    print("\n========================================")
    print("TEST 5: CACHE MISS + ALLOCATION")
    print("========================================")

    cocotb.start_soon(
        Clock(dut.clk, 10, units="ns").start()
    )

    await reset_dut(dut)

    address = 0x30
    data = 0x77

    # --------------------------------------------------------
    # Write to main memory.
    #
    # Because your cache uses WRITE-THROUGH and
    # NO-WRITE-ALLOCATE, this updates main memory
    # but does not allocate the cache line.
    # --------------------------------------------------------

    await cpu_write(
        dut,
        address,
        data
    )

    # --------------------------------------------------------
    # First READ
    #
    # This should cause:
    #
    # CPU
    #   ↓
    # CACHE MISS
    #   ↓
    # MAIN MEMORY
    #   ↓
    # CACHE LINE ALLOCATION
    #   ↓
    # READ DATA
    # --------------------------------------------------------

    result = await cpu_read(
        dut,
        address,
        expected=data
    )

    assert result == data

    # --------------------------------------------------------
    # Second READ
    #
    # The block should now be in cache.
    # Therefore this should be a HIT.
    # --------------------------------------------------------

    result = await cpu_read(
        dut,
        address,
        expected=data
    )

    assert result == data

    print("PASS: Cache miss followed by allocation and hit")
    print("========================================\n")


# ============================================================
# TEST 6
# Different Addresses
# ============================================================

@cocotb.test()
async def test_multiple_addresses(dut):

    print("\n========================================")
    print("TEST 6: MULTIPLE ADDRESS TEST")
    print("========================================")

    cocotb.start_soon(
        Clock(dut.clk, 10, units="ns").start()
    )

    await reset_dut(dut)

    test_vectors = [
        (0x04, 0x12),
        (0x08, 0x34),
        (0x0C, 0x56),
        (0x10, 0x78),
        (0x14, 0x9A),
        (0x18, 0xBC),
    ]

    # Write
    for address, data in test_vectors:

        await cpu_write(
            dut,
            address,
            data
        )

    # Read
    for address, expected in test_vectors:

        result = await cpu_read(
            dut,
            address,
            expected=expected
        )

        assert result == expected

    print("PASS: Multiple address test")
    print("========================================\n")


# ============================================================
# TEST 7
# Cache Conflict / Replacement
# ============================================================

@cocotb.test()
async def test_cache_conflict(dut):

    print("\n========================================")
    print("TEST 7: CACHE CONFLICT / REPLACEMENT")
    print("========================================")

    cocotb.start_soon(
        Clock(dut.clk, 10, units="ns").start()
    )

    await reset_dut(dut)

    # --------------------------------------------------------
    # Address format:
    #
    # [7:6] = TAG
    # [5:2] = INDEX
    # [1:0] = OFFSET
    #
    # 0x04 = 0000 0100
    #
    # TAG   = 00
    # INDEX = 0001
    #
    # 0x44 = 0100 0100
    #
    # TAG   = 01
    # INDEX = 0001
    #
    # Therefore:
    #
    # 0x04 and 0x44 map to the SAME cache line
    # but have DIFFERENT tags.
    # --------------------------------------------------------

    address1 = 0x04
    data1 = 0xAA

    address2 = 0x44
    data2 = 0x55

    # Put first value in memory
    await cpu_write(
        dut,
        address1,
        data1
    )

    # Load address1 into cache
    await cpu_read(
        dut,
        address1,
        expected=data1
    )

    # Put second value in memory
    await cpu_write(
        dut,
        address2,
        data2
    )

    # Reading address2 should replace address1's cache line
    await cpu_read(
        dut,
        address2,
        expected=data2
    )

    # Reading address1 again should now MISS
    # and reload address1 from main memory.
    await cpu_read(
        dut,
        address1,
        expected=data1
    )

    print("PASS: Cache conflict/replacement")
    print("========================================\n")


# ============================================================
# TEST 8
# Sequential Access
# ============================================================

@cocotb.test()
async def test_sequential_access(dut):

    print("\n========================================")
    print("TEST 8: SEQUENTIAL ACCESS")
    print("========================================")

    cocotb.start_soon(
        Clock(dut.clk, 10, units="ns").start()
    )

    await reset_dut(dut)

    base_address = 0x40

    values = [
        0x10,
        0x20,
        0x30,
        0x40
    ]

    # Write four consecutive bytes
    for i, value in enumerate(values):

        await cpu_write(
            dut,
            base_address + i,
            value
        )

    # Read them back
    for i, expected in enumerate(values):

        result = await cpu_read(
            dut,
            base_address + i,
            expected=expected
        )

        assert result == expected

    print("PASS: Sequential access")
    print("========================================\n")
```

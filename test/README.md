# Cocotb testbench

This testbench uses [Cocotb](https://docs.cocotb.org/en/stable/) to exercise
the `tt_um_tpmdle` direct-mapped cache through its Tiny Tapeout pin interface.
The tests cover reset, ready/valid handshaking, cache hits and misses,
write-through behavior, aliasing, memory sweeps, and `ena` gating.

## Setting up

The RTL source is [../src/asic_fables.v](../src/asic_fables.v), and the
testbench instantiates `tt_um_tpmdle` in [tb.v](tb.v). Python dependencies
are listed in [requirements.txt](requirements.txt).

## How to run

From this directory, install the dependencies and run the RTL simulation:

```sh
python3 -m pip install -r requirements.txt
make -B
```

To run gatelevel simulation, first harden your project and copy `../runs/wokwi/results/final/verilog/gl/{your_module_name}.v` to `gate_level_netlist.v`.

Then run:

```sh
make -B GATES=yes
```

If you wish to save the waveform in VCD format instead of FST format, edit tb.v to use `$dumpfile("tb.vcd");` and then run:

```sh
make -B FST=
```

This will generate `tb.vcd` instead of `tb.fst`.

## How to view the waveform file

Using GTKWave

```sh
gtkwave tb.fst tb.gtkw
```

Using Surfer

```sh
surfer tb.fst
```

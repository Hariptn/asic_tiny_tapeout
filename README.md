![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg) ![](../../workflows/fpga/badge.svg)

# Direct-Mapped Cache with CPU Interface

This project implements a 4-line direct-mapped, write-through cache with
2-byte cache lines and an internal 16-byte main memory. It exposes a
ready/valid CPU-style interface through the Tiny Tapeout pins.

See the [project documentation](docs/info.md) for the cache organization,
pin protocol, and usage examples.

## Running the tests

The Cocotb testbench covers reset and ready signaling, reads and writes,
cache hits and misses, aliasing, write-through behavior, full-memory sweeps,
and `ena` gating. From the `test` directory, run:

```sh
make -B
```

See [test/README.md](test/README.md) for RTL and gate-level simulation details.

## What is Tiny Tapeout?

Tiny Tapeout is an educational project that aims to make it easier and cheaper than ever to get your digital and analog designs manufactured on a real chip.

To learn more and get started, visit https://tinytapeout.com.

## Project structure

- `src/asic_fables.v` contains the top-level wrapper, cache controller, and main memory.
- `docs/info.md` describes the design and pin-level protocol.
- `test/test.py` contains the Cocotb functional tests.
- `test/Makefile` defines the RTL and gate-level simulation commands.

The GitHub action will automatically build the ASIC files using [LibreLane](https://www.zerotoasiccourse.com/terminology/librelane/).

## Enable GitHub actions to build the results page

- [Enabling GitHub Pages](https://tinytapeout.com/faq/#my-github-action-is-failing-on-the-pages-part)

## Resources

- [FAQ](https://tinytapeout.com/faq/)
- [Digital design lessons](https://tinytapeout.com/digital_design/)
- [Learn how semiconductors work](https://tinytapeout.com/siliwiz/)
- [Join the community](https://tinytapeout.com/discord)
- [Build your design locally](https://www.tinytapeout.com/guides/local-hardening/)

## What next?

- [Submit your design to the next shuttle](https://app.tinytapeout.com/).
- Edit [this README](README.md) and explain your design, how it works, and how to test it.
- Share your project on your social network of choice:
  - LinkedIn [#tinytapeout](https://www.linkedin.com/search/results/content/?keywords=%23tinytapeout) [@TinyTapeout](https://www.linkedin.com/company/100708654/)
  - Mastodon [#tinytapeout](https://chaos.social/tags/tinytapeout) [@matthewvenn](https://chaos.social/@matthewvenn)
  - X (formerly Twitter) [#tinytapeout](https://twitter.com/hashtag/tinytapeout) [@tinytapeout](https://twitter.com/tinytapeout)
  - Bluesky [@tinytapeout.com](https://bsky.app/profile/tinytapeout.com)

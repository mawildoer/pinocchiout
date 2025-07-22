# `pinocchiout` - STM32 Pinout Solver

![screenshot](https://raw.githubusercontent.com/mawildoer/pinocchiout/refs/heads/main/screenshot.png)

## Installation

I recommend using [`uv`](https://docs.astral.sh/uv/getting-started/installation/) to install this project.

Then, all you need to do is run `uvx pinocchiout` and it'll handle the rest.

## Usage

### With a `reqs.yaml/json` file

`reqs.yaml/json` is a simple file describing the requirements of your project.

```yaml title="reqs.yaml"
chip: STM32G431C6
package: UFQFPN48
requirements:
  - name: position-sensor
    kind: spi
    signals:
      - MOSI
      - MISO
      - SCK

reserved_pins:
 - PB8  # boot select pin

```

This one, for example, says you're trying to find a pinout for the STM32G431C6 microcontroller, in the UFQFPN48 package, with a SPI peripheral. It also reserves the boot select pin, PB8.

YAML is preferred, because it allows for comments, but JSON is also supported:

```json title="reqs.json"
{
    "chip": "STM32G431C6",
    "package": "UFQFPN48",
    "requirements": [
        {
            "name": "spi",
            "peripheral": "spi",
            "kind": "spi",
            "signals": ["MOSI", "MISO", "SCK"]
        }
    ]
}
```

You can print out a table of the pinout like so:

```bash title="Printing the pinout"
uvx pinocchiout --reqs "examples/reqs.yaml"
```

Peripheral names ("peripheral") and signal names ("signals") are treated as regular expressions, so you can use them to match multiple.

### As a library

Honestly, it could be better, but see `example.py` for a simple example of how to use it as a library.

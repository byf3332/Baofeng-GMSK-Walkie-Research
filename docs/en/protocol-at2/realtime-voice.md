# Real-time Voice

## Mode Control

| Operation | payload |
|---|---|
| Enable off-network session | `00 02 04 07 01` |
| Disable off-network session | `00 02 04 07 00` |
| Press PTT | `00 02 04 02 01` |
| Release PTT | `00 02 04 02 00` |
| PTT status acknowledgment | `00 82 04 02` |

## Voice Encoding

| Parameter | Value |
|---|---|
| Codec | AMR-NB MR475 |
| Sample rate | 8000 Hz |
| PCM | mono PCM16LE |
| PCM frame | 320 bytes |
| Frame duration | 20 ms |
| Encoded frame | 12 bytes |

An AMR-NB MR475 IETF storage frame consists of a 1-byte ToC and a 12-byte payload. AT2 transmits only the 12-byte payload. Prepend `04` when decoding it as an IETF storage frame.

## Transmit Frames

Real-time voice uses family `02`, command `04`, and subcommand `03`.

| Type | payload | Duration |
|---|---|---:|
| Normal packet | `00 02 04 03 00 00 [60-byte voice]` | 100 ms |
| Tail packet | `00 02 04 03 00 00 [48-byte voice]` | 80 ms |

A normal packet concatenates five encoded frames and is transmitted approximately every 100 ms. A tail packet concatenates four encoded frames.

## Receive Frames

The device sends family `02`, command `04`, and subcommand `03`. Remove leading zeroes after the subcommand, then split the remaining data into 12-byte AMR-NB MR475 encoded frames.

# Clone

## Block Read

| Step | Direction | Data | Length |
| --- | --- | --- | --- |
| 1 | TX | `52` + address uint16-be + `08` | 4 bytes |
| 2 | RX | Header + payload | 12 bytes |
| 3 | TX | `06` | 1 byte |
| 4 | RX | `06` | 1 byte |

The header is `57` + address uint16-be + `08`, or the request header bytes in reverse order. The payload is 8 bytes.

## Clone Write

| Step | Direction | Data | Length |
| --- | --- | --- | --- |
| 1 | TX | `45` | 1 byte |
| 2 | RX | `46` | 1 byte |
| 3 | TX | `02 80 82 4F 47 52 41 4D` | 8 bytes |
| 4 | RX | `06` | 1 byte |
| 5 | TX | `02` | 1 byte |
| 6 | RX | `50 33 31 30 37 F7 00 00` | 8 bytes |
| 7 | TX | `06` | 1 byte |
| 8 | RX | `06` | 1 byte |

## Block Write

| Step | Direction | Data | Length |
| --- | --- | --- | --- |
| 1 | TX | `57` + address uint16-be + `08` + payload | 12 bytes |
| 2 | RX | `06` | 1 byte |

The payload is 8 bytes. Send `45` after all blocks have been written. No response is read.

## Address Sequence

| Current block | Next read block | Next write block |
| --- | --- | --- |
| `0x0108` | `0x02B0` | `0x02B0` |
| `0x02B8` | `0x0330` | `0x0380` |
| `0x0338` | `0x0380` | Skipped |

All other addresses increment by 8. The terminal address is `0x03E0`. Reads include `0x0330` and `0x0338`; writes skip both blocks.

## Image Layout

| Region | Address | Length |
| --- | --- | --- |
| Channels 1–16 | `0x0010–0x010F` | 16 bytes per channel |
| Basic settings | `0x02B0–0x02BF` | 16 bytes |
| Read blocks | `0x0330–0x033F` | 16 bytes |
| System settings | `0x03C0–0x03CF` | 16 bytes |
| Image | `0x0000–0x03DF` | `0x03E0` bytes |

## Channel Record

| Offset | Length | Field |
| --- | --- | --- |
| `0x00` | 4 | RX frequency |
| `0x04` | 4 | TX frequency |
| `0x08` | 2 | RX CTCSS / DCS |
| `0x0A` | 2 | TX CTCSS / DCS |
| `0x0C` | 1 | Flags |
| `0x0D` | 1 | Encryption key and reserved bits |
| `0x0E` | 2 | Reserved |

A record filled with `FF` is an empty channel. A TX frequency filled with `FF` disables transmission.

## Frequency

RX and TX frequencies use 4-byte little-endian packed BCD in 10 Hz units. Four `00` or four `FF` bytes decode to zero.

Example: **430.125000 MHz**

| Operation | Value |
| --- | --- |
| `430125000 Hz ÷ 10` | `43012500` |
| BCD bytes | `43 01 25 00` |
| Stored bytes | `00 25 01 43` |

## CTCSS

CTCSS uses 2-byte little-endian BCD in 0.1 Hz units. Bit 15 is zero.

Example: **123.0 Hz**

| Operation | Value |
| --- | --- |
| `123.0 × 10` | `1230` |
| BCD word | `0x1230` |
| Stored bytes | `30 12` |

## DCS

| Bit | Field |
| --- | --- |
| 15 | DCS flag, fixed at 1 |
| 14 | `0` Normal, `1` Reverse |
| 11–0 | Packed BCD for the three-digit DCS code |

Example: **DCS 023 Normal**

| Operation | Value |
| --- | --- |
| Word | `0x8000 \| 0x023 = 0x8023` |
| Stored bytes | `23 80` |

DCS 023 Reverse uses word `0xC023` and stored bytes `23 C0`. Both `00 00` and `FF FF` mean no subtone; the encoded off value is `FF FF`.

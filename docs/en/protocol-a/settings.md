# Settings

## Channel Flags

Channel flags are stored at channel record offset `0x0C`.

| Bit | Mask | `0` | `1` |
| --- | --- | --- | --- |
| 7 | `0x80` | Frequency hopping off | Frequency hopping on |
| 4 | `0x10` | Included in scan | Excluded from scan |
| 3 | `0x08` | Low power | High power |
| 2 | `0x04` | FM | NFM |
| 1 | `0x02` | Analog | Encrypted digital |
| 0 | `0x01` | Busy lock on | Busy lock off |

Bits 0–4 at channel record offset `0x0D` contain encryption key `0–31`. Bits 5–7 are reserved.

## General Settings `0x02B0`

| Absolute address | Offset | Field | Encoding |
| --- | --- | --- | --- |
| `0x02B0` | 0 | Voice prompt | `00` off, `01` on |
| `0x02B1` | 1 | Prompt language | `00` English, `01` Chinese |
| `0x02B3` | 3 | VOX | `00` off, `01` on |
| `0x02B4` | 4 | VOX gain | `01–05` |
| `0x02B6` | 6 | Low-voltage TX inhibit | `00` off, `01` on |
| `0x02B7` | 7 | High-voltage TX inhibit | `00` off, `01` on |
| `0x02B8` | 8 | Alarm | `00` off, `01` on |
| `0x02B9` | 9 | Noise reduction | `00` off, `01` on |

## System Settings `0x03C0`

| Absolute address | Offset | Field | Encoding |
| --- | --- | --- | --- |
| `0x03C0` | 0 bit 0 | Key tone | `0` off, `1` on |
| `0x03C0` | 0 bit 1 | Battery saver | `0` off, `1` on |
| `0x03C1` | 1 | Squelch | `00` always open, `01` normal, `05` enhanced, `09` strict |
| `0x03C2` | 2 | Side key | `00` off, `01` monitor, `02` power, `03` alarm |
| `0x03C3` | 3 | TOT | `00` off, `01–0A` for 30–300 seconds |

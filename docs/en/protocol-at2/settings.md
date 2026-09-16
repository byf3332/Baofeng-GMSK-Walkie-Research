# Device Settings

Queries use family `01`; settings use family `02`. Query responses use family `81`; setting acknowledgments use family `82`.

## Common Settings

| Setting | Query payload | Set payload | Value |
|---|---|---|---|
| Volume | `00 01 01 01` | `00 02 01 01 [value]` | 1–8 |
| Prompt language | `00 01 01 03` | `00 02 01 03 [value]` | `00` Chinese, `01` English |
| Prompt tone | `00 01 01 04` | `00 02 01 04 [value]` | `00` off, `01` on |
| Dual watch | `00 01 02 0D` | `00 02 02 0D [value]` | `00` off, `02` on |
| Squelch | `00 01 02 04` | `00 02 02 04 [value]` | 0–9 |
| TOT | `00 01 02 05` | `00 02 02 05 [uint16-le]` | 0–240 seconds |
| VOX | `00 01 02 06` | `00 02 02 06 [value]` | `00` off, `01` on |
| VOX sensitivity | `00 01 02 07` | `00 02 02 07 [value]` | 1–5 |
| TX inhibit | `00 01 02 09` | `00 02 02 09 [value]` | `00` off, `01` on |
| TX interval | `00 01 02 0A` | `00 02 02 0A [uint16-le]` | 0–240 seconds |
| Noise reduction | `00 01 02 11` | `00 02 02 11 [value]` | `00` off, `01` on |

## SmartLink

| Operation | payload |
|---|---|
| Query switch | `00 01 04 09` |
| Set switch | `00 02 04 09 [00/01]` |
| Query main PTT long-press mapping | `00 01 04 0A 01` |
| Set main PTT long-press mapping | `00 02 04 0A 01 [target]` |

| target | Mapping |
|---|---|
| `01` | Other1 |
| `06` | Zello |
| `08` | Other3 |
| `09` | Other4 |
| `0A` | Other2 |
| `0B` | Olaradio |

## Device Name

| Operation | payload |
|---|---|
| Set name | `00 02 03 01 [UTF-8 bytes]` |
| Setting acknowledgment | `00 82 03 01 00` |

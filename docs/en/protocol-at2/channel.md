# Channel Programming

## Channel Table

The table contains 30 channels. Each record is 24 bytes.

| Offset | Length | Field | Encoding |
|---|---:|---|---|
| `0x00` | 1 | Record marker | `01` |
| `0x01` | 1 | Channel number | 1–30 |
| `0x02` | 1 | Reserved | `00` |
| `0x03` | 4 | RX frequency | `MHz × 100000`, uint32-le |
| `0x07` | 4 | TX frequency | `MHz × 100000`, uint32-le |
| `0x0B` | 1 | RX tone index | CTCSS / DCS index; `7F` for off |
| `0x0C` | 1 | RX tone type | `00` CTCSS, `01` DCS |
| `0x0D` | 1 | TX tone index | CTCSS / DCS index; `7F` for off |
| `0x0E` | 1 | TX tone type | `00` CTCSS, `01` DCS |
| `0x0F` | 1 | RX DCS polarity | `00` Normal, `01` Inverted |
| `0x10` | 1 | TX DCS polarity | `00` Normal, `01` Inverted |
| `0x11` | 1 | Busy lock | `00` on, `01` off |
| `0x12` | 1 | Bandwidth | `00` wide, `01` narrow |
| `0x13` | 1 | Power | `00` low, `01` high |
| `0x14` | 1 | Scan list | `00` included, `01` excluded |
| `0x15` | 1 | Frequency hopping | `00` off, `01` on |
| `0x16` | 1 | Mode | `00` analog, `01` digital |
| `0x17` | 1 | Encryption key | `00` off, `01`–`1F` keys 1–31 |

An all-zero frequency field represents an empty frequency.

Example: **430.125000 MHz**

`430.125000 × 100000 = 43012500 = 0x02905C14`; the encoded field is `14 5C 90 02`.

## Read

| Operation | payload |
|---|---|
| Read 30 channel records | `00 01 02 02` |

The response uses family `81`, command `02`, and `02` as the first data byte. The remaining data contains 24-byte channel records.

## Single-channel Write

| Operation | payload |
|---|---|
| Write or clear one record | `00 02 02 02 [24-byte record]` |
| Write acknowledgment | `00 82 02 02 00` |

An empty channel retains the record marker and channel number. RX and TX frequencies are zero. RX and TX tone indices are `7F`.

## Full-table Write

Concatenate 30 records in channel-number order to form 720 bytes. Send the data in 168-byte chunks.

| Operation | payload |
|---|---|
| Write chunk | `00 02 02 02 [up to 168-byte records]` |
| Chunk acknowledgment | `00 82 02 02 00` |

Send the next chunk after receiving acknowledgment for the current chunk.

## Channel Selection

| Operation | payload |
|---|---|
| Select a single-watch channel | `00 02 02 0E 01 [channel] 00` |
| Select dual-watch channel A | `00 02 02 0E 01 [channel] 00` |
| Select dual-watch channel B | `00 02 02 0E 02 [channel] 00` |
| Select focus A | `00 02 02 0F 01` |
| Select focus B | `00 02 02 0F 02` |
| Channel switch acknowledgment | `00 82 02 0E 00` |

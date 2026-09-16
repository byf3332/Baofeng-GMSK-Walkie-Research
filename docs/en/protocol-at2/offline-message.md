# Off-network Messages

Off-network messages use family `02`, command `04`, and subcommand `01`. The message ID is a 4-byte uint32-be value. The sender field is 16-byte UTF-8 padded on the right with spaces.

## Types

| type | Content | Frame |
|---|---|---|
| `01` | Text | Start frame |
| `02` | Text | Data frame |
| `03` | Voice | Start frame |
| `04` | Voice | Data frame |
| `05` | Image | Start frame |
| `06` | Image | Data frame |

The acknowledgment payload for each business frame is `00 82 04 01 00`.

## Short Text

UTF-8 text up to 180 bytes uses one frame.

| Field | Length | Encoding |
|---|---:|---|
| Fixed header | 5 | `00 02 04 01 01` |
| Message ID | 4 | uint32-be |
| Reserved | 1 | `00` |
| Sender | 16 | UTF-8 padded on the right with `20` |
| Text length | 2 | uint16-le |
| Fragment count and sequence | 2 | `01 00` |
| Text | N | UTF-8 |

## Fragmented Text

Split text into 131-byte chunks. The start frame contains no text. Send the data frames in sequence.

| Frame | payload |
|---|---|
| Start frame | `00 02 04 01 01 [msgId be32] 00 [sender 16] [streamLength le16] [partCount] 00` |
| Data frame | `00 02 04 01 02 [msgId be32] [seq be16] 00 [up to 131-byte text]` |

`streamLength` is the sum of all fragment lengths plus one byte for each fragment.

## Voice Message

Voice uses AMR-NB MR475. Each frame covers 20 ms. BLE data retains the 12-byte MR475 payload. Split voice data into 132-byte chunks.

| Frame | payload |
|---|---|
| Start frame | `00 02 04 01 03 [msgId be32] 00 [sender 16] [dataLength le16] [partCount le16] [durationSeconds le16]` |
| Data frame | `00 02 04 01 04 [msgId be32] [seq be16] 00 [up to 132-byte voice]` |

## Image Message

Images use JPEG with a 300 px long edge and quality 75. Split image data into 132-byte chunks.

| Frame | payload |
|---|---|
| Start frame | `00 02 04 01 05 [msgId be32] 00 [sender 16] [dataLength le16] [partCount] 00 [width le16] [height le16]` |
| Data frame | `00 02 04 01 06 [msgId be32] [seq be16] 00 [up to 132-byte jpeg]` |

## Session Control

| Operation | payload |
|---|---|
| Enable off-network session | `00 02 04 07 01` |
| Disable off-network session | `00 02 04 07 00` |

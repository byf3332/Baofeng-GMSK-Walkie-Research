# Frame Format

## Structure

| Offset | Length | Field | Encoding |
|---|---:|---|---|
| `0x00` | 2 | Header | `AA 55` |
| `0x02` | 1 | Length | Bytes from family through the end of data |
| `0x03` | 1 | Leading byte | `00` |
| `0x04` | 1 | family | Command family |
| `0x05` | 1 | command | Command number |
| `0x06` | N | data | Command data |
| Variable | 2 | CRC | little-endian |
| Variable | 2 | Tail | `77 EE` |

The length field excludes the leading `00`. CRC input starts at family and ends at the last data byte.

## CRC

| Parameter | Value |
|---|---|
| Algorithm | CRC-16/CCITT-FALSE |
| Polynomial | `0x1021` |
| Init | `0x1234` |
| RefIn | false |
| RefOut | false |
| Output byte order | little-endian |

## Command Families

| family | Direction | Meaning |
|---|---|---|
| `01` | Host to device | Query |
| `02` | Host to device | Setting or data transmission |
| `81` | Device to host | Query response or status report |
| `82` | Device to host | Setting acknowledgment |

A received frame may omit the leading `00`. In that form, the length directly covers family, command, and data. The CRC input remains unchanged.

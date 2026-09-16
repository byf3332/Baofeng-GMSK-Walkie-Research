# Handshake

## Serial

The serial port uses 9600 baud and 8N1.

## Constants

| Name | Bytes |
| --- | --- |
| PROGRAM probe | `02 70 72 4F 47 52 41 4D` |
| Normal password entry | `02 75 63 62 66 70 77 70 64` |
| Normal password entry ASCII | `ucbfpwd` |
| Normal authentication handshake | `10 C5 EA 35` |
| Clone entry | `02 80 82 4F 47 52 41 4D` |
| Clone identification | `50 33 31 30 37 F7 00 00` |
| Clone probe | `52 01 30 08` |
| Clone probe response | `57 01 30 08 FF FF FF FF FF FF FF FF` |
| ACK | `06` |
| Reject | `04` |
| Exit | `45` |

## Normal Password Authentication

The password field is fixed at 16 bytes. It contains 0–16 ASCII bytes padded on the right with `00`. An empty password is 16 bytes of `00`.

| Step | Direction | Data | Length |
| --- | --- | --- | --- |
| 1 | TX | `02 70 72 4F 47 52 41 4D` | 8 bytes |
| 2 | RX | Version | 4 bytes |
| 3 | TX | `02 75 63 62 66 70 77 70 64` | 8 bytes |
| 4 | RX | `06` | 1 byte |
| 5 | TX | `10 C5 EA 35` | 4 bytes |
| 6 | RX | `06` | 1 byte |
| 7 | TX | Programming password | 16 bytes |
| 8 | RX | `06` | 1 byte |
| 9 | TX | `02 70 72 4F 47 52 41 4D` | 8 bytes |
| 10 | RX | Version | 4 bytes |

`04` indicates rejection during authentication.

## Clone Read Handshake

| Step | Direction | Data | Length |
| --- | --- | --- | --- |
| 1 | TX | `02 80 82 4F 47 52 41 4D` | 8 bytes |
| 2 | RX | `06` | 1 byte |
| 3 | TX | `02` | 1 byte |
| 4 | RX | `50 33 31 30 37 F7 00 00` | 8 bytes |
| 5 | TX | `06` | 1 byte |
| 6 | RX | `06` | 1 byte |
| 7 | TX | `52 01 30 08` | 4 bytes |
| 8 | RX | `57 01 30 08 FF FF FF FF FF FF FF FF` | 12 bytes |
| 9 | TX | `06` | 1 byte |
| 10 | RX | `06` | 1 byte |

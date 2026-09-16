# Password and Subsystem ID

## Dealer Profile

Encode the ASCII dealer code with Base64, take the first 16 bytes, then pad on the right with `00` to 16 bytes.

| Dealer code | Programming password | Name | Subsystem ID |
| --- | --- | --- | --- |
| `POFUNG` | `UE9GVU5H` | Export trial | 0 |
| `CN59500` | `Q041OTUwMA==` | Baofeng | 1 |
| `CN59501` | `Q041OTUwMQ==` | Wang Qinghong | 2 |
| `CN59502` | `Q041OTUwMg==` | Wang Xinyuan | 3 |
| `CN59503` | `Q041OTUwMw==` | Li Muwang | 4 |
| `CN59504` | `Q041OTUwNA==` | Wang Jingsong | 5 |
| `CN02801` | `Q04wMjgwMQ==` | Deng Xiaosong | 6 |
| `CN02501` | `Q04wMjUwMQ==` | Jiang Keming | 7 |
| `CN53601` | `Q041MzYwMQ==` | Zhang Lili | 8 |
| `CN93101` | `Q045MzEwMQ==` | Chen Jun | 9 |
| `CN53201` | `Q041MzIwMQ==` | Wu Duanle / Suofei | 10 |
| `CN53901` | `Q041MzkwMQ==` | LZF | 11 |

## Writing the Subsystem ID

Run this sequence after normal password authentication.

| Step | Direction | Data | Length |
| --- | --- | --- | --- |
| 1 | TX | `02 60 62 4F 41 57 52 4D` | 8 bytes |
| 2 | RX | `06` | 1 byte |
| 3 | TX | `20` | 1 byte |
| 4 | RX | `06` | 1 byte |
| 5 | TX | `67 00 00 04` + subsystem ID uint32-be | 8 bytes |
| 6 | RX | `06` | 1 byte |
| 7 | TX | `45` | 1 byte |
| 8 | RX | `06` | 1 byte |

The subsystem ID is stored as the low 8 bits with a range of `0–255`. Writing `256` produces `0`; writing `999` produces `231`.

## Changing the Password and Subsystem ID

| Name | Value |
| --- | --- |
| Super-administrator entry | `02 75 63 66 62 77 70 64` |
| Super-administrator entry ASCII | `ucfbwpd` |
| Change operation | `20 EA AB 5C` |
| Super-administrator password | `admin#jzssjb1` |
| Configuration entry | `02 60 62 4F 41 57 52 4D` |
| Configuration confirmation | `20` |
| Subsystem ID command | `67 00 00 04` + uint32-be |

| Step | Direction | Data | Length |
| --- | --- | --- | --- |
| 1 | TX | `02 70 72 4F 47 52 41 4D` | 8 bytes |
| 2 | RX | Version | 4 bytes |
| 3 | TX | `02 75 63 66 62 77 70 64` | 8 bytes |
| 4 | RX | `06` | 1 byte |
| 5 | TX | `20 EA AB 5C` | 4 bytes |
| 6 | RX | `06` | 1 byte |
| 7 | TX | `61 64 6D 69 6E 23 6A 7A 73 73 6A 62 31 00 00 00` | 16 bytes |
| 8 | RX | `06` | 1 byte |
| 9 | TX | New programming password | 16 bytes |
| 10 | RX | `06` | 1 byte |
| 11 | TX | `02 60 62 4F 41 57 52 4D` | 8 bytes |
| 12 | RX | `06` | 1 byte |
| 13 | TX | `20` | 1 byte |
| 14 | RX | `06` | 1 byte |
| 15 | TX | `67 00 00 04` + subsystem ID uint32-be | 8 bytes |
| 16 | RX | `06` | 1 byte |
| 17 | TX | `45` | 1 byte |
| 18 | RX | `06` | 1 byte |

## Subsystem ID Voice Query

With the radio powered off, turn the channel selector to 3. Hold PTT and side key 1 while powering on. The voice prompt has the form `X power on (encrypted) 3`, where `X` is the decimal subsystem ID.

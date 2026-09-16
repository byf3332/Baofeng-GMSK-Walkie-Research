# 读写频

## Block read

| 序号 | 方向 | 数据 | 长度 |
| --- | --- | --- | --- |
| 1 | TX | `52` + address uint16-be + `08` | 4 bytes |
| 2 | RX | Header + payload | 12 bytes |
| 3 | TX | `06` | 1 byte |
| 4 | RX | `06` | 1 byte |

Header 为 `57` + address uint16-be + `08`，或请求头的逆序字节序列。Payload 为 8 bytes。

## Clone Write

| 序号 | 方向 | 数据 | 长度 |
| --- | --- | --- | --- |
| 1 | TX | `45` | 1 byte |
| 2 | RX | `46` | 1 byte |
| 3 | TX | `02 80 82 4F 47 52 41 4D` | 8 bytes |
| 4 | RX | `06` | 1 byte |
| 5 | TX | `02` | 1 byte |
| 6 | RX | `50 33 31 30 37 F7 00 00` | 8 bytes |
| 7 | TX | `06` | 1 byte |
| 8 | RX | `06` | 1 byte |

## Block write

| 序号 | 方向 | 数据 | 长度 |
| --- | --- | --- | --- |
| 1 | TX | `57` + address uint16-be + `08` + payload | 12 bytes |
| 2 | RX | `06` | 1 byte |

Payload 为 8 bytes。全部 block 写入后发送 `45`，无需读取响应。

## 地址序列

| 当前 block | Read 下一 block | Write 下一 block |
| --- | --- | --- |
| `0x0108` | `0x02B0` | `0x02B0` |
| `0x02B8` | `0x0330` | `0x0380` |
| `0x0338` | `0x0380` | 不进入该地址 |

其余地址递增 8，终止地址为 `0x03E0`。Read 读取 `0x0330` 和 `0x0338`，Write 跳过这两个 block。

## 镜像布局

| 区域 | 地址 | 长度 |
| --- | --- | --- |
| 信道 1–16 | `0x0010–0x010F` | 16 bytes / 信道 |
| 基础配置 | `0x02B0–0x02BF` | 16 bytes |
| 读取 block | `0x0330–0x033F` | 16 bytes |
| 系统设置 | `0x03C0–0x03CF` | 16 bytes |
| 镜像 | `0x0000–0x03DF` | `0x03E0` bytes |

## 信道记录

| 偏移 | 长度 | 字段 |
| --- | --- | --- |
| `0x00` | 4 | RX 频率 |
| `0x04` | 4 | TX 频率 |
| `0x08` | 2 | RX CTCSS / DCS |
| `0x0A` | 2 | TX CTCSS / DCS |
| `0x0C` | 1 | Flags |
| `0x0D` | 1 | 加密密钥和保留位 |
| `0x0E` | 2 | 保留 |

16 bytes 全 `FF` 表示空信道。TX 频率全 `FF` 表示禁止发射。

## 频率

RX 和 TX 频率使用 4-byte little-endian packed BCD，单位为 10 Hz。四字节全 `00` 或全 `FF` 解码为 0。

例如：**430.125000 MHz**

| 运算 | 值 |
| --- | --- |
| `430125000 Hz ÷ 10` | `43012500` |
| BCD bytes | `43 01 25 00` |
| Stored bytes | `00 25 01 43` |

## CTCSS

CTCSS 使用 2-byte little-endian BCD，单位为 0.1 Hz，bit 15 为 0。

例如：**123.0 Hz**

| 运算 | 值 |
| --- | --- |
| `123.0 × 10` | `1230` |
| BCD word | `0x1230` |
| Stored bytes | `30 12` |

## DCS

| Bit | 字段 |
| --- | --- |
| 15 | DCS 标志，固定为 1 |
| 14 | `0` Normal，`1` Reverse |
| 11–0 | 三位 DCS 十进制码的 BCD |

例如：**DCS 023 Normal**

| 运算 | 值 |
| --- | --- |
| Word | `0x8000 \| 0x023 = 0x8023` |
| Stored bytes | `23 80` |

DCS 023 Reverse 的 word 为 `0xC023`，存储为 `23 C0`。`00 00` 和 `FF FF` 均表示关闭亚音，写入关闭值使用 `FF FF`。

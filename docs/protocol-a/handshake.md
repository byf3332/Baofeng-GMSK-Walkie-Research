# 握手

## 串口

串口使用 9600 baud、8N1。

## 常量

| 名称 | 字节 |
| --- | --- |
| PROGRAM probe | `02 70 72 4F 47 52 41 4D` |
| 普通密码入口 | `02 75 63 62 66 70 77 70 64` |
| 普通密码入口 ASCII | `ucbfpwd` |
| 普通认证握手 | `10 C5 EA 35` |
| Clone 入口 | `02 80 82 4F 47 52 41 4D` |
| Clone identification | `50 33 31 30 37 F7 00 00` |
| Clone probe | `52 01 30 08` |
| Clone probe response | `57 01 30 08 FF FF FF FF FF FF FF FF` |
| ACK | `06` |
| Reject | `04` |
| Exit | `45` |

## 普通密码认证

密码字段固定为 16 bytes，内容为 0–16 bytes ASCII，右侧补 `00`。空密码为 16 bytes `00`。

| 序号 | 方向 | 数据 | 长度 |
| --- | --- | --- | --- |
| 1 | TX | `02 70 72 4F 47 52 41 4D` | 8 bytes |
| 2 | RX | Version | 4 bytes |
| 3 | TX | `02 75 63 62 66 70 77 70 64` | 8 bytes |
| 4 | RX | `06` | 1 byte |
| 5 | TX | `10 C5 EA 35` | 4 bytes |
| 6 | RX | `06` | 1 byte |
| 7 | TX | 读写频密码 | 16 bytes |
| 8 | RX | `06` | 1 byte |
| 9 | TX | `02 70 72 4F 47 52 41 4D` | 8 bytes |
| 10 | RX | Version | 4 bytes |

认证阶段返回 `04` 表示拒绝。

## Clone Read 握手

| 序号 | 方向 | 数据 | 长度 |
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


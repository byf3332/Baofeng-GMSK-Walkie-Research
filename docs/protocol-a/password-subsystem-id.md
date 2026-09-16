# 密码与子网 ID

## Dealer profile

Dealer code 的 ASCII bytes 经过 Base64 编码，取前 16 bytes 后右侧补 `00` 到 16 bytes。

| Dealer code | 读写频密码 | 名称 | subsystem ID |
| --- | --- | --- | --- |
| `POFUNG` | `UE9GVU5H` | 外贸体验版 | 0 |
| `CN59500` | `Q041OTUwMA==` | 宝锋 | 1 |
| `CN59501` | `Q041OTUwMQ==` | 王青红 | 2 |
| `CN59502` | `Q041OTUwMg==` | 王鑫源 | 3 |
| `CN59503` | `Q041OTUwMw==` | 李木旺 | 4 |
| `CN59504` | `Q041OTUwNA==` | 王景松 | 5 |
| `CN02801` | `Q04wMjgwMQ==` | 邓小松 | 6 |
| `CN02501` | `Q04wMjUwMQ==` | 姜克明 | 7 |
| `CN53601` | `Q041MzYwMQ==` | 张丽丽 | 8 |
| `CN93101` | `Q045MzEwMQ==` | 陈军 | 9 |
| `CN53201` | `Q041MzIwMQ==` | 吴端乐 / Suofei | 10 |
| `CN53901` | `Q041MzkwMQ==` | LZF | 11 |

## subsystem ID 写入

普通密码认证完成后执行以下序列。

| 序号 | 方向 | 数据 | 长度 |
| --- | --- | --- | --- |
| 1 | TX | `02 60 62 4F 41 57 52 4D` | 8 bytes |
| 2 | RX | `06` | 1 byte |
| 3 | TX | `20` | 1 byte |
| 4 | RX | `06` | 1 byte |
| 5 | TX | `67 00 00 04` + subsystem ID uint32-be | 8 bytes |
| 6 | RX | `06` | 1 byte |
| 7 | TX | `45` | 1 byte |
| 8 | RX | `06` | 1 byte |

subsystem ID 按低 8 bits 保存，取值范围为 `0–255`。写入 `256` 得到 `0`，写入 `999` 得到 `231`。

## 密码与 subsystem ID 修改

| 名称 | 值 |
| --- | --- |
| 超级管理员入口 | `02 75 63 66 62 77 70 64` |
| 超级管理员入口 ASCII | `ucfbwpd` |
| 修改操作 | `20 EA AB 5C` |
| 超级管理员密码 | `admin#jzssjb1` |
| 配置入口 | `02 60 62 4F 41 57 52 4D` |
| 配置确认 | `20` |
| subsystem ID 命令 | `67 00 00 04` + uint32-be |

| 序号 | 方向 | 数据 | 长度 |
| --- | --- | --- | --- |
| 1 | TX | `02 70 72 4F 47 52 41 4D` | 8 bytes |
| 2 | RX | Version | 4 bytes |
| 3 | TX | `02 75 63 66 62 77 70 64` | 8 bytes |
| 4 | RX | `06` | 1 byte |
| 5 | TX | `20 EA AB 5C` | 4 bytes |
| 6 | RX | `06` | 1 byte |
| 7 | TX | `61 64 6D 69 6E 23 6A 7A 73 73 6A 62 31 00 00 00` | 16 bytes |
| 8 | RX | `06` | 1 byte |
| 9 | TX | 新读写频密码 | 16 bytes |
| 10 | RX | `06` | 1 byte |
| 11 | TX | `02 60 62 4F 41 57 52 4D` | 8 bytes |
| 12 | RX | `06` | 1 byte |
| 13 | TX | `20` | 1 byte |
| 14 | RX | `06` | 1 byte |
| 15 | TX | `67 00 00 04` + subsystem ID uint32-be | 8 bytes |
| 16 | RX | `06` | 1 byte |
| 17 | TX | `45` | 1 byte |
| 18 | RX | `06` | 1 byte |

## subsystem ID 语音查询

关机状态下将信道旋钮转到 3，按住 PTT 和侧键 1 开机。语音播报格式为 `X 开机（加密）3`，`X` 为十进制 subsystem ID。


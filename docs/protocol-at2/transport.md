# BLE 传输

## GATT

| 项目 | UUID | 属性 |
|---|---|---|
| Service | `0000AE60-0000-1000-8000-00805F9B34FB` | Primary Service |
| TX | `0000AE10-0000-1000-8000-00805F9B34FB` | Write / Write Without Response |
| RX | `0000AE05-0000-1000-8000-00805F9B34FB` | Indicate / Notify |
| CCCD | `00002902-0000-1000-8000-00805F9B34FB` | `0002` 启用 Indicate，`0001` 启用 Notify |

连接后请求 MTU 247，完成服务发现，再启用 RX 特征的 CCCD。协议帧写入 TX 特征，设备响应由 RX 特征返回。

## 写入顺序

每次 GATT 写入完成后再发送下一帧。协议帧长度不得超过当前 ATT payload 上限。

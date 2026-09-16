# BLE Transport

## GATT

| Item | UUID | Property |
|---|---|---|
| Service | `0000AE60-0000-1000-8000-00805F9B34FB` | Primary Service |
| TX | `0000AE10-0000-1000-8000-00805F9B34FB` | Write / Write Without Response |
| RX | `0000AE05-0000-1000-8000-00805F9B34FB` | Indicate / Notify |
| CCCD | `00002902-0000-1000-8000-00805F9B34FB` | `0002` enables Indicate; `0001` enables Notify |

After connecting, request MTU 247, complete service discovery, and enable the RX characteristic CCCD. Write protocol frames to the TX characteristic. Device responses arrive on the RX characteristic.

## Write Order

Send the next frame after the current GATT write completes. A protocol frame must fit within the current ATT payload limit.

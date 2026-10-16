# WOOW Serial（WOOW 串口）

[English](README.en.md)

把 RS485／RS232 設備變成 Home Assistant 的原生裝置：在側邊欄面板監看線路上的訊框、學起來、組成裝置和實體，牆面按鍵也能直接觸發自動化。不需要寫 YAML。

管理面板的做法參考 [HAIR](https://github.com/DAB-LABS/HAIR)（Home Assistant 紅外線管理面板）。

## 功能

- **埠**
  - 本機串口：Raspberry Pi 上的 RS485（SC16IS752，`/dev/ttySC*`）和 RS232（`/dev/ttyAMA0`）。
  - 外接設備：綁定其他整合提供的串口，例如渥屋 HA-WF485-V3（ESPHome）。選了裝置就會自動帶入要用的實體。
- **監看**：
  - 自動收集每個埠收到的訊框，依標頭／位址分組並計數。
  - 自動辨識 9 種校驗碼（CRC16/Modbus、CRC16/CCITT、SUM8、XOR8 等）。
  - 可以命名、隱藏，或直接「加到裝置」「做成按鍵」。
- **裝置**：
  - 把指令組成窗簾、燈光、開關、影音設備、選擇器，自動產生 cover／light／switch／media_player／select 實體，每個指令另有一個按鈕。
  - 解析設備的回覆來更新狀態，也可以讀出感測數值、定時輪詢。
- **按鍵面板**：
  - 牆面按鍵（或任何會主動送訊框的輸入設備）的每個鍵都可以觸發自動化。在自動化編輯器裡直接選「裝置 → 按下某鍵」，按鍵改名也不會讓舊的自動化失效。
  - 每個鍵也能直接綁定去控制另一個裝置，不必寫自動化。
- **發送紀錄**：
  - 記錄 HA 送出的每一筆，以及是誰送的（服務、實體、面板、裝置），還有對方有沒有回覆、回覆花了幾毫秒。
  - 同一條線上的其他埠如果也收到，就證明真的送上了線。這種回音不會進監看，也不會觸發按鍵。
- **內建範本庫**：杜亞、A-OK 窗簾馬達，Waveshare Modbus 繼電器，XY-MD02 溫濕度，Epson、BenQ 投影機，Denon／Marantz 擴大機，Extron 和「1V2.」HDMI 矩陣。每個範本送出的訊框都和原廠文件的範例逐位元組比對過。也可以放自己的範本。
- **給 AI agent 操作**：面板能做的事都有對應的 Home Assistant 服務（附回應資料），可以用 [ha-mcp](https://github.com/homeassistant-ai/ha-mcp) 或 Home Assistant 內建的 MCP 伺服器操作。AI 做的每個變更都記在面板的「活動」分頁，連同它說明的原因。
- **服務與事件**：`woow_serial.send` 可以送出 HEX 或文字並等回覆；`woow_serial_frame` 和 `woow_serial_button` 事件可以當自動化觸發條件。
- 介面有繁體中文和英文。不需要安裝任何額外 Python 套件。

## 需求

- Home Assistant 2026.10 以上（HAOS 或容器版都可以）。
- 本機串口要讓 Home Assistant 看得到裝置檔（HAOS 的 Raspberry Pi 5 可直接使用）。
- 外接設備：任何能用「text 實體送出、sensor 實體顯示收到的資料」的整合。HA-WF485-V3 會自動辨識。

CAN 匯流排請改用另一個套件 [WOOW CAN](https://github.com/WOOWTECH/Woow_ha_can)。

## 安裝

**HACS（建議）**
1. HACS → 右上角選單 → 自訂存放庫 → 填入 `https://github.com/WOOWTECH/Woow_ha_serial`，類別選「整合」。
2. 搜尋「WOOW Serial」並下載。
3. 重新啟動 Home Assistant。

**手動**：把 `custom_components/woow_serial` 複製到 Home Assistant 的 `custom_components/`，然後重新啟動。

## 設定

到「設定 → 裝置與服務 → 新增整合 → WOOW Serial」，可以選擇：

| 選項 | 用途 |
|---|---|
| 本機串口 | 選擇 `/dev/ttySC0` 等埠，設定鮑率、資料位元、同位、停止位元。RS485 預設會濾掉自己送出的回音 |
| 外接設備 | 選擇設備，例如 HA-WF485-V3，發送和接收實體會自動帶入；其他整合可以自己選實體 |
| 管理面板 | 第一次安裝時會自動建立，側邊欄會出現「WOOW 串口」 |

每個埠事後都可以在「設定」修改，改完自動重新載入。

## 管理面板

| 分頁 | 內容 |
|---|---|
| 總覽 | 各埠狀態和收發筆數、手動發送（可自動附加校驗碼、等回覆）、即時資料 |
| 裝置 | 裝置與按鍵面板，以及它們的編輯器 |
| 監看 | 收到的訊框，依來源分組 |
| 發送紀錄 | 送出的訊框、來源、回覆、有沒有被其他埠收到 |
| 活動 | 誰改了什麼、送了什麼：AI 和腳本（透過服務）、面板上的人、實體操作，以及附上的原因 |

### 建立裝置的流程

已知型號直接在「裝置」分頁按「從範本新增」，選範本、埠，填位址就好。其他設備：

1. 在設備的原廠遙控器或面板上操作一次，訊框會出現在「監看」。
2. 按該筆的「加到裝置」：選一個裝置，或新增一個。
3. 在編輯器裡：
   - 選擇裝置類型。
   - 把功能對應到指令，例如「打開」對應到「開」。
   - 需要的話，加上狀態回讀規則。
4. 儲存後實體就會出現，可以放進儀表板，也可以在自動化裡使用。

### 指令範本

指令照協議表的寫法打，用大括號代入數值：

| 寫法 | 意思 |
|---|---|
| `55 01 02 03 01` | 固定的 HEX。可加空格、逗號，也可寫 `0x55` |
| `{addr}` | 裝置參數。HEX 指令填 HEX（例如設備位址），文字指令填文字（例如輸出編號 `2`） |
| `{value:u8}` | 數值。型別有 `u8 s8 u16 u16le s16 s16le u24 u32 u32le s32 s32le bcd bcd2` |
| `{crc16_modbus}` | 校驗碼，算前面所有位元組。`{sum8@1}` 表示從第 2 個位元組開始算 |
| `PWR ON\r` | 文字格式。可用 `\r \n \t \xHH`，數值寫成 `{value:03d}` |

`{value}` 的數值來自實體，例如亮度、位置、音量，會依「數值範圍」換算成設備的數字，例如音量 0～60，或是反向的 100～0。

每個指令還可以設定：
- **重複**和間隔：同一筆送幾次。
- **等待回覆**：設備會回答的指令（Modbus、多數 RS485 馬達、RS232 影音設備）都請設定。送出後會佔住這個埠，等到回答（或時間到）才送下一筆，避免下一筆在半雙工的 RS485 線上和回答撞在一起。內建範本都已設好。
- **接著送**：送完隔一段時間再送另一個指令，通常是查詢。很多設備對設定指令只回確認（例如 Epson 只回 `:`），接著查詢才知道真正的狀態。

可用的校驗碼：`crc16_modbus`、`crc16_ccitt`、`crc16_xmodem`、`sum16`、`crc8`、`crc8_maxim`、`xor8`、`sum8`、`sum8_neg`。

### 接收樣式（狀態回讀、感測器、按鍵）

| 寫法 | 意思 |
|---|---|
| `??` | 任一位元組 |
| `{pos:u8}` | 讀出一個數字，名稱叫 `pos` |
| `{addr}` | 要和裝置參數相符 |
| `{crc16_modbus}` | 校驗碼要正確，不正確的訊框不算 |
| `*` | 放在最後，表示後面的位元組都不管 |
| `^PWR=(?P<p>\d+)` | 文字格式：正規表示式，用具名群組讀出數值 |

例如杜亞窗簾回報位置 `55 {addr} 01 01 {pos:u8} {crc16_modbus}`，狀態選「位置」、值填 `{pos}`。編輯器裡的「試比對」會拿監看中的訊框測試樣式。

- 文字樣式裡的 `{參數名}` 會換成裝置參數，例如 Extron 矩陣的 `Out0*{output} In0*3 All`。
- **只認這個指令的回覆**：Modbus 的回覆不會寫是哪個暫存器，同一塊繼電器板的每一路要只採用自己那次讀取的回覆，就在規則或感測器選這個選項。
- 讀回的位置或亮度超出裝置的數值範圍時會忽略。例如杜亞馬達沒設行程時回報 `FF`，不會被當成全開。音量超出範圍則當作最大或最小。

### 按鍵面板

1. 新增裝置，類型選「按鍵面板」，或在監看的訊框上按「做成按鍵」。
2. 每個按鍵按「聆聽」，再按一下實體按鍵，樣式就自動填好。
3. 在自動化編輯器選「裝置 → 這個面板」，觸發條件會列出每個按鍵：「『情境 1』按下」。
4. 想讓按鍵直接控制，就在「同時執行」選裝置和動作，例如切換開／關、打開窗簾、選訊源。

同一個鍵在 300 毫秒內重複送出的訊框只算一次（可調），所以長按大約每秒觸發 3 次。如果綁定在 5 秒內被觸發超過 10 次，會自動暫停 60 秒並寫入紀錄，避免迴圈。

## 服務與事件

```yaml
# 送出並等回覆
action: woow_serial.send
data:
  config_entry_id: <埠，在介面用下拉選單選>
  hex: "01 03 00 00 00 02 C4 0B"
  wait_ms: 1000
response_variable: r   # r.reply.hex、r.timeout
```

```yaml
# 收到特定資料就觸發
triggers:
  - trigger: event
    event_type: woow_serial_frame
    event_data:
      name: RS485-1
      hex: "A5 5A 01"
```

```yaml
# 線上還有別的設備在輪詢時，只等符合樣式的那筆回覆
action: woow_serial.send
data:
  port: RS485-1
  hex: "04 04 00 01 00 02 20 5E"
  expect: "04 04 04 {t:s16} {h:u16} {crc16_modbus}"
  wait_ms: 2000
response_variable: r   # r.reply.captures.t = -55（溫度 -5.5 °C）
```

`woow_serial_button` 事件的資料：`keypad`、`button`、`button_id`、`hex`，以及樣式讀出的數值。

## 內建範本

| 範本 | 類型 | 埠設定 | 參數 |
|---|---|---|---|
| 杜亞窗簾馬達（RS485，協議 A4） | 窗簾 | 9600 8N1 | `addr`，出廠 `FE FE` |
| A-OK 奧科窗簾馬達（RS485） | 窗簾（位置方向相反，已換算） | 2400 8N1 | `id`、`ch`（通道遮罩） |
| Waveshare Modbus RTU 繼電器（單路） | 開關（每一路一個裝置） | 9600 8N1 | `addr`、`coil`（`00 00`～`00 07`） |
| XY-MD02 溫濕度感測器 | 感測器 | 9600 8N1 | `addr` |
| Epson 投影機（ESC/VP21） | 影音設備 | 9600 8N1 | — |
| BenQ 投影機 | 影音設備 | 依選單設定，TK860 是 115200 | — |
| Denon／Marantz 擴大機 | 影音設備 | 9600 8N1 | — |
| Extron 矩陣切換器的一個輸出（SIS） | 選擇器 | 9600 8N1 | `output` |
| HDMI 矩陣的一個輸出（「1V2.」協定） | 選擇器 | 9600 8N1 | `output` |

每個範本都附原廠文件出處和現場注意事項（例如位址衝突、鮑率、方向）。自己的範本放在 `<設定資料夾>/woow_serial/templates/*.json`，格式和內建的相同；同一個 id 會蓋過內建的。

## 給 AI agent 用

AI 不需要確認就能操作，所有變更都記在「活動」分頁。給 AI 的完整說明在 [`llms.txt`](llms.txt)，重點：

- **連線方式**
  - [ha-mcp](https://github.com/homeassistant-ai/ha-mcp)：用 `ha_call_service` 呼叫 `woow_serial.*`，記得帶 `return_response: true`。
  - Home Assistant 內建的 MCP 伺服器（限 admin）：服務也是 LLM API「WOOW Serial」的工具。開放全部 LLM API 時，工具名稱是 `woow-serial__<服務>`；也可以單獨連 `/api/mcp/woow_serial`。
- **流程**：先 `describe`，再 `list_ports`。已知型號用 `list_templates`、`create_from_template`；其他設備用 `get_monitor`、`listen` 或 `learn_command`／`learn_button` 學，再用 `save_device` 存。操作用實體服務或 `run_command`，確認用 `get_device`、`get_send_log`、`get_activity`。
- **埠、裝置、指令都可以用名稱**，不必記 ID。存檔失敗會回傳帶代碼的錯誤，讓 AI 修正後重送。
- **權限**：改設定的服務（存裝置、刪裝置、學習、從範本建立）需要 admin 使用者；操作設備不需要。
- 每個變更都請附 `note`，用一句話說明原因，會顯示在活動紀錄裡。

## 注意事項

- 一個埠同一時間只能給一個程式用：開埠時設為獨佔。
- 分段間隔決定怎麼把連續的位元組切成一筆。自動值是 24 個字元時間、至少 20 ms。設備自己切段比較慢時，在埠設定調大，例如 HA-WF485-V3 要 100 ms。
- 外接設備是透過 sensor 實體接收的：同一筆資料連續出現兩次時，中間要回到閒置值（例如 IDLE）才看得到第二次。HA-WF485-V3 就是這樣運作的：它會把間隔不到約 0.1 秒的兩筆併成一筆，同樣的內容要隔約 0.35 秒（回到 IDLE 之後）才看得到第二次。
- 黏在一起的訊框會自動切開：收到的一筆如果整筆對不上任何樣式，但剛好可以完全切成幾段已知的訊框（這個埠上裝置的 HEX 樣式，以及我們剛送出、設備原樣回送的訊框），就會一段一段處理。例如按鍵面板連送兩次、或按鍵和輪詢回覆被 WF485 併在一起。有任何認不得的位元組就不切，避免憑空多出按鍵。
- 外接埠等回覆時會自動多等 0.5 秒，因為回覆要經過其他整合才到得了 Home Assistant。
- RS485 是半雙工：會主動送訊框的設備（例如牆面按鍵）可能和輪詢撞在一起。輪詢間隔不要設得太密。

## 開發

```bash
cd frontend && npm install && npm run build   # 面板（Lit + TypeScript + rollup），輸出到 custom_components/woow_serial/frontend/
pip install homeassistant==2026.10.1 pytest && pytest tests   # 單元測試
```

- `tests/test_templates.py`：每個內建範本送出的訊框都和原廠文件的範例逐位元組比對。
- `tests/test_sim_bus.py`：虛擬匯流排。範本驅動依原廠文件獨立寫成的模擬設備（`tools/sim/protocols.py`），兩邊互相驗證，不需要硬體，CI 也會跑。
- `tools/sim/matrix.py`：實機測試矩陣，在兩組 RS485／RS232 迴路上輪流讓本機埠和 HA-WF485-V3 當控制端，另一端跑模擬設備。全程用 AI 會用的服務操作。
- `tools/` 其他的是在實機上用的檢查和實測腳本。

## 授權

MIT。管理面板的做法參考 DAB-LABS 的 [HAIR](https://github.com/DAB-LABS/HAIR)（MIT）。

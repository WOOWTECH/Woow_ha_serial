"""Constants for WOOW Serial."""

DOMAIN = "woow_serial"

CONF_KIND = "kind"
CONF_PORT = "port"
KIND_SERIAL = "serial"  # an on-board UART (RS485 / RS232)
KIND_EXTERNAL = "external"  # a port another integration provides, e.g. an HA-WF485-V3 over ESPHome
KIND_HUB = "hub"  # the admin layer: panel, monitor, send log, managed devices (one per Home Assistant)

# Serial options
CONF_BAUDRATE = "baudrate"
CONF_BYTESIZE = "bytesize"
CONF_PARITY = "parity"
CONF_STOPBITS = "stopbits"
CONF_FRAME_GAP = "frame_gap_ms"
CONF_ECHO_FILTER = "echo_filter"
CONF_LOOP_FLUSH = "loop_flush"
CONF_LINE_ENDING = "line_ending"

# External port binding (options of a KIND_EXTERNAL entry)
CONF_DEVICE_ID = "device_id"
CONF_TX_ENTITY = "tx_entity"
CONF_TX_FORMAT = "tx_format"
CONF_RX_ENTITY = "rx_entity"
CONF_RX_FORMAT = "rx_format"
CONF_IDLE_VALUES = "idle_values"
CONF_TX_ECHO_ENTITY = "tx_echo_entity"
CONF_SETTINGS_ENTITY = "settings_entity"
CONF_STATUS_ENTITY = "status_entity"

BAUDRATES = [1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]
LINE_ENDINGS = {"none": b"", "cr": b"\r", "lf": b"\n", "crlf": b"\r\n"}
TX_FORMATS = ["hex_space", "hex", "text"]
RX_FORMATS = ["hex", "text"]

SERIAL_DEFAULTS = {
    CONF_BAUDRATE: 9600,
    CONF_BYTESIZE: 8,
    CONF_PARITY: "N",
    CONF_STOPBITS: 1,
    CONF_FRAME_GAP: 0,
    CONF_ECHO_FILTER: False,
    CONF_LOOP_FLUSH: False,
    CONF_LINE_ENDING: "none",
}
EXTERNAL_DEFAULTS = {
    CONF_TX_FORMAT: "hex_space",
    CONF_RX_FORMAT: "hex",
    CONF_IDLE_VALUES: "IDLE",
    CONF_LINE_ENDING: "none",
}
# Entity id endings of an HA-WF485-V3 (ESPHome firmware), used to fill a binding in from the device.
WF485_ENTITIES = {
    CONF_TX_ENTITY: ("text", "_hex_data_tx"),
    CONF_RX_ENTITY: ("sensor", "_uart_net_hex"),
    CONF_TX_ECHO_ENTITY: ("sensor", "_net_uart_hex"),
    CONF_SETTINGS_ENTITY: ("sensor", "_uart_settings"),
    CONF_STATUS_ENTITY: ("binary_sensor", "_device_status"),
}

# Fired on the HA event bus for every received frame (handy as an automation trigger).
EVENT_FRAME = f"{DOMAIN}_frame"
# Fired when a keypad button is pressed; the device triggers listen to it.
EVENT_BUTTON = f"{DOMAIN}_button"

SERVICE_SEND = "send"
ATTR_ENTRY = "config_entry_id"

MAX_FRAME = 1024  # bytes; a longer burst without a gap is cut into several frames

# Admin panel
PANEL_URL = "woow-serial"
PANEL_ICON = "mdi:serial-port"
PANEL_ELEMENT = "woow-serial-panel"
PANEL_FILE = "woow-serial-panel.js"
PANEL_STATIC = "/woow_serial_static"

# Monitor and send log
CATALOG_PREFIX = 2  # frames are grouped by their first bytes (protocol header / address)
CATALOG_GROUP_ROWS = 200  # distinct frames kept per group; the least recently heard go first
CATALOG_TOTAL_ROWS = 5000
MIRROR_ROWS = 500
REPLY_WINDOW = 0.5  # s: the first frame on the same port this soon after a send is its reply
REPLY_WINDOW_EXTERNAL = 1.5  # external ports report through their integration, which adds latency
EXTERNAL_LATENCY = 0.5  # s added to a wait on an external port: the answer reaches HA that much later
HEARD_WINDOW = 1.5  # s: our own bytes heard on another port this soon are an echo, not news
LIVE_PUSH = 0.3  # s between pushes to the panel
LIVE_MAX = 200  # frames per push; the rest are only counted

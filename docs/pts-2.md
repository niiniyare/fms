# PTS-2 Forecourt Controller — API & Integration Guide

**Source:** Technotrade LLC Technical Guide R11 (Oct 2024) + Commercial Correspondence (Mar 2026)
**Hardware:** PTS-2 / PTS-2 PRO
**Guide Version:** 2.0.0
**Status:** Reference — read alongside the ERPNext FMS Implementation Guide

---

## Section 0 — Document Map

This guide and the **ERPNext FMS Implementation Guide** are companion documents.
They divide responsibility at a clean boundary:

```
┌─────────────────────────────────────────────────────────────────┐
│          THIS GUIDE — PTS-2 API & Integration Guide             │
│                                                                 │
│  • PTS-2 hardware, ports, DIP-switch, WFC wireless              │
│  • jsonPTS protocol: HTTP push payloads, WebSocket commands     │
│  • SD card CSV file schemas                                     │
│  • SDK setup, language samples (JS / C# / C++ / Java / Python) │
│  • Device configuration reference                               │
│  • Security, diagnostics, firmware                              │
│  • Procurement and pre-deployment planning                      │
└─────────────────────────────────────────────────────────────────┘
                              ↕  cross-references both ways
┌─────────────────────────────────────────────────────────────────┐
│          FMS GUIDE — ERPNext FMS Implementation Guide           │
│                                                                 │
│  • Frappe receiver code (fms/api/pts2.py)                       │
│  • WebSocket back-commands (fms/api/pts2_commands.py)           │
│  • Pump Configuration, PTS2 Device doctypes                     │
│  • Shift, Meter Reading, Tank Dip, Cashier Session doctypes     │
│  • GL journal posting at shift close                            │
│  • Wetstock reconciliation engine                               │
│  • Reporting, dashboards, workspaces                            │
└─────────────────────────────────────────────────────────────────┘
```

**What is deliberately excluded from both guides:**
- KRA eTIMS invoice submission — belongs in a dedicated compliance Frappe app
- MPesa payment gateway integration — belongs in a dedicated payments Frappe app

**Cross-reference notation used throughout:**
`→ FMS §11.3` means "see ERPNext FMS Implementation Guide, Section 11.3"

---

## Section 1 — Quick Start

Get from unboxed hardware to receiving your first pump transaction in under 15 minutes.

### 1.1 Prerequisites

- PTS-2 BOX-001 or SDK-001 powered on (12V DC, 2–5A adapter)
- microSD Class 10 formatted FAT32 inserted
- CR2032 battery installed (for RTC — without it timestamps are wrong)
- Your computer on the same LAN as the PTS-2

### 1.2 First Connection

**Default network settings:**

| Parameter | Default |
|---|---|
| IP address | 192.168.1.117 |
| HTTP port | 80 |
| HTTPS port | 443 |
| Login | admin |
| Password | admin |

Set your computer's Ethernet adapter to the same subnet (e.g. 192.168.1.10,
mask 255.255.255.0, gateway 192.168.1.13). Open a browser:

```
http://192.168.1.117    (DIP-1 switch ON)
https://192.168.1.117   (DIP-1 switch OFF — accept the self-signed cert)
```

Accept the login prompt with `admin` / `admin`.

> **Change the default password immediately** under Configuration → Users.

### 1.3 Minimum Configuration to Record a Transaction

1. **Configuration → Pumps tab** — set Pump Port 1 to protocol and baud rate
   matching your dispenser (or "37. Pump Simulator" for testing)
2. **Configuration → Grades tab** — add at least one fuel grade with a price
3. **Configuration → Nozzles tab** — link nozzle 1 of pump 1 to the fuel grade
4. **Configuration → Parameters → Device: Controller → SD Flash Disk Settings**
   — enable "Save pump transactions to SD"

With these four steps done, take the nozzle up on the pump simulator. The pump
moves to FILLING state. Put it down. Check Reporting → Pumps — you should see
one transaction row.

### 1.4 First Remote Upload

1. **Configuration → Settings → Remote Server Settings**
   - Domain name: `technotrade.ua`
   - Server user: `admin`
   - Upload status: checked, URI `jsonPTS`, period 1 second
   - Server port: 80
   - Secret key: leave empty
2. Verify DNS: NETWORK SETTINGS → DNS `8.8.8.8` and `8.8.4.4`
3. Verify gateway matches your router

Watch for the green connectivity indicator in the Remote Server Settings section.
Then visit:
```
https://www.technotrade.ua/PTS2/Status?PtsId=<your_device_id>
```
(Device ID is on the Device Information page.) You should see live status
updating every second.

Once you confirm connectivity against Technotrade's test server, point the URIs
at your own server and replace the secret key with a strong random value.

---

## Section 2 — Hardware Reference

### 2.1 Controller Variants

| Model | MCU | Best for |
|---|---|---|
| PTS-2 | STM32F427 | Standard deployments up to 120 pumps |
| PTS-2 PRO | STM32H743 / STM32H753 | High-throughput sites, future headroom |

**Packaging options:**

| Code | Description |
|---|---|
| PTS2-PCB-001 | Bare PCB board — embed inside your own enclosure |
| PTS2-BOX-001 | PCB in metal box with cable glands and power switch |
| PTS2-SDK-001 | BOX-001 + USB/RS-485 converter + USB/RS-232 converter + cabling |

For production station deployment: **PTS2-BOX-001**.
For development and testing: **PTS2-SDK-001** (includes simulators and API).

### 2.2 Electrical Specifications

| Parameter | Value |
|---|---|
| Power supply | 12 V DC |
| Current consumption | 700 mA max (SDK: 850 mA) |
| Operating temperature | −40 °C to +60 °C |
| Dimensions | 85 × 58 × 30 mm (PCB) |
| Weight | 200 g |
| RTC battery | CR2032 3V DC |
| Storage | microSD Class 10, FAT32 |

### 2.3 Port Map

| Port | Interface | Purpose |
|---|---|---|
| ETHERNET | RJ-45 | jsonPTS — management systems, cloud server, web browser |
| PC PORT | RS-232 3-wire | UniPump binary protocol — legacy POS / PTS-1 compatibility |
| PUMP PORT 1–4 | RS-485 2-wire | Fuel dispenser control (4 independent protocols) |
| LOG PORT | RS-232 3-wire | ATG probe / console |
| USER PORT | RS-232 3-wire | ATG probe / console |
| DISP PORT | RS-485 or RS-232 | Price boards or ATG (interface selected via parameter) |
| DEBUG PORT | RS-232 2-wire (TxD+GND) | Firmware diagnostic output, 115200 baud 8N1 |
| EXT PORT | RS-232 3-wire | GPS module, optional expansion |

> **Wiring rule:** Never connect cable shields to any PTS-2 port. Connect the
> shield to ground on the dispenser side only. Use SFTP CAT 5E or CAT 6 for all
> RS-485 and current-loop runs. Minimum 0.3 m separation between power and
> signal cables in conduit.

### 2.4 DIP-Switch Reference

Applied at power-on only — changes during operation have no effect until restart.

| Switch | OFF (default) | ON |
|---|---|---|
| DIP-1 | HTTPS port 443 | HTTP port 80 |
| DIP-2 | Digest authentication | Basic authentication |
| DIP-3 | Normal startup | Format SD card on startup |
| DIP-4 | Normal startup | Reset all config to factory defaults |

**Special combination — DIP-3 + DIP-4 both ON:**
Resets to factory defaults then looks for `Config.js` in the SD card root and
restores from it automatically. User accounts are never included in the backup
for security reasons — reconfigure them manually.

### 2.5 Status LED

| Pattern | Meaning | Action |
|---|---|---|
| Toggle every 1 second | Normal operation | None |
| Rapid blink every 100 ms | Boot error | Check SD card: present, correctly seated, FAT32 |
| No blink | No power or firmware crash | Check power supply; see Section 14.1 |

### 2.6 Capacity Limits

| Resource | Limit |
|---|---|
| Pumps | 120 |
| Probes / tanks | 20 |
| Fuel grades | 20 |
| Price boards | 5 (up to 10 displays each) |
| RFID readers | 120 |
| RFID tags | No limit |
| Users | 10 |
| Pump transaction records | 100,000 |
| Tank measurement records | 100,000 |

---

## Section 3 — Protocol Architecture

### 3.1 Two Inbound Protocol Interfaces

The PTS-2 exposes two distinct protocol surfaces depending on which port you
connect to:

**jsonPTS (Ethernet port)**
Technotrade's JSON-based proprietary protocol. HTTP or HTTPS. Used by the
built-in web server, all new management system integrations, and the remote
server communication channel. The full specification is a separate document
(*"jsonPTS communication protocol specification for PTS-2 controller"*) available
from Technotrade on request — see Appendix A for how to obtain it.

**UniPump (PC port / RS-232)**
Binary protocol. Kept for backward compatibility with systems already speaking
the PTS-1 protocol. Supports the same 120 pumps and 20 probes. If you are
building new software, use jsonPTS over Ethernet instead.

### 3.2 Three jsonPTS Communication Models

Every integration with ERPNext FMS uses one or more of these three models:

```
MODEL 1 — Web Server API (synchronous request/response)
  Your code → HTTP GET/POST → PTS-2 web server → JSON response

  Use for: pump control commands, config reads, report generation.
  Latency: 50–200 ms typical on LAN.

MODEL 2 — HTTP Push (async, PTS-2 as client)
  PTS-2 → HTTP POST (pump sale / tank reading / alert) → Your server
  Your server → HTTP 200 OK → PTS-2 marks record uploaded

  Use for: receiving all operational data in near real time.
  Guarantee: at-least-once delivery with SD card buffering.
  Deduplication required on your server.

MODEL 3 — WebSocket (bidirectional, persistent)
  PTS-2 → WebSocket connect (RFC 6455) → Your server
  PTS-2 ↔ Your server (full duplex, persistent)

  Use for: real-time pump status stream + sending commands back.
  Latency: sub-second.
  Reconnect: PTS-2 reconnects automatically on disconnect.
```

For the ERPNext FMS integration, all three models are used:
- Model 2 handles inbound data (pump transactions → Forecourt Transaction doctype)
- Model 3 handles outbound commands (price push, pump auth, RFID sync)
- Model 1 is used during setup, diagnostics, and report generation

`→ FMS §10` for the Frappe-side implementation of all three models.

### 3.3 Protocol Transparency

Your integration code needs to know only the jsonPTS interface. The PTS-2
internally translates to every supported dispenser or ATG brand's native
protocol. Adding a new dispenser brand later requires only a PTS-2 firmware
update — no changes to your FMS code.

```
ERPNext FMS (jsonPTS only)
       │
       ▼
    PTS-2
       ├── Pump Port 1 → Gilbarco G-SITE RS-485
       ├── Pump Port 2 → Tatsuno current loop
       ├── Pump Port 3 → Wayne RS-485
       └── LOG Port    → Gilbarco Veeder Root TLS RS-232
```

### 3.4 Multi-Master Control

Multiple management systems can connect simultaneously through different ports.
The PTS-2 internally tracks which system holds an authorisation lock on each
dispenser at any moment. This enables the monitoring-only pattern (Section 12.4)
where a new cloud system and an existing POS coexist without conflict.

---

## Section 4 — HTTP Push Integration

### 4.1 How It Works

The PTS-2 acts as an HTTP client. For each enabled upload type it maintains two
counters on the SD card: total records saved and total records uploaded. On each
upload cycle it POSTs unuploaded records to the configured URI until it receives
HTTP 200. On non-200 or no response it retries indefinitely.

```
Records saved to SD card (PUMPTRN.CSV, TANKMSR.CSV, etc.)
         │
         │ HTTP POST, JSON body, X-Signature header
         ▼
Your server endpoint (URI configured per record type)
         │
         │ HTTP 200 OK (anything else = retry)
         ▼
PTS-2 advances the upload counter
```

**Critical requirements on your server:**
1. Return HTTP 200 for every successfully received record — including duplicates.
   If you return non-200, the PTS-2 retries forever. Duplicates arrive after any
   outage; your deduplication logic handles them, your HTTP response does not.
2. Process the record before returning 200 if you need guaranteed processing.
   Returning 200 then failing internally loses data.

### 4.2 Enabling Upload Types

Each type has two prerequisites — one on the controller, one on the probe (for
tank-related types). Both must be enabled or upload silently never happens.

| Upload type | Controller parameter | Additional requirement |
|---|---|---|
| Pump transactions | SD Flash Disk Settings → Save pump transactions to SD | — |
| Tank measurements | SD Flash Disk Settings → Save tank measurements to SD | — |
| In-tank deliveries | SD Flash Disk Settings → Save tank measurements to SD | Probe parameter → Automatic in-tank delivery detection |
| Alerts | SD Flash Disk Settings → Save alerts to SD | Tank alarms configured on Tanks tab |
| GPS records | SD Flash Disk Settings → Save GPS records to SD | GPS module installed + enabled |
| Status | No SD prerequisite | Sent on a configurable interval |
| Configuration | No SD prerequisite | Sent on every config change |

> **The most common integration failure:** pump transactions not uploading because
> "Save pump transactions to SD" was not enabled. Verify this during
> commissioning by confirming PUMPTRN.CSV exists and is growing on the SD card.

### 4.3 Remote Server Configuration

`Configuration → Settings → Remote Server Settings:`

| Field | Description |
|---|---|
| Server IPv4 address | Static IP of your server, or `0.0.0.0` if using domain name |
| Domain name | e.g. `fms.yourdomain.com` — PTS-2 resolves DNS at connect time |
| Server user | Select a user from the Users tab (PTS-2 authenticates to your server as this user) |
| Timeout of server response | Seconds to wait before marking an upload attempt as failed |
| Secret key | HMAC-SHA256 shared secret — see Section 4.4 |

For each upload type: check the enable checkbox, set the URI path, set the port.

### 4.4 HMAC Signature Verification

Every HTTP upload includes an `X-Signature` header:

```
X-Signature: <hmac-sha256-hex-digest-of-raw-request-body>
```

Your server verifies this to confirm the request came from your PTS-2 (not a
man-in-the-middle) and that the body was not altered in transit.

```python
import hmac, hashlib

def verify_pts2_signature(body: bytes, received: str, secret: str) -> bool:
    """
    Always use hmac.compare_digest — constant-time comparison prevents
    timing attacks. Never use == for HMAC comparison.
    """
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received)
```

The secret key is a shared string configured identically on the PTS-2 and your
server. Generate with:

```python
import secrets
secret = secrets.token_hex(32)   # 64 hex chars, 256 bits of entropy
```

Rotate the key by updating both sides within the same maintenance window. Any
requests with a mismatched signature should return HTTP 401. The PTS-2 will
retry — once you update the key on the PTS-2 side, uploads resume.

### 4.5 URI Routing

Each upload type has its own configurable URI. Route all types to one endpoint
and dispatch by `RecordType`, or to separate endpoints per type:

```
All → /api/method/fms.api.pts2.receive       (dispatch by RecordType)

Or per type:
  Pump transactions → /api/pts2/pump_transaction
  Tank measurements → /api/pts2/tank_measurement
  Deliveries        → /api/pts2/delivery
  Alerts            → /api/pts2/alert
  Status            → /api/pts2/status
```

### 4.6 Pump Transaction Payload

One POST per completed pump sale.

```json
{
  "RecordType":        "PumpTransaction",
  "DeviceId":          "003B00265030500420303531",
  "DateTime":          "2026-05-17 22:00:00",
  "DateTimeStart":     "2026-05-17 21:50:00",
  "Pump":              1,
  "Nozzle":            2,
  "GradeId":           1,
  "TransactionNumber": 12345,
  "UserId":            1,
  "Volume":            "0001000.000",
  "Amount":            "0214200.00",
  "Price":             "000214.200",
  "VolumeTotal":       "0000000000123456.700",
  "AmountTotal":       "0000000000567890.100",
  "TCVolume":          "0000985.000",
  "TagLength":         16,
  "Tag":    "000000000000000000000000000000001234567890abcdef"
}
```

| Field | Description |
|---|---|
| `RecordType` | Always `"PumpTransaction"` |
| `DeviceId` | Hardware ID — use this to identify which station sent the record |
| `DateTime` | Transaction end time (controller's local clock) |
| `DateTimeStart` | Transaction start time |
| `Pump` | Pump number, 1-based |
| `Nozzle` | Nozzle number on the pump, 1-based |
| `GradeId` | Fuel grade ID as configured on Grades tab |
| `TransactionNumber` | Sequential non-resettable counter — deduplication key |
| `UserId` | ID of the user/system that authorised this pump |
| `Volume` | Litres dispensed this transaction |
| `Amount` | Currency value dispensed this transaction |
| `Price` | Price per litre at time of transaction |
| `VolumeTotal` | Cumulative non-resettable volume totalizer at transaction end |
| `AmountTotal` | Cumulative non-resettable amount totalizer at transaction end |
| `TCVolume` | Temperature-compensated volume (at 15 °C base condition) |
| `TagLength` | Meaningful character count in the Tag field |
| `Tag` | RFID tag identifier — 48-char zero-padded hex string |

**Deduplication key:** `TransactionNumber` + `DeviceId`. Store as a unique
constraint. Duplicate POSTs arrive silently after outages — return 200 and
ignore them.

**Totalizer anti-theft check:** `VolumeTotal` is non-resettable and increments
for every litre dispensed whether authorised or manual. If the difference between
consecutive `VolumeTotal` values is greater than the `Volume` of the transaction
between them, fuel was dispensed outside management system control.
`→ FMS §13.3` for how this is surfaced in the Meter Reading Discrepancy Log.

**Tag extraction:**
```python
def effective_tag(tag_raw: str, tag_length: int) -> str:
    return tag_raw[-tag_length:] if tag_length else tag_raw.lstrip("0")
```

### 4.7 Tank Measurement Payload

Posted each time the PTS-2 detects a product height change exceeding the
configured threshold.

```json
{
  "RecordType":       "TankMeasurement",
  "DeviceId":         "003B00265030500420303531",
  "DateTime":         "2026-05-17 20:00:00",
  "Tank":             1,
  "Status":           0,
  "Alarms":           "00",
  "PHPresent":        true,
  "ProductHeight":    "00002500.0",
  "WHPresent":        true,
  "WaterHeight":      "00000010.0",
  "TPresent":         true,
  "Temperature":      "+00000020.0",
  "PVPresent":        true,
  "ProductVolume":    "0000020000",
  "WVPresent":        true,
  "WaterVolume":      "0000000100",
  "UPresent":         true,
  "Ullage":           "0000005000",
  "PTCVPresent":      true,
  "ProductTCVolume":  "0000019891",
  "DPresent":         true,
  "Density":          "00000759.0",
  "MPresent":         true,
  "Mass":             "00015180.0",
  "FPPresent":        true,
  "FillingPercentage": 57
}
```

The `Present` boolean for each measurement type indicates whether the connected
probe model provides that parameter. When `false`, ignore the corresponding value
field. `Status` 0 = OK; non-zero = probe error code.

**Alarm bitmask (Alarms field, hex):**

| Bit | Alarm |
|---|---|
| 0 | Product critical high |
| 1 | Product high |
| 2 | Product low |
| 3 | Product critical low |
| 4 | Water high |
| 5 | Probe failure |
| 6 | Probe float stuck |
| 7 | Tank leakage |

`→ FMS §13` for how tank measurements feed the wetstock reconciliation engine.

### 4.8 In-Tank Delivery Payload

Posted when the PTS-2 automatically detects a fuel delivery (product level rising
faster than pump dispensing can account for).

```json
{
  "RecordType":             "FuelDelivery",
  "DeviceId":               "003B00265030500420303531",
  "DeliveryStart":          "2026-05-17 19:00:30",
  "DeliveryEnd":            "2026-05-17 19:50:00",
  "Tank":                   1,
  "ValuesPresent":          "0055",
  "ProductHeightStart":     "00000125.0",
  "ProductHeightEnd":       "00002500.0",
  "WaterHeightStart":       "00000010.0",
  "WaterHeightEnd":         "00000010.0",
  "TemperatureStart":       "+00000020.0",
  "TemperatureEnd":         "+00000020.0",
  "ProductVolumeStart":     "0000001000",
  "ProductVolumeEnd":       "0000020000",
  "ProductTCVolumeStart":   "0000000995",
  "ProductTCVolumeEnd":     "0000019891",
  "DensityStart":           "00000759.0",
  "DensityEnd":             "00000759.0",
  "MassStart":              "00000759.0",
  "MassEnd":                "00015180.0",
  "PumpsDispensedVolume":   "0000000000"
}
```

`PumpsDispensedVolume` is the volume dispensed through pumps during the delivery
window. Apply the concurrent-sales correction:

```
dip_measured = ProductVolumeEnd − ProductVolumeStart + PumpsDispensedVolume
variance     = docket_volume − dip_measured
```

`→ FMS §12.1` for the full delivery reconciliation workflow.

### 4.9 Alert Payload

```json
{
  "RecordType":   "Alert",
  "DeviceId":     "003B00265030500420303531",
  "DateTime":     "2026-05-17 21:46:47",
  "DeviceType":   1,
  "DeviceNumber": 3,
  "IsStarted":    true,
  "Code":         1
}
```

| DeviceType | Device |
|---|---|
| 0 | PTS-2 Controller |
| 1 | Pump |
| 2 | Probe / Tank |
| 3 | Price Board |
| 4 | Reader |

`IsStarted: true` = condition started. `IsStarted: false` = condition cleared.
Store both events and compute duration for alerting and SLA tracking.

**Key alert codes:**

| Code | Alert |
|---|---|
| 1 | Device offline |
| 2 | Device error |
| 3 | Product critical high |
| 4 | Product high |
| 5 | Product low |
| 6 | Product critical low |
| 7 | Water height high |
| 8 | Tank leakage detected |
| 9 | Probe float stuck |
| 10 | Power supply loss |
| 11 | Low battery voltage |
| 12 | High CPU temperature |

### 4.10 Status Payload

Sent on a configurable interval (typically every 1–60 seconds). Contains
real-time state of every connected device.

```json
{
  "RecordType": "Status",
  "DeviceId":   "003B00265030500420303531",
  "DateTime":   "2026-05-17 22:30:00",
  "Controller": {
    "battery_ok": true,
    "sd_card_ok": true,
    "gps_fix":    false
  },
  "Pumps": [
    {"number": 1, "state": "IDLE",    "online": true},
    {"number": 2, "state": "FILLING", "online": true, "volume": "012.450"},
    {"number": 3, "state": "OFFLINE", "online": false}
  ],
  "Probes": [
    {"number": 1, "online": true,  "product_height": "2500.0", "alarms": "00"},
    {"number": 2, "online": true,  "product_height": "1800.0", "alarms": "04"},
    {"number": 3, "online": false, "product_height": "0.0",    "alarms": "00"}
  ],
  "Boards":   [{"number": 1, "online": true}],
  "Readers":  [{"number": 1, "online": true}]
}
```

`→ FMS §28.2` for how status feeds the HQ Dashboard's open shift and alert panels.

### 4.11 Configuration Upload Payload

Sent automatically whenever any configuration changes on the PTS-2. Contains the
equivalent of the `Config.js` backup file. Use it to maintain a configuration
snapshot per device on your server, enabling remote audit and disaster recovery.


---

## Section 5 — WebSocket Integration

### 5.1 Connection Model

The PTS-2 connects to your server as a WebSocket client (RFC 6455). You never
need a static IP or open inbound firewall at the station — outbound HTTPS on
port 443 is the only egress required.

```
Your server (WebSocket listener)
         │
         │  wss://fms.yourdomain.com/api/pts2/ws
         │  ← PTS-2 initiates the connection
         │
         │  Real-time status frames (every ~1 second)  ──→
         │  ←── Commands (authorize, price, tags, etc.)
         │
         ▼
      PTS-2 Controller
```

The PTS-2 reconnects automatically after any disconnect using the configured
reconnection period. For Shell Maanzoni's deployment on a consumer router, expect
occasional reconnects — design your server handler as stateless (no session
state that breaks on reconnect).

### 5.2 Nginx Configuration (Required)

Standard `bench setup nginx` does not enable WebSocket proxying. Add this block
inside your server's Nginx site configuration:

```nginx
location /api/pts2/ws {
    proxy_pass         http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header   Upgrade    $http_upgrade;
    proxy_set_header   Connection "upgrade";
    proxy_set_header   Host       $host;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
}
```

Without this, the Nginx proxy strips the `Upgrade` header and the WebSocket
handshake silently fails with a 101 that never upgrades.

### 5.3 Command Reference

All commands share a common envelope. Fields specific to each command follow.

**Envelope:**
```json
{
  "Command":  "<CommandName>",
  "DeviceId": "003B00265030500420303531"
}
```

---

**AuthorizePump — Unlock a pump for dispensing**

```json
{
  "Command":     "AuthorizePump",
  "DeviceId":    "003B00265030500420303531",
  "Pump":        2,
  "PresetType":  1,
  "PresetValue": "050.000"
}
```

| PresetType | Meaning |
|---|---|
| 0 | No preset — fill until nozzle down |
| 1 | Volume preset — fill N litres |
| 2 | Amount preset — fill to N currency value |
| 3 | Full tank — attendant enters preset at pump keyboard |

---

**StopPump — Emergency stop**

```json
{
  "Command":  "StopPump",
  "DeviceId": "003B00265030500420303531",
  "Pump":     2
}
```

---

**SuspendPump / ResumePump — Pause and resume filling**

```json
{"Command": "SuspendPump", "DeviceId": "...", "Pump": 2}
{"Command": "ResumePump",  "DeviceId": "...", "Pump": 2}
```

---

**SetGradePrices — Update pump display prices**

```json
{
  "Command":  "SetGradePrices",
  "DeviceId": "003B00265030500420303531",
  "Grades": [
    {"Id": 1, "Price": "214.200"},
    {"Id": 2, "Price": "229.000"},
    {"Id": 3, "Price": "242.900"}
  ]
}
```

After this command the PTS-2 immediately pushes updated prices to all connected
price boards.

`→ FMS §26.2` for how the bulk price update wizard triggers this command.

---

**UpdateTagList — Sync RFID tags**

```json
{
  "Command":  "UpdateTagList",
  "DeviceId": "003B00265030500420303531",
  "Tags": [
    {
      "Id":     "000000000000000000000000000000001234567890abcdef",
      "Name":   "Swedi Abuti",
      "Length": 16,
      "Valid":  true
    },
    {
      "Id":     "000000000000000000000000000000009876543210fedcba",
      "Name":   "Peter Mbeve",
      "Length": 16,
      "Valid":  true
    }
  ]
}
```

The tag list on the PTS-2 is replaced entirely. Send the complete active list on
every sync, not just changes.

`→ FMS §10.2` for the `sync_rfid_tags()` helper that builds this payload from
Employee records.

---

**GetStatus — Request immediate status snapshot**

```json
{
  "Command":  "GetStatus",
  "DeviceId": "003B00265030500420303531"
}
```

Response is the same format as the Status upload payload (Section 4.10).

---

**GetConfiguration / SetConfiguration — Remote config management**

```json
{"Command": "GetConfiguration", "DeviceId": "..."}
```

Returns the full controller configuration. Use `SetConfiguration` with the same
structure to apply changes remotely — equivalent to using the web server
Configuration page without browser access.

### 5.4 Pump State Values

| State | Meaning |
|---|---|
| `IDLE` | Nozzle in holster, pump ready |
| `NOZZLE` | Nozzle lifted, waiting for authorisation |
| `FILLING` | Dispensing fuel |
| `OFFLINE` | No communication with pump |

The `NOZZLE` → `FILLING` transition requires an `AuthorizePump` command (or
automatic authorisation if enabled in pump parameters).

---

## Section 6 — Web Server API

All endpoints require HTTP authentication (Digest or Basic depending on DIP-2).
Base URL: `https://<pts2-ip>` or `http://<pts2-ip>` depending on DIP-1.

### 6.1 Device Information

```
GET /
```

Returns firmware version, device ID, battery status, SD card state, GPS state,
and the list of communication protocols included in this firmware build.

Key fields:

| Field | Description |
|---|---|
| `device_id` | 24-character hex — use as the `DeviceId` in all remote server records |
| `firmware_version` | e.g. `"R11"` — check against latest before deployment |
| `battery_voltage` | Alert and replace CR2032 if below 3.0 V |
| `sd_card_free_mb` | Alert if < 50 MB |

### 6.2 Configuration Read and Write

```
GET  /config               Read all configuration
GET  /config/<tab>         Read one tab
POST /config/<tab>         Write one tab (JSON body)
```

Available tabs: `settings`, `pumps`, `probes`, `params`, `grades`, `tanks`,
`nozzles`, `boards`, `readers`, `wireless`, `users`.

### 6.3 Pump Control

```
GET  /pumps                Current state of all pumps
POST /pumps/<pump_number>  Send action to a specific pump
```

Actions available via the web API mirror the WebSocket commands (Section 5.3):
`authorize`, `stop`, `suspend`, `resume`, `get_totals`, `set_price`, `get_price`,
`get_tag`, `set_lights`.

The WebSocket channel is preferred for pump control in production — lower latency
and no connection overhead per command. Use the web API for diagnostics and
manual testing.

### 6.4 Tank Monitoring

```
GET /tanks                 Current measurements for all tanks
```

Returns all probe measurement fields per tank — same structure as the
TankMeasurement upload payload (Section 4.7) plus last delivery information.

### 6.5 Report Generation

```
GET /reports/<type>
  ?pump=<N>
  &tank=<N>
  &grade=<N>
  &user=<name>
  &tag=<hex>
  &from=<ISO datetime>
  &to=<ISO datetime>
  &format=json|csv|excel
```

Report types: `pumps`, `tanks`, `deliveries`, `reconciliation`, `gps`, `alerts`.

The reconciliation report compares pump-dispensed volume against tank ATG
measurements for the same period — a built-in cross-check before the more
detailed wetstock reconciliation in the FMS runs at shift close.
`→ FMS §13` for the FMS-side wetstock engine.

### 6.6 Fuel Grade Prices

```
POST /config/grades
```

```json
{
  "grades": [
    {"id": 1, "name": "Unleaded",  "price": "214.200", "tc_coefficient": "0.00110"},
    {"id": 2, "name": "V-Power",   "price": "229.000", "tc_coefficient": "0.00110"},
    {"id": 3, "name": "Diesel",    "price": "242.900", "tc_coefficient": "0.00084"}
  ]
}
```

Price update immediately propagates to all connected price boards. Pumps receive
it on the next authorisation, or immediately if the pump protocol supports live
price push.

### 6.7 RFID Tag List

```
GET  /config/tags          Read all tags
POST /config/tags          Replace entire tag list
```

Tag list body format mirrors the `UpdateTagList` WebSocket command (Section 5.3).
The list is also stored in `TAGS.CSV` on the SD card — downloadable and
uploadable from Configuration → Readers tab.

### 6.8 Configuration Backup and Restore

```
GET  /config/backup        Download Config.js
POST /config/restore       Upload Config.js (multipart)
```

Store `Config.js` on your management server and re-upload after firmware updates
or factory resets. **User accounts are not included in the backup** — maintain a
separate secure record of user credentials.

### 6.9 Firmware Update

```
POST /firmware             Upload c_pts2.bin or c_pts2p.bin (multipart)
```

Controller restarts automatically after upload and applies the firmware. Takes
under one minute. See Section 15 for the complete firmware update procedure
including pre-update backup steps.

---

## Section 7 — SD Card Data Files

### 7.1 File Index

| File | Description | Header row |
|---|---|---|
| `PUMPTRN.CSV` | Pump transaction records | Yes |
| `TANKMSR.CSV` | Tank measurement records | Yes |
| `TANKDLV.CSV` | In-tank delivery records | Yes |
| `GPSRECS.CSV` | GPS tracking records | Yes |
| `ALERTS.CSV` | Alert event records | Yes |
| `TAGS.CSV` | RFID tag list | **No** |
| `NNCALIB.CSV` | Tank calibration chart (NN = zero-padded tank number) | **No** |
| `ACALIBNN.CSV` | Auto-generated calibration chart | **No** |
| `CONFIG.JS` | Configuration backup | n/a |
| `SETTINGS.INI` | Internal settings | n/a |
| `PTSLOG.TXT` | System log | n/a |
| `PORTLOG.BIN` | Communication log (encrypted) | n/a |
| `SERVER.LOG` | Remote server upload log | n/a |
| `C_PTS2.BIN` | Firmware update (auto-applied on startup, then deleted) | n/a |

### 7.2 CSV Date Format

All timestamps use the format `DD.MM.YY HH:MM:SS` — note the two-digit year.
When parsing, interpret YY < 70 as 20YY and YY >= 70 as 19YY (standard Unix
convention). Store in your database as full ISO 8601 datetimes.

```python
from datetime import datetime

def parse_pts2_datetime(s: str) -> datetime:
    return datetime.strptime(s, "%d.%m.%y %H:%M:%S")
```

### 7.3 PUMPTRN.CSV Schema

```
DateTime, Pump, Nozzle, Transaction, UserId, Volume, Amount, Price,
VolumeTotal, AmountTotal, DateTimeStart, TCVolume, TagLengthSymbols, Tag
```

| Column | Format | Notes |
|---|---|---|
| DateTime | DD.MM.YY HH:MM:SS | Transaction end |
| Pump | 2-digit int | |
| Nozzle | 1-digit int | |
| Transaction | 5-digit int | Dedup key with DeviceId |
| UserId | 2-digit int | Authorising user |
| Volume | NNNNNNNN.NNN | Litres |
| Amount | NNNNNNNNNN.NN | Currency |
| Price | NNNNNNNN.NNN | Per litre |
| VolumeTotal | NNNNNNNNNNNNNNNN.NNN | Non-resettable totalizer |
| AmountTotal | NNNNNNNNNNNNNNNN.NN | Non-resettable totalizer |
| DateTimeStart | DD.MM.YY HH:MM:SS | Transaction start |
| TCVolume | NNNNNNNN.NNN | Temperature-compensated litres |
| TagLengthSymbols | 2-digit int | Meaningful chars in Tag |
| Tag | 48-char hex | Zero-padded RFID identifier |

### 7.4 TANKMSR.CSV Schema

```
DateTime, Probe, Status, Alarms,
PHPresent, ProductHeight, WHPresent, WaterHeight,
TPresent, Temperature, PVPresent, ProductVolume,
WVPresent, WaterVolume, UPresent, Ullage,
PTCVPresent, ProductTCVolume, DPresent, Density,
MPresent, Mass, FPPresent, FillingPercentage
```

Heights in mm (one decimal). Volumes as 10-digit integers (litres, no decimal).
Temperature as signed value with leading sign character `+00000020.0`.

### 7.5 TANKDLV.CSV Schema

```
DateTimeStart, DateTimeEnd, Tank, ValuesPresent,
ProductHeightStart, ProductHeightEnd, WaterHeightStart, WaterHeightEnd,
TemperatureStart, TemperatureEnd, ProductVolumeStart, ProductVolumeEnd,
ProductTCVolumeStart, ProductTCVolumeEnd, DensityStart, DensityEnd,
MassStart, MassEnd, PumpsDispensedVolume
```

`ValuesPresent` is a 4-char hex bitmask indicating which parameter columns are
populated. `PumpsDispensedVolume` is essential for delivery variance calculation
— see Section 4.8.

### 7.6 TAGS.CSV Schema

No header row. Four comma-separated fields per line:

```
TagId (48-char hex), TagLength (2-digit int), Validity (0/1), Name (≤20 chars)
```

```
000000000000000000000000000000001234567890abcdef,16,1,Swedi Abuti
000000000000000000000000000000009876543210fedcba,16,1,Peter Mbeve
000000000000000000000000000000000000000000012345,05,0,Deactivated Tag
```

### 7.7 NNCALIB.CSV Schema

No header row. Two 9-digit fields per line:

```
LevelIn_0_1mm (9-digit int), VolumeInUnits (9-digit int)
```

**Critical:** The level column is in **0.1 mm units**, not mm. To convert a
strapping table from mm to the calibration file format, multiply each height
value by 10.

```python
def mm_to_calib_units(mm: float) -> int:
    return round(mm * 10)

def format_calib_row(height_mm: float, volume_l: float) -> str:
    return f"{mm_to_calib_units(height_mm):09d},{round(volume_l):09d}"
```

File naming: `01CALIB.CSV` for tank 1, `02CALIB.CSV` for tank 2, etc.
Auto-generated charts are named `ACALIB01.CSV`, `ACALIB02.CSV`, etc.

### 7.8 ALERTS.CSV Schema

```
DateTime, DeviceType, DeviceNumber, IsStarted, Code
```

`DeviceType`: 0=Controller, 1=Pump, 2=Probe/Tank, 3=Price Board, 4=Reader.
`IsStarted`: 1=alert began, 0=alert cleared.

### 7.9 GPSRECS.CSV Schema

```
DateTime, Latitude, NorthSouthIndicator, Longitude, EastWestIndicator,
SpeedOverGround, CourseOverGround, Mode
```

Latitude in DDMM.MMMM format; Longitude in DDDMM.MMMM format.
Mode: `A` = active GPS fix, `V` = void (no fix).

---

## Section 8 — WFC Wireless Communicator

### 8.1 What It Is

The WFC (Wireless Forecourt Communicator) is a small companion board that
eliminates all RS-485 and current-loop cable runs between the PTS-2 and the
forecourt equipment. Each WFC unit installs inside a dispenser, connects to the
dispenser's internal communication interface, and talks to the central PTS-2
controller over a secured Wi-Fi network.

```
PTS-2 (in server room / kiosk)
         │
         │  Wi-Fi (secured)
         ├──────────────────── WFC unit inside Pump 1
         ├──────────────────── WFC unit inside Pump 2
         ├──────────────────── WFC unit inside Pump 3
         ├──────────────────── WFC unit inside Pump 4
         ├──────────────────── WFC unit inside Pump 5
         ├──────────────────── WFC unit inside Pump 6
         ├──────────────────── WFC unit inside Pump 7
         └──────────────────── WFC unit inside Pump 8
```

No signal cables between the controller room and the forecourt islands at all.
The PTS-2 still uses its standard configuration — the WFC layer is transparent
to the jsonPTS protocol.

### 8.2 WFC Hardware Interfaces

Each WFC board provides a rich set of physical interfaces so it can connect to
any dispenser brand:

- Various current loop interfaces (2-wire, 3-wire, 4-wire)
- Voltage-driven interfaces
- RS-485
- RS-422
- RS-232
- Additional port for RFID readers installed on nozzles

This means the WFC supports all 156 dispenser brands that the PTS-2 supports.
The WFC handles the cable connection to the dispenser; the PTS-2 handles the
protocol.

### 8.3 PTS-2 Configuration for WFC

1. Go to **Configuration → Wireless tab**
2. Select which PTS-2 pump ports are using wireless communication
3. For each device on those ports, assign the WFC unit's IP address and port

The PTS-2 sends pump control packets over Wi-Fi to each WFC unit's IP address
instead of over the RS-485 cable. From the jsonPTS protocol perspective,
nothing changes — pumps are still addressed by number.

### 8.4 Network Requirements for WFC

- A Wi-Fi access point covering the entire forecourt area with good signal at
  each pump island
- Each WFC unit gets a static IP address (or DHCP reservation by MAC address)
  on the same network as the PTS-2
- The access point should be dedicated to forecourt automation — do not share
  it with customer Wi-Fi
- Router placement: ideally in the controller room or kiosk; ensure signal
  reaches the furthest island at acceptable strength

### 8.5 Wired vs Wireless Decision Matrix

| Factor | Wired (RS-485) | Wireless (WFC) |
|---|---|---|
| Cabling labour | High — trenching or conduit per island | None |
| Ongoing reliability | Excellent once installed | Good — depends on Wi-Fi quality |
| Interference risk | Low (shielded cable) | Possible (forecourt RF environment) |
| Cost per pump | Cable + conduit + labour | WFC unit hardware cost |
| Maintenance | Rare — cables rarely fail | Wi-Fi AP maintenance; WFC firmware updates |
| Pump placement changes | Requires re-cabling | Change IP assignment only |
| Suitable for retrofits | Harder in existing buildings | Easier |

### 8.6 Shell Maanzoni Recommendation

Shell Maanzoni has 8 pumps across 4 islands. The wired option requires running
shielded cable from the controller location to each of the 4 islands, with each
island potentially needing conduit through the forecourt apron.

WFC eliminates all of that at the cost of 8 WFC units (one per pump). Before
committing to either approach:

1. Request WFC pricing from Tamara (Appendix A) — the email quotes PTS-2 unit
   prices but not WFC unit prices
2. Get a cable run estimate from your electrician for comparison
3. Survey Wi-Fi signal coverage at each island before committing to WFC

The WFC is particularly attractive for Shell Maanzoni if the pump islands are
at a significant distance from the controller location or if underground conduit
is expensive.

`→ FMS §18` for server infrastructure considerations that are independent of the
wired vs wireless choice.

---

## Section 9 — SDK and Development Environment

### 9.1 What the SDK Contains

The PTS2-SDK-001 (order code) is the recommended starting point for any
integration development. It contains everything needed to build and test the
full integration in an office environment without a live petrol station.

**Hardware (identical to the production BOX-001 plus converters):**
- PTS-2 controller in metal box
- USB/RS-485 interface converter (for pump simulator)
- USB/RS-232 interface converter (for probe simulator)
- Cabling

**Software:**
- `SimUniPump.exe` — Windows fuel dispenser simulator (up to 99 pumps)
- `SimUniProbe.exe` — Windows ATG probe simulator (up to 20 probes)
- jsonPTS communication protocol specification document
- PTS2-WEB server component
- API reference implementations in: JavaScript, C#, C++, Java

### 9.2 Development Environment Setup

```
Developer PC
├── Ethernet cable → PTS-2 Ethernet port (jsonPTS)
├── USB/RS-485 converter → PTS-2 PUMP PORT 1 (runs SimUniPump.exe)
└── USB/RS-232 converter → PTS-2 USER PORT (runs SimUniProbe.exe)
```

Power on the PTS-2 (12V DC). Set your computer's Ethernet adapter to the same
subnet as the controller (192.168.1.x). The pump and probe simulators each
appear as a COM port via the USB converters (FTDI chip drivers from
`ftdichip.com/drivers/vcp-drivers/`).

**One-time configuration (do this before writing any integration code):**

```
1. Configuration → Pumps tab
   Pump Port 1: Protocol "2. UniPump", Baud "9600"
   Assign pumps 1–4, physical addresses 1–4

2. Configuration → Probes tab
   Probe port USER: Protocol "9. UniProbe", Baud "9600"
   Assign probes 1–3, physical addresses 1–3

3. Configuration → Parameters → Device: Pump
   For each pump 1–4: Parameter 1.2 "Protocol type" = "UniPump for PTS"

4. Configuration → Grades tab
   Add fuel grades matching your station (UX, VP, DX)

5. Configuration → Nozzles tab
   Link each nozzle to its grade and tank

6. Configuration → Parameters → Device: Controller
   SD Flash Disk Settings → enable all Save checkboxes

7. Run SimUniPump.exe
   Settings: 9600 baud, 8N1 → Open the RS-485 COM port
   Verify green+red LEDs blink on PTS-2 Pump Port 1

8. Run SimUniProbe.exe
   Settings: 9600 baud, 8N1 → Open the RS-232 COM port
   Verify green+red LEDs blink on PTS-2 USER port
```

Only green LED blinking (no red) means the PTS-2 is sending but not receiving —
check wiring or configuration.

### 9.3 Language Guide

**Which language to use depends on where the code runs:**

| Language | Best for | SDK support |
|---|---|---|
| Python | Frappe/ERPNext hooks, server-side receiver, CLI tools | Derive from jsonPTS spec (not in SDK but straightforward) |
| JavaScript | Browser-side pump monitoring widget, Node.js server | Included in SDK |
| C# (.NET Core) | Windows POS systems, cross-platform server | Included in SDK (open source) |
| C++ | Embedded systems, performance-critical gateways | Included in SDK |
| Java | Android mobile apps, cross-platform server | Included in SDK |

For the ERPNext FMS integration, Python is the primary language.
`→ FMS §10` for the complete Python receiver and WebSocket command implementations.

### 9.4 JavaScript Integration

The SDK ships a JS reference implementation. For browser-based monitoring (pump
status display in an ERPNext workspace widget or standalone dashboard):

```javascript
// WebSocket connection to PTS-2 controller (direct LAN connection)
class PTS2Monitor {
  constructor(pts2Host, credentials) {
    this.host = pts2Host;
    this.auth = btoa(`${credentials.user}:${credentials.password}`);
    this.ws   = null;
    this.onStatus = null;   // callback: (statusPayload) => void
  }

  connect() {
    this.ws = new WebSocket(`ws://${this.host}/api/pts2/ws`);

    this.ws.onopen = () => {
      // Send authentication handshake per jsonPTS spec
      this.ws.send(JSON.stringify({
        Command:  "Authenticate",
        User:     atob(this.auth).split(":")[0],
        Password: atob(this.auth).split(":")[1]
      }));
      // Request immediate status
      this.ws.send(JSON.stringify({Command: "GetStatus"}));
    };

    this.ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.RecordType === "Status" && this.onStatus) {
        this.onStatus(msg);
      }
    };

    this.ws.onclose = () => {
      // Reconnect after 5 seconds
      setTimeout(() => this.connect(), 5000);
    };
  }

  authorize(pumpNumber, presetType = 0, presetValue = null) {
    const cmd = {Command: "AuthorizePump", Pump: pumpNumber, PresetType: presetType};
    if (presetValue) cmd.PresetValue = presetValue;
    this.ws.send(JSON.stringify(cmd));
  }

  updatePrices(grades) {
    // grades: [{id: 1, price: "214.200"}, ...]
    this.ws.send(JSON.stringify({
      Command: "SetGradePrices",
      Grades:  grades.map(g => ({Id: g.id, Price: g.price}))
    }));
  }
}

// Usage
const monitor = new PTS2Monitor("192.168.1.117", {user: "pos", password: "secret"});
monitor.onStatus = (status) => {
  status.Pumps.forEach(pump => {
    console.log(`Pump ${pump.number}: ${pump.state}`);
  });
};
monitor.connect();
```

### 9.5 C# Integration

The SDK ships a .NET Core open-source API compatible with Windows, Linux, and
macOS. For integrations with Windows-based POS systems or cross-platform backend
services:

```csharp
// Minimal HTTP push receiver in ASP.NET Core
using System.Security.Cryptography;
using System.Text;

[ApiController]
[Route("api/pts2")]
public class PTS2ReceiverController : ControllerBase
{
    private readonly string _secret;
    private readonly IPumpTransactionService _txService;

    public PTS2ReceiverController(IConfiguration config,
                                   IPumpTransactionService txService)
    {
        _secret    = config["PTS2:SecretKey"];
        _txService = txService;
    }

    [HttpPost("receive")]
    public async Task<IActionResult> Receive()
    {
        using var reader = new StreamReader(Request.Body);
        var body = await reader.ReadToEndAsync();

        // Verify HMAC signature
        if (!string.IsNullOrEmpty(_secret))
        {
            var received = Request.Headers["X-Signature"].FirstOrDefault() ?? "";
            var expected = ComputeHmac(body, _secret);
            if (!CryptographicOperations.FixedTimeEquals(
                    Encoding.UTF8.GetBytes(expected),
                    Encoding.UTF8.GetBytes(received)))
                return Unauthorized();
        }

        var data = System.Text.Json.JsonSerializer.Deserialize<
            Dictionary<string, object>>(body);

        switch (data["RecordType"].ToString())
        {
            case "PumpTransaction":
                await _txService.HandleAsync(data);
                break;
            // ... other record types
        }

        return Ok();  // Must return 200 for PTS-2 to advance upload counter
    }

    private static string ComputeHmac(string body, string secret)
    {
        using var hmac = new HMACSHA256(Encoding.UTF8.GetBytes(secret));
        var hash = hmac.ComputeHash(Encoding.UTF8.GetBytes(body));
        return Convert.ToHexString(hash).ToLower();
    }
}
```

### 9.6 Python Integration

Python is not in the SDK but is the primary language for Frappe/ERPNext.
The complete production-ready Python receiver, WebSocket command helpers, and
utility functions are in the FMS Implementation Guide.
`→ FMS §10.2` for `fms/api/pts2.py` (receiver).
`→ FMS §10.2` for `fms/api/pts2_commands.py` (WebSocket commands).

For standalone Python (outside Frappe):

```python
import json, hmac, hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler

SECRET = "your-secret-key-here"

class PTS2Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length)
        sig    = self.headers.get("X-Signature", "")

        # Verify signature
        expected = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            self.send_response(401)
            self.end_headers()
            return

        data = json.loads(body)
        handle(data)   # your dispatch logic

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def log_message(self, *args):
        pass  # suppress default access log

def handle(data):
    rt = data.get("RecordType")
    if rt == "PumpTransaction":
        print(f"Sale: Pump {data['Pump']} Nozzle {data['Nozzle']} "
              f"Vol {data['Volume']} L Amt {data['Amount']}")
    elif rt == "TankMeasurement":
        print(f"Tank {data['Tank']} Level: {data.get('ProductHeight')} mm")
    elif rt == "Alert":
        print(f"Alert: Device {data['DeviceType']}/{data['DeviceNumber']} "
              f"Code {data['Code']} Started={data['IsStarted']}")

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8080), PTS2Handler)
    print("Listening on :8080")
    server.serve_forever()
```

### 9.7 PTS2-WEB Server Component

The SDK includes a component called **PTS2-WEB server**. This is a separate
piece of software (not the built-in PTS-2 web server on the controller itself)
intended for developers building web-based management front-ends.

PTS2-WEB server acts as a bridge:

```
Browser / Web App
      │
      │  REST / WebSocket (jsonPTS)
      ▼
PTS2-WEB Server (runs on your PC or server)
      │
      │  jsonPTS (Ethernet)
      ▼
PTS-2 Controller
      │
      ▼
Dispensers / Probes
```

It handles the jsonPTS communication with the controller and exposes a clean
API to your web front-end, abstracting the lower-level protocol details. Useful
for building browser-based POS dashboards or kiosk interfaces.

To obtain full documentation and the PTS2-WEB server binaries: contact Tamara
at `ts@technotrade.ua` or WhatsApp `+380958347530` (see Appendix A).

### 9.8 Simulator Reference

**SimUniPump.exe — Fuel Dispenser Simulator:**

| Feature | Detail |
|---|---|
| Pumps supported | Up to 99, each with a unique physical address |
| Nozzles per pump | Up to 6, each with independent total counters |
| Modes | Automatic (controlled by PTS-2) / Manual (independent) |
| Totalizers | Volume and amount per nozzle, stored in Windows registry |
| Preset support | Volume, amount, full tank |
| Immediate dispensing | Skip wait time for large volume tests |
| Random presence | Simulator autonomously takes nozzles up and down for integration testing |

**SimUniProbe.exe — ATG Probe Simulator:**

| Feature | Detail |
|---|---|
| Probes supported | Up to 20 |
| Measurable parameters | Product height, water height, temperature, product volume, water volume, ullage, TC volume, density, mass |
| Any parameter | Can be individually enabled or disabled per probe |
| Delivery simulation | Simulate in-tank delivery event |
| Error simulation | Simulate probe error state |
| Tank height | Configurable per probe |

---

## Section 10 — Device Configuration Reference

### 10.1 Parameters System

All PTS-2 configuration is stored as typed parameters in 4-byte (32-bit) memory
sections. Parameters are grouped by device type. The full catalogue is in the
configuration files `pts_config_en.js` (English), accessible at:

```
https://192.168.1.117/pts_config_en.js
```

This file lists every supported protocol, baud rate, and parameter with its
type, range, mask, shift, and default value.

### 10.2 Essential Controller Parameters

**SD Flash Disk Settings** — these must be enabled for any data to upload:

| Parameter | Must enable for |
|---|---|
| Save pump transactions to SD | Pump transaction upload, reports |
| Save tank measurements to SD | Tank measurement upload, delivery detection |
| Save GPS records to SD | GPS tracking (requires GPS module) |
| Save alerts to SD | Alert upload |

**Port Flexible Communication Settings** — per probe port (LOG, USER, DISP):
- Data bits (7 or 8)
- Stop bits (1 or 2)
- Parity (None, Even, Odd)

Some ATG brands require specific settings here. Check the ATG manufacturer's
documentation for the correct communication parameters.

**Decimal Digits System Settings:**
Number of decimal digits in volume, amount, and price. **Must match the
dispenser display configuration** — mismatch causes all volume and amount values
to be off by a power of 10.

**Logging Settings:**
Enable "Extended logging for data upload to remote server" to generate
`SERVER.LOG`. Turn on only when troubleshooting connectivity — it generates
significant log volume.

### 10.3 Pump Parameters

**PUMP AUTHORIZATION SETTINGS:**

| Parameter | When to enable |
|---|---|
| Automatically authorize pump on nozzle up | Standalone operation without POS |
| Automatically close transaction | Automatic mode — close on nozzle down |
| Read pump totals automatically | Always enable — needed for totalizer-based theft detection |

**TAG VERIFICATION SETTINGS:**

| Parameter | Effect |
|---|---|
| Verify tag in list before authorization | Pump only authorizes if the presented RFID tag is in the allowed list |
| Keep verifying tag during filling | Pause filling if tag is removed mid-fill (AVI anti-theft) |

**PUMP MULTIPLIERS:**
Adjust volume, price, and amount scale factors. Use if the dispenser display
shows values in unexpected units or the number of decimal places differs from
the PTS-2 settings.

### 10.4 Probe Parameters

| Parameter | Effect |
|---|---|
| Probe offset from tank bottom | Distance from sensor base to tank floor in mm. Critical for accurate volume calculation. |
| Automatic volume from calibration chart | Enable if probe measures level only (not volume). Requires calibration chart uploaded. |
| Automatic TC volume | Calculate temperature-compensated volume at 15 °C. Requires temperature measurement and grade TC coefficient. |
| Automatic in-tank delivery detection | Enable for delivery auto-detection and `TANKDLV.CSV` recording. |
| Automatic tank leakage detection | Raise alert if tank loses product faster than pumps can account for. |
| Automatic alarm check | Monitor high/low product and water levels. |

### 10.5 Fuel Grade Configuration

For each grade: name, price per litre/gallon, temperature-expansion coefficient.

**Temperature-expansion coefficients at 15 °C:**

| Product | Coefficient |
|---|---|
| Petrol (PMS, UX, VP) | 0.00110 |
| Diesel (AGO, DX) | 0.00084 |
| Aviation Jet A-1 | 0.00094 |
| Kerosene (DPK) | 0.00094 |
| LPG propane | 0.00290 |
| LPG butane | 0.00200 |

For Shell Maanzoni: UX and VP both use 0.00110; DX uses 0.00084.
`→ FMS §6.3` for how fuel grades map to ERPNext Items.

---

## Section 11 — Connected Devices

### 11.1 Fuel Dispensers

**Connection interfaces supported:**

| Interface | Notes |
|---|---|
| RS-485 (2-wire A/B) | Most modern dispensers — direct connection |
| 2-wire current loop | Older Gilbarco, Tokheim — needs RS-485 converter |
| 3-wire current loop | Some Tokheim models |
| 4-wire current loop | Some Nuovo Pignone models |

Interface converter catalogue: `technotrade.ua/dispensers-interface-converters.html`

**Configuration steps:**
1. Configuration → Pumps tab: assign protocol and baud rate per pump port
2. Assign each pump to a port with its physical address (the ID set inside the
   dispenser)
3. Verify decimal digit settings match dispenser display (Parameters → Controller
   → DECIMAL DIGITS SYSTEM SETTINGS)
4. Set pump parameters per pump (Parameters → Pump)
5. Configure grades and nozzle linkages

**Operations available on all brands:**
get status, authorize, stop, suspend/resume, get/set price, get totals,
get filling info, get transaction info, TC volume calculation, set lights (brand
dependent), get tag (brand dependent).

**Built-in pump simulator:** Protocol "37. Pump Simulator" for development
without real hardware. Supports immediate dispensing, nozzle up/down simulation,
zero-volume transactions, and tag simulation.

### 11.2 ATG Systems and Probes

Up to 20 probes across 3 ports (LOG, USER, DISP). Each port independently
configurable for protocol, baud rate, data bits, stop bits, and parity.

**Configuration steps:**
1. Configuration → Probes tab: assign protocol and baud rate per probe port
2. Assign each probe to a port with its physical address
3. Configuration → Tanks tab: configure tanks (tank 1 = probe 1, tank 2 = probe 2)
4. Upload calibration charts per tank
5. Set probe parameters per probe

**Features available on all brands:**
product level, water level, temperature, product volume, water volume, ullage,
TC volume, density, mass (availability depends on probe model — check Present
flags in the measurement payload).

**Auto-calibration:** If no strapping table is available, enable automatic
calibration on the tank. The PTS-2 accumulates level and dispensing data over
several days of normal operation and generates `ACALIBNN.CSV` automatically.

**Built-in probe simulator:** Protocol "7. Probe Simulator". Supports all
measurement parameters and delivery event simulation.

### 11.3 Price Boards

Up to 5 boards, up to 10 price displays each. Connect via DISP port (RS-485
or RS-232, selectable via parameter).

Configuration on Boards tab: assign port, protocol, baud rate, physical address,
and which fuel grades each board should display.

Price boards update automatically whenever grade prices change in the PTS-2
— whether via web API, WebSocket command, or remote server configuration push.

### 11.4 RFID Readers and AVI Systems

Up to 120 readers. Configurable per port for protocol, baud rate, and
communication settings. Each reader is assigned to a specific pump (or all
pumps if Pump = 0).

**RFID for attendant authorisation:**
- Attendant taps RFID card → PTS-2 checks tag against allowed list → authorizes
  pump if valid
- All transactions saved with the attending tag ID — full per-attendant sales
  reporting

**AVI for vehicle identification:**
- Nozzle reader detects vehicle transponder when nozzle inserted in tank
- PTS-2 continuously re-reads during filling — if nozzle removed (canister theft),
  filling pauses automatically
- Filling resumes only when the original vehicle tag is detected again

`→ FMS §14` for how RFID tags map to Employee records and fleet card records.

---

## Section 12 — Integration Patterns

Each pattern is self-contained. A real deployment may combine elements of
multiple patterns at different phases.

### 12.1 Pattern A — Full Cloud (Recommended for New Installations)

**Topology:**
```
PTS-2 (station) → HTTPS push + WSS commands → ERPNext FMS (cloud)
```

**PTS-2 configuration:**
- DIP-1 OFF (HTTPS)
- Remote server: domain name = your cloud domain, port 443
- All upload types enabled
- WebSocket enabled, reconnect period 30 seconds
- SD card logging enabled for all types

**Data flow:**
- Pump transactions → FMS creates Forecourt Transaction → linked to open Shift
- Tank measurements → FMS monitors stock levels in tabBin
- Deliveries → FMS raises Purchase Receipt for review
- Alerts → FMS creates Forecourt Alert, triggers notifications
- Status → FMS HQ Dashboard updates in real time

`→ FMS §10` for all Frappe-side implementation.
`→ FMS §28` for the HQ Dashboard that consumes this data.

### 12.2 Pattern B — LAN Integration (Existing POS On-Site)

**Topology:**
```
Existing POS (LAN) ←→ PTS-2 (LAN) ←→ Dispensers
```

**Use case:** You have a site-level POS system that will drive the PTS-2
directly on the local network. Cloud upload is secondary or disabled.

**PTS-2 configuration:**
- DIP-1 ON or OFF depending on your POS's SSL capability
- No remote server needed (or optional for reporting only)
- POS connects to `http://192.168.1.117` or configured LAN IP

**FMS role:** The FMS may still receive uploads for HQ reporting while the POS
handles real-time station control.

### 12.3 Pattern C — Protocol Converter (Existing POS, Different Dispensers)

**Use case:** Your POS speaks one dispenser protocol (e.g. Gilbarco G-SITE) but
you have installed a different dispenser brand.

```
Existing POS (speaks Gilbarco) → PTS-2 Pump Port 2 (Gilbarco input)
                                → PTS-2 Pump Port 1 (Censtar output → actual dispensers)
```

No changes to the existing POS software. The PTS-2 translates internally.
Supports up to 4 simultaneous protocol conversions across its 4 pump ports.

### 12.4 Pattern D — Monitoring Only (Existing Automated Station)

**Use case:** A station already has a POS system controlling dispensers. You
want cloud reporting and alerts without disrupting the existing operation.

Install the PTS-2 in-line between the existing POS/controllers and the
dispensers. The PTS-2 passes all communication through while capturing every
transaction, tank reading, and alert and uploading to the FMS.

Existing POS: no changes required. The PTS-2 operates invisibly.

### 12.5 Pattern E — Phased Automation (Shell Maanzoni)

Shell Maanzoni's planned trajectory:

**Phase 1 — Data Collection (now):**
Deploy PTS-2 in automatic mode. All pump sales auto-recorded and uploaded to
ERPNext FMS. Meter readings, dip readings, and cash reconciliation entered
manually by station staff in ERPNext.
`→ FMS §14` (Automatic Station Operation) for PTS-2 parameters.
`→ FMS §9` for manual station workflows that run in parallel.

**Phase 2 — Partial Integration:**
ERPNext sends `AuthorizePump` commands via WebSocket before each fill. POS
Invoices auto-created from Forecourt Transaction records at shift close.
Manual meter entry simplified to verification rather than data entry.
`→ FMS §11.3` for shift close workflow.

**Phase 3 — Full Integration:**
RFID attendant cards synced from Employee records. Fleet card authorisation via
RFID readers linked to Customer records. Price push from ERPNext to PTS-2
triggered automatically on EPRA gazette updates. Shift open/close fully
automated.
`→ FMS §14, §26.2` for fleet card and bulk price push workflows.

---

## Section 13 — Security Reference

### 13.1 Transport Security

| Scenario | Protocol | Recommendation |
|---|---|---|
| Initial setup / LAN development | HTTP (DIP-1 ON) | Acceptable for private LAN only |
| Production LAN | HTTPS (DIP-1 OFF, self-signed cert) | Accept the cert in your client |
| Production remote upload | HTTPS port 443 | Your server must have a CA-signed cert |
| WebSocket LAN | WS | Acceptable for private LAN only |
| WebSocket remote | WSS (TLS) | Required for internet-facing deployment |

### 13.2 Authentication Modes

**Digest (DIP-2 OFF, default):** Challenge-response. Credentials are never sent
in plain text. Preferred for all deployments.

**Basic (DIP-2 ON):** Credentials Base64-encoded in the Authorization header.
Only use over HTTPS where the header is encrypted by the TLS layer.

### 13.3 User Permission Model

Create a dedicated user for each management system. The admin account should
only be used for configuration via browser — never in automated integrations.

| Permission | What it allows |
|---|---|
| Configuration | Read and write all configuration tabs |
| Control | Authorize pumps, stop pumps, set prices |
| Monitoring | Read pump states and tank measurements |
| Reports view | Generate and download reports |

Minimal permission sets:
- FMS receiver user: Monitoring + Reports view
- FMS command user (price push, pump auth): Control + Monitoring
- Audit user: Reports view only

### 13.4 HMAC Key Management

```python
# Generate a strong secret key
import secrets
key = secrets.token_hex(32)   # 256-bit key, 64 hex characters
print(key)

# Store in your server's environment variables — never in source code
# Environment variable: PTS2_SECRET_KEY=<key>
```

**Key rotation procedure:**
1. Generate new key
2. Update your server's environment variable (or Frappe site config)
3. Update the PTS-2: Configuration → Settings → Remote Server Settings → Secret key
4. Both sides must be updated in the same maintenance window
5. Any device that is offline during rotation will resume uploading once
   reconnected and its key is updated

---

## Section 14 — Diagnostics and Troubleshooting

### 14.1 Status LED Diagnostic

| LED pattern | Likely cause | Resolution |
|---|---|---|
| Toggle 1s | Normal | None |
| Rapid blink 100ms | SD card issue | Check insertion; verify FAT32; use DIP-3 ON to reformat |
| No LED at all | No power | Check 12V supply, polarity, current rating |
| Normal LED but no web access | Network issue | Verify IP settings; try DIP-4 reset if password lost |

### 14.2 Self-Diagnostics Page

Tests all hardware peripherals. Before running diagnostics, connect the
board in loopback configuration:

- RS-485 ports (all 4 pump ports + DISP RS-485): interconnect all A lines
  together, all B lines together
- RS-232 ports (PC, LOG, USER, DISP RS-232): short TxD to RxD on each port

Results: green = OK, red = Error. A red pump port usually indicates a wiring
issue or a faulty RS-485 line driver.

### 14.3 Communication Logging

The Logging page records raw bytes on any selected port to `PORTLOG.BIN` (encrypted).
Use this to diagnose dispenser communication problems.

**Procedure:**
1. Note current time (shown on Logging page)
2. Select the port (e.g. Pump Port 1)
3. Set a stop time
4. Click START
5. Reproduce the problem
6. Click STOP and download the log file
7. Email to `support@technotrade.ua` with: device protocol, physical address,
   exact timestamp of the problem, detailed description

The file is encrypted — Technotrade must decode it.

### 14.4 Remote Server Upload Troubleshooting

**Step 1:** Enable extended logging.
Configuration → Parameters → Device: Controller → LOGGING SETTINGS →
"Extended logging for data upload to remote server" → Set.

**Step 2:** Download `SERVER.LOG` from Device Information page.

**Step 3:** Inspect each upload session for the failure mode.

Common failures and resolutions:

| Symptom in SERVER.LOG | Cause | Fix |
|---|---|---|
| DNS resolution failed | DNS server not configured | Network Settings → DNS: 8.8.8.8, 8.8.4.4 |
| Connection refused | Wrong port or server not listening | Verify server port and firewall rules |
| Connection timeout | Gateway misconfigured | Network Settings → Gateway must match router |
| 401 Unauthorized | Wrong user credentials | Users tab → verify user password; verify server expects same credentials |
| 500 / non-200 response | Server-side error | Check your server's application logs |
| Records stuck (counter not advancing) | SD logging disabled | Enable Save to SD in controller parameters |
| Duplicate records arriving | Server returning non-200 on dedup path | Server must return 200 for duplicates too |

**Quick connectivity test:** Point upload to Technotrade's test server
(see Section 1.4). If the green indicator appears, your PTS-2 network and
configuration are correct — the problem is specific to your server endpoint.

### 14.5 Debug Port

Connect a serial terminal to the DEBUG port (2 wires: TxD + GND):
- Baud rate: 115200
- Data bits: 8
- Stop bits: 1
- Parity: None

Displays raw firmware boot messages and diagnostic output. Useful when the
web server is not reachable after a firmware update.

---

## Section 15 — Firmware Management

### 15.1 Update via Web Interface

Request the latest firmware from Technotrade (`support@technotrade.ua`) or
download from `technotrade.ua/pts2-forecourt-controller.html`.

**Before updating — always do these three things:**
1. Download `Config.js` (Configuration → Settings → BACKUP/RESTORE CONFIGURATION)
2. Download all CSV report files (Reporting → Report files tab)
3. Note all user accounts and passwords — they are not backed up

**Update procedure:**
1. Firmware Update page → Select `c_pts2.bin` (PTS-2) or `c_pts2p.bin` (PTS-2 PRO)
2. Upload — controller restarts automatically
3. Update takes under 1 minute
4. Verify new firmware version on Device Information page
5. If configuration was lost, restore from `Config.js`
6. Reconfigure user accounts manually

### 15.2 Update via SD Card

1. Place `c_pts2.bin` / `c_pts2p.bin` in the SD card root
2. Power on — firmware auto-applies on startup
3. File is deleted after successful application

Use this method when web access is unavailable.

### 15.3 Recovery After Failed Update

If web access fails after a firmware update:

1. Set DIP-3 ON and DIP-4 ON
2. If you have `Config.js`: place it in the SD card root
3. Press the Restart button on the board
4. Controller resets to factory defaults, then auto-restores from `Config.js`
5. Return DIP-3 and DIP-4 to OFF
6. Reconfigure user accounts

---

## Appendix A — Procurement and Pre-Deployment

### A.1 Pricing (USD, March 2026)

| Product | Order Code | 1–2 pcs | 3–9 pcs (−5%) | 10–49 pcs (−10%) | 50–99 pcs (−15%) | 100+ pcs (−20%) |
|---|---|---|---|---|---|---|
| PCB board (bare) | PTS2-PCB-001 | $950 | $903 | $855 | $807 | $760 |
| Controller in box | PTS2-BOX-001 | $1,025 | $974 | $923 | $871 | $820 |
| SDK (development kit) | PTS2-SDK-001 | $1,250 | $1,187 | $1,125 | $1,063 | $1,000 |

For a typical single-site deployment (Shell Maanzoni):
- 1 × SDK-001 for development: $1,250
- 1 × BOX-001 for the station: $1,025
- Total hardware: $2,275

For multi-site (3–9 sites) bulk order, the 3–9 unit pricing applies to
BOX-001: $974 per site, saving $51 per unit.

> WFC unit pricing not listed in the March 2026 quote — request separately
> from Tamara before committing to wired installation.

### A.2 BOM Per Site

In addition to the PTS-2 unit, each site requires:

| Item | Specification | Notes |
|---|---|---|
| Power supply adapter | 12V DC, 2–5A | Standard industrial PSU; use UPS for continuous power |
| Network cable | FTP CAT 5E or FTP CAT 6 | Wired deployments only; one run per pump island |
| RTC battery | CR2032 3V DC | Pre-install before deployment; replace when voltage < 3.0V |
| Internet router | No specific requirements | Middle-range consumer router suitable |
| WFC units | 1 unit per pump | Wireless deployments only — price TBD |

### A.3 What to Request from Technotrade Before Development Begins

The following items are not publicly available and must be requested directly:

1. **jsonPTS communication protocol specification document** — the complete
   field-by-field protocol reference. Without this, the SDK API samples and this
   guide are sufficient to build a working integration, but the spec document
   fills in edge cases, error codes, and advanced commands.

2. **SDK-001 unit** — order to ship to Nairobi. Lead time: Kyiv, Ukraine →
   Nairobi varies; confirm with Tamara at time of order.

3. **WFC pricing and stock** — quote for 8 units (one per pump at Shell Maanzoni).

4. **BOX-001 quote** for Shell Maanzoni production deployment.

### A.4 Contact

| Channel | Details |
|---|---|
| Primary contact | Tamara Soldatska — Business Development Responsible |
| Email | ts@technotrade.ua |
| WhatsApp | +380958347530 |
| Phone | +380979232791, +380445024655 |
| Skype | live:tamroniy |
| Technical support | https://www.technotrade.ua/support |
| Postal address | Mrii str. 17, Kyiv 04128, Ukraine |
| Web | www.technotrade.ua |
| YouTube demos | https://www.youtube.com/watch?v=Y3DpBNii_84 (PTS-2 overview) |
| WFC video | https://www.youtube.com/watch?v=odUBGFAMEac |
| WFC product page | https://www.technotrade.ua/wireless-forecourt-communicator |

---

## Appendix B — Supported Hardware

### B.1 Fuel Dispensers (156 brands)

2A · ACTRONIC · ADAST · AG WALKER · AGIRA · ANGI International · ARIEL · ASPRO ·
ASSYTECH · ASTRON · AZT · BAILONG · BARANSAY · BATCHEN · BENNETT · BERNET ·
BLUE SKY · CENSTAR · CETIL · CFT Clean Fuel · CHANGLONG · COMPAC · COPTRON ·
CORITEC · CZAR · DATIAN MACHINES · DEM G. SPYRIDES · DEVELCO · DIGITAL FLOW ·
DINT · DONG HWA PRIME · DURULSAN · EAGLESTAR · EASTAR · ECOTEC · EHAD ·
EKOSIS · EMGAZ DRAGON · ENDURANCE · EPCO · ESIWELMA · EUROPUMP · FALCON LPG ·
FLOW · FORNOVO GAS · FUELQUIP · FUELSIS · FUREN HIGHTECH · GALILEO · GASLIN ·
GERKON · GESPASA · **GILBARCO** · GREENFIELD · HAKO · HITACHI · HONG YANG ·
IFSF · IMW · INTERMECH · IPT · JANASI · JAPAN ENERJUMP · JAPAN TECH · KAISAI ·
KALVACHA · KIEVNIIGAZ · KOREA ENE · KPG-2 · KRAUS · KRIPFLOW · KWANGSHIN ·
LAFON · LANFENG · LAOXU · LEARED · LIQUID CONTROLS · LG ENE · LOGITRON · MAIDE ·
MASER · MEKSAN/WAYNE SU86 · MEKSER · MEPSAN · MIDCO · MIDCOM · MITHRA FUELING ·
MM PETRO · MOTOGAZ · MOUNTAIN CHINA · MRT · MS GAS · MUXTRONICS · NARA ·
NET FUN LEADER · NUOVA MIGAS · **NUOVO PIGNONE** · ONSUN · ORCA ·
PEC (GALLAGHER) · PARKER · PECO · PEGASUS · PETPOSAN · PETROEQUIP ·
PETROMECCANICA · PETROTEC · PROWALCO · PUMP CONTROL · PUMPTRONICS · REAL-TECH ·
RIX · S.A.M.P.I. · SAFE · SALZKOTTEN · **SANKI** · SATAM EQUALIS S · SAVEL ·
SEA BIRD · SHELF · SCHEIDT & BACHMANN · SHIBATA · SLAVUTICH · SOMO PETRO ·
STABILIZING · STAR · STAR-HIGH · **TATSUNO (JAPAN)** · **TATSUNO EUROPE** ·
TATTAN · TAURUS · TEAM · TEKSER · TERABAYT TEXNO SERVIS · TIGER ·
**TOKHEIM** · **TOKHEIM INDIA** · TOKICO · TOMINAGA · TOPAZ ·
TOTAL CONTROL SYSTEMS · TRANSPONDER · TRUE TECH · UCAR ELEKTRIC · UESTCO ·
UNICON-TIT · VANZETTI · **WAYNE DRESSER** · WAYNE PIGNONE · WELLDONE MACHINES ·
WERTCO · WINTEC ENERGY · YENEN · ZCHENG GENUINE MACHINES · ZHEJIANG ZHISHENG ·
ZHONGSHENG

### B.2 ATG Systems and Probes (65 brands)

ACCU · **ALISONIC** · ANHUI QIDIAN · ASSYTECH · AXIONICS · BLUESKY · CENSTAR ·
DOVER · DUT-E · EAGLESTAR · EBW · EMERSON ROSEMOUNT · ENRAF · ESCORT FD ·
**FAFNIR** · FIRSTRATE · **FRANKLIN FUELING** · GAMICOS · **GILBARCO VEEDER ROOT** ·
HCCK · HECTRONIC · HOLYKELL · HONG YANG · HUMANENTEC · IFSF · INCON · JOYO ·
JUBO · KACISE · KANGYU · KUNLUN · LABKO · LIGO · MECHATRONICS · MEPSAN UNIMEP ·
METRIKEMP · MTS ATG SENSORS · ND · NORTH FALCON · O.L.E. · OKET · OMNICOMM ·
OMNTEC · **OPW** · PHOENIX · POKCENSER · QINGDAO GUIHE · RCS EPSILON · RIKA ·
SANSHEN · SBEM · SENSOR · SINOTECH · SKE LEVEL GAUGE · **START ITALIANA** ·
**STRUNA** · TECHNOTON · TENET · UBTECK · UNIPROBE · **VEGA** · VEPAMON ·
WINDBELL · XT SENSORS · ZCHENG GENUINE MACHINES

### B.3 Price Boards (17 brands)

AVS · BEVER INNOVATIONS · BODET · COMSIGHT · GILBARCO · GLARE-LED · HECTRONIC ·
MENTALITY · NOVYC · PANELES LEDS PERU · PCA · PWM · QSERV · RGB TECHNOLOGIES ·
SHENZHEN JUMING ELECTRONICS (UMLED) · TOP SCREENS · U-GREAT LED

### B.4 RFID Readers and AVI Systems (10 types)

CHAFON UHF · HECTRONIC AVI · HID AVI · LINKSPRITE ISO-18000-6B/6C (EPC G2) ·
LOOPTAG AVI · MINGTE AVI · OTI PETROSMART · RDR-485 · VIOTYS · VRD-485

---

*End of Document*

**Source:** Technotrade LLC Technical Guide R11 (Oct 2024) + Commercial Quote (Mar 2026)
**Guide Version:** 2.0.0
**Excludes by design:** KRA eTIMS compliance (dedicated compliance app),
MPesa integration (dedicated payments app)
**Companion document:** ERPNext FMS Implementation Guide v3.0.0

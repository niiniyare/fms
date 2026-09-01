# PTS-2 Forecourt Controller — FMS Integration Guide

**Controller:** PTS-2 (Technotrade LLC, Ukraine)  
**Protocol:** jsonPTS, Revision 140 (2026-08-16)  
**Integration type:** Bidirectional — WebSocket + HTTP push  
**Status:** Design phase

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  FORECOURT                                                  │
│                                                             │
│  Pump 1 ──┐                                                 │
│  Pump 2 ──┤── PTS-2 Controller ──── LAN/WAN ──────────────────┐
│  Pump N ──┘        (WebSocket CLIENT)                       │ │
│                                                             │ │
│  Tank probes ─── PTS-2 (UploadTankMeasurement push)         │ │
└─────────────────────────────────────────────────────────────┘ │
                                                                 │
                                              ┌──────────────────┘
                                              │
                                  ┌───────────▼────────────┐
                                  │   pts_bridge            │
                                  │  (Python / asyncio)     │
                                  │                         │
                                  │  WebSocket server       │
                                  │  port 8765              │
                                  │                         │
                                  │  - Auth (Digest/Basic)  │
                                  │  - Packet routing       │
                                  │  - Pump control API     │
                                  └───────────┬────────────┘
                                              │ Odoo JSON-RPC
                                              │ (internal network)
                                  ┌───────────▼────────────┐
                                  │   Odoo 18               │
                                  │                         │
                                  │  /web/dataset/call_kw   │
                                  │                         │
                                  │  fms.pts.transaction    │
                                  │  fms.shift.meter.entry  │
                                  │  fms.dip_log (probe)    │
                                  └────────────────────────┘
```

**Key insight:** PTS-2 is always the WebSocket **client**. Your server listens; PTS-2 dials in. No static IP needed at the pump side.

---

## 2. jsonPTS Protocol Basics

### Message envelope

All messages — in both directions — use this envelope:

```json
{
  "Protocol": "jsonPTS",
  "PtsId": "003A003A3435510938393730",
  "Packets": [
    {
      "Id": 1,
      "Type": "MessageType",
      "Data": { }
    }
  ]
}
```

| Field | Notes |
|---|---|
| `Protocol` | Always `"jsonPTS"` |
| `PtsId` | Unique controller serial (24 hex chars). Use as device identity key. |
| `Packets` | Array — multiple packets per envelope allowed |
| `Id` | Packet ID; response echoes same `Id` |
| `Type` | Message type string (see §4–6) |
| `Data` | Payload object; absent in ACK responses |

### Authentication

Configured by DIP-2 switch on the controller:

| DIP-2 | Auth method |
|---|---|
| OFF | HTTP Digest (MD5) — recommended |
| ON | HTTP Basic (base64) |

For WebSocket: auth happens on the HTTP upgrade handshake.

### Transport options

| Method | Use case |
|---|---|
| WebSocket (RFC 6455) | Primary — bidirectional, pump control + uploads |
| HTTP POST to `/jsonPTS` | Alternative — upload-only, simpler but no pump control |

Use WebSocket for full integration (authorize pumps, receive transactions).

---

## 3. Message Flow — Complete Fill Cycle

```
PTS-2 (pump side)                    Bridge                    Odoo

     │                                  │                         │
     │── WebSocket connect ─────────────▶│                         │
     │   (HTTP Upgrade + Digest auth)    │                         │
     │                                  │                         │
     │── GetControllerStatus ───────────▶│                         │
     │◀─ ControllerStatus ───────────────│                         │
     │                                  │                         │
     │                                  │◀── PumpAuthorize RPC ────│  (attendant tap PDQ)
     │◀─ PumpAuthorize ──────────────────│                         │
     │   (pump, nozzle, type, dose,      │                         │
     │    price, transaction)            │                         │
     │                                  │                         │
     │── PumpAuthorizeConfirmation ──────▶│                         │
     │   (pump, transaction)             │──── store trans# ───────▶│
     │                                  │                         │
     │   [customer lifts nozzle]         │                         │
     │── PumpFillingStatus (polling) ────▶│                         │
     │   (volume, amount, flow_rate)     │──── live update ────────▶│ (optional WebSocket to UI)
     │                                  │                         │
     │   [fill complete]                 │                         │
     │── PumpEndOfTransactionStatus ─────▶│                         │
     │   (pump, nozzle, volume,          │                         │
     │    tc_volume, amount, price,      │                         │
     │    total_volume, total_amount,    │                         │
     │    date_time_start, date_time)    │                         │
     │                                  │──── create/match ───────▶│
     │                                  │     pts.transaction       │
     │◀─ PumpCloseTransaction ───────────│                         │
     │   (same transaction #)            │                         │
     │                                  │                         │
     │── UploadPumpTransaction ──────────▶│  (PTS-2 also pushes     │
     │   (full record for persistence)   │   independent copy)     │
     │                                  │──── upsert record ──────▶│
     │◀─ OK ─────────────────────────────│                         │
```

---

## 4. Pump Control Messages (Bridge → PTS-2)

### PumpAuthorize

Sent by bridge when attendant initiates a fill on PDQ/FMS.

```json
{
  "Protocol": "jsonPTS",
  "Packets": [{
    "Id": 42,
    "Type": "PumpAuthorize",
    "Data": {
      "Pump": 1,
      "Nozzle": 2,
      "Type": "Amount",
      "Dose": 5000.00,
      "Price": 187.50,
      "Transaction": 1001,
      "AutoCloseTransaction": false,
      "CustomData": "SHIFT-2026090101-ATT03"
    }
  }]
}
```

| Field | Notes |
|---|---|
| `Pump` | Logical pump number 1–100 |
| `Nozzle` | Nozzle 1–6; OR use `FuelGradeId` if grades configured |
| `Type` | `"Volume"`, `"Amount"`, or `"FullTank"` |
| `Dose` | Litres (Volume) or currency units (Amount) |
| `Price` | Per-litre price; omit if grades config has price |
| `Transaction` | Your internal reference (1–65535, wraps) |
| `AutoCloseTransaction` | `false` — close manually after confirming payment |
| `CustomData` | Shift ref + attendant ID, stored in pump log |

**Response:** `PumpAuthorizeConfirmation` with `{Pump, Transaction}`.

### PumpStop

Halt active fill (customer changes mind, overage):

```json
{
  "Protocol": "jsonPTS",
  "Packets": [{"Id": 43, "Type": "PumpStop",
    "Data": {"Pump": 1}}]
}
```

### PumpEmergencyStop

All pumps off immediately (spill, fire):

```json
{
  "Protocol": "jsonPTS",
  "Packets": [{"Id": 44, "Type": "PumpEmergencyStop", "Data": {}}]
}
```

### PumpCloseTransaction

Must be sent after `PumpEndOfTransactionStatus` to release pump for next fill:

```json
{
  "Protocol": "jsonPTS",
  "Packets": [{"Id": 45, "Type": "PumpCloseTransaction",
    "Data": {"Pump": 1, "Transaction": 1001}}]
}
```

### PumpGetStatus

Poll pump state (use only if WebSocket events insufficient):

```json
{
  "Protocol": "jsonPTS",
  "Packets": [{"Id": 46, "Type": "PumpGetStatus",
    "Data": {"Pump": 1}}]
}
```

Possible state values in response:

| State | Meaning |
|---|---|
| `Idle` | Pump ready, no active transaction |
| `Authorized` | PumpAuthorize sent, nozzle not yet lifted |
| `Filling` | Fill in progress |
| `EndOfTransaction` | Fill done, transaction still open |
| `Finished` | Transaction closed |
| `Offline` | Pump not responding |

---

## 5. Upload Messages (PTS-2 → Bridge)

These are pushed by PTS-2 independently. Bridge must ACK each with `{"Message":"OK"}`.

### UploadPumpTransaction

Triggered after every completed fill. Full authoritative record.

```json
{
  "Protocol": "jsonPTS",
  "PtsId": "003A003A3435510938393730",
  "Packets": [{
    "Id": 123,
    "Type": "UploadPumpTransaction",
    "Data": {
      "DateTimeStart": "2026-09-01T06:12:00",
      "DateTime":      "2026-09-01T06:14:35",
      "Pump": 1,
      "Nozzle": 2,
      "Tank": 3,
      "FuelGradeId": 1,
      "FuelGradeName": "Diesel",
      "Transaction": 1001,
      "Volume": 26.720,
      "TCVolume": 26.654,
      "Price": 187.50,
      "Amount": 5010.00,
      "TotalVolume": 48231.150,
      "TotalAmount": 9043341.00,
      "Tag": "",
      "UserId": 1,
      "IsOffline": false,
      "CustomData": "SHIFT-2026090101-ATT03",
      "PumpTransactionsUploaded": 47,
      "PumpTransactionsTotal": 47,
      "ConfigurationId": "1234ABCD"
    }
  }]
}
```

**Fields to store in Odoo:**

| jsonPTS field | Odoo field | Notes |
|---|---|---|
| `Transaction` | `pts_transaction_id` | PTS-2 sequence, wraps at 65535 |
| `PtsId` | `pts_device_id` | Controller serial |
| `Pump` | `pump_number` | Match to `fms.pump` record |
| `Nozzle` | `pts_nozzle` | Nozzle index |
| `Volume` | `volume` (closing reading delta) | Actual dispensed litres |
| `TCVolume` | `tc_volume` | Temperature-compensated — use for inventory |
| `Amount` | `amount` | Currency amount dispensed |
| `Price` | `price_per_litre` | Actual pump price |
| `TotalVolume` | `volume_totalizer` | Odometer — use for meter entry closing |
| `TotalAmount` | `amount_totalizer` | Odometer |
| `DateTimeStart` | `pts_start_time` | |
| `DateTime` | `pts_end_time` | |
| `CustomData` | — | Parse shift ref + attendant ID |
| `Tank` | — | Cross-check against dip entry |

**ACK required:**
```json
{
  "Protocol": "jsonPTS",
  "Packets": [{"Id": 123, "Type": "UploadPumpTransaction", "Message": "OK"}]
}
```

If bridge returns error, PTS-2 retries — idempotency is critical.

### UploadTankMeasurement

Probe data, pushed on interval (typically 1 min). Use for automatic dip entries.

```json
{
  "Protocol": "jsonPTS",
  "PtsId": "003A003A3435510938393730",
  "Packets": [{
    "Id": 124,
    "Type": "UploadTankMeasurement",
    "Data": {
      "DateTime": "2026-09-01T06:15:00",
      "Tank": 1,
      "FuelGradeId": 1,
      "FuelGradeName": "Diesel",
      "Status": "OK",
      "Alarms": [],
      "ProductHeight": 2534.1,
      "WaterHeight": 3.2,
      "Temperature": 24.7,
      "ProductVolume": 18420,
      "WaterVolume": 2,
      "ProductUllage": 6580,
      "ProductTCVolume": 18351,
      "TankFillingPercentage": 73
    }
  }]
}
```

Map to `fms.dip_log` or a new `fms.probe_reading` model:

| jsonPTS field | Odoo use |
|---|---|
| `ProductVolume` | `dip_volume` (litres) |
| `ProductTCVolume` | `tc_volume` (preferred for reconciliation) |
| `ProductHeight` | `dip_height_mm` |
| `WaterHeight` | `water_height_mm` (alert if > threshold) |
| `Temperature` | `temperature_c` |
| `Alarms` | trigger `fms.incident` if non-empty |

### UploadInTankDelivery

Pushed when probe detects delivery (volume rises). Auto-create `fms.fuel.delivery` record.

---

## 6. New Odoo Models / Fields

### 6.1 `fms.pts.device` (new model)

Tracks each physical PTS-2 controller.

```python
class FmsPtsDevice(models.Model):
    _name = 'fms.pts.device'

    pts_id        = fields.Char('PTS Serial', required=True, index=True)
    name          = fields.Char('Label')           # e.g. "Forecourt Controller A"
    last_seen     = fields.Datetime()
    ws_connected  = fields.Boolean('WS Connected')
    pump_ids      = fields.One2many('fms.pump', 'pts_device_id')
    tank_ids      = fields.One2many('stock.location', 'pts_device_id')
```

### 6.2 `fms.pts.transaction` (new model)

Raw pump transaction log, direct from PTS-2. Immutable after creation.

```python
class FmsPtsTransaction(models.Model):
    _name = 'fms.pts.transaction'

    pts_device_id       = fields.Many2one('fms.pts.device', required=True)
    pts_transaction_id  = fields.Integer('PTS Tx#', required=True)  # 1–65535
    pump_number         = fields.Integer()
    nozzle              = fields.Integer()
    tank_number         = fields.Integer()
    fuel_grade_name     = fields.Char()
    date_start          = fields.Datetime()
    date_end            = fields.Datetime()
    volume              = fields.Float(digits=(12, 3))   # dispensed
    tc_volume           = fields.Float(digits=(12, 3))   # temperature-compensated
    price               = fields.Float(digits=(12, 3))
    amount              = fields.Float(digits=(12, 2))
    volume_totalizer    = fields.Float(digits=(16, 3))   # odometer reading
    amount_totalizer    = fields.Float(digits=(16, 2))
    is_offline          = fields.Boolean()
    custom_data         = fields.Char()                  # shift ref parsed here
    shift_id            = fields.Many2one('fms.shift')   # matched on import
    meter_entry_id      = fields.Many2one('fms.shift.meter.entry')
    state               = fields.Selection([
        ('raw', 'Unmatched'),
        ('matched', 'Matched to Shift'),
        ('conflict', 'Conflict'),
    ], default='raw')

    _sql_constraints = [
        ('pts_tx_unique', 'unique(pts_device_id, pts_transaction_id)',
         'Duplicate PTS transaction'),
    ]
```

### 6.3 Fields added to `fms.shift.meter.entry`

```python
pts_transaction_id  = fields.Many2one('fms.pts.transaction', 'PTS Transaction',
                                      readonly=True)
pts_volume          = fields.Float('PTS Volume (L)', digits=(12, 3), readonly=True)
pts_tc_volume       = fields.Float('TC Volume (L)', digits=(12, 3), readonly=True)
pts_variance        = fields.Float('PTS vs Meter Var', digits=(12, 3),
                                   compute='_compute_pts_variance', store=True)
closing_totalizer   = fields.Float('Closing Totalizer', digits=(16, 3))
opening_totalizer   = fields.Float('Opening Totalizer', digits=(16, 3))
```

### 6.4 `fms.probe.reading` (new model, optional)

If automated dip-from-probe is wanted:

```python
class FmsProbeReading(models.Model):
    _name = 'fms.probe.reading'

    pts_device_id    = fields.Many2one('fms.pts.device')
    tank_number      = fields.Integer()
    tank_location_id = fields.Many2one('stock.location')
    datetime         = fields.Datetime()
    product_volume   = fields.Float(digits=(12, 0))
    tc_volume        = fields.Float(digits=(12, 0))
    height_mm        = fields.Float(digits=(8, 1))
    water_height_mm  = fields.Float(digits=(8, 1))
    temperature_c    = fields.Float(digits=(6, 1))
    alarms           = fields.Char()  # JSON array string
    shift_id         = fields.Many2one('fms.shift')
```

---

## 7. Bridge Service — `pts_bridge/`

Standalone Python process. Runs alongside Odoo, communicates via Odoo JSON-RPC.

### Directory layout

```
pts_bridge/
├── main.py          # entry point — asyncio event loop
├── server.py        # WebSocket server (websockets lib)
├── handler.py       # packet router (dispatch by Type)
├── odoo_client.py   # Odoo JSON-RPC calls
├── pump_control.py  # PumpAuthorize / PumpStop helpers
├── config.py        # env-based config
└── requirements.txt
```

### Environment variables

```
PTS_WS_HOST=0.0.0.0
PTS_WS_PORT=8765
PTS_AUTH_USER=pts
PTS_AUTH_PASS=<secret>
PTS_AUTH_METHOD=digest          # or basic
ODOO_URL=http://localhost:8069
ODOO_DB=fms
ODOO_USER=pts_bridge@fms.local
ODOO_API_KEY=<odoo-api-key>
```

### Packet routing logic

```python
HANDLERS = {
    'UploadPumpTransaction':  handle_pump_transaction,
    'UploadTankMeasurement':  handle_tank_measurement,
    'UploadInTankDelivery':   handle_delivery,
    'GetControllerStatus':    handle_status_query,
    # pump control responses
    'PumpAuthorizeConfirmation': handle_authorize_confirmation,
    'PumpEndOfTransactionStatus': handle_end_of_transaction,
    'PumpFillingStatus':      handle_filling_status,
}

async def route(ws, device_id, packet):
    handler = HANDLERS.get(packet['Type'])
    if handler:
        response = await handler(ws, device_id, packet)
        await ws.send(json.dumps(response))
    else:
        await ws.send(ack(packet['Id'], packet['Type']))
```

### Idempotency

`UploadPumpTransaction` retry-safe — always ACK even if already stored:

```python
async def handle_pump_transaction(ws, device_id, packet):
    data = packet['Data']
    try:
        odoo.create_pts_transaction(device_id, data)
    except xmlrpc.client.Fault as e:
        if 'unique' in str(e):
            pass  # duplicate, ACK anyway
        else:
            return error_response(packet['Id'], packet['Type'], str(e))
    return ack(packet['Id'], packet['Type'])
```

---

## 8. Odoo Endpoints (called by Bridge)

### 8.1 Create PTS transaction

```python
# bridge calls:
odoo.execute_kw('fms.pts.transaction', 'create_from_pts', [[{
    'pts_device_id': device_id,
    'pts_transaction_id': data['Transaction'],
    'pump_number': data['Pump'],
    'nozzle': data['Nozzle'],
    'volume': data['Volume'],
    'tc_volume': data.get('TCVolume', 0),
    'amount': data['Amount'],
    'price': data['Price'],
    'volume_totalizer': data.get('TotalVolume', 0),
    'date_start': data.get('DateTimeStart'),
    'date_end': data['DateTime'],
    'custom_data': data.get('CustomData', ''),
    'is_offline': data.get('IsOffline', False),
}]])
```

`create_from_pts` model method also attempts auto-match to open shift:

```python
@api.model
def create_from_pts(self, vals_list):
    for vals in vals_list:
        rec = self.create(vals)
        rec._try_match_shift()
    return True

def _try_match_shift(self):
    # find open shift covering self.date_end
    shift = self.env['fms.shift'].search([
        ('state', 'in', ['open', 'in_progress']),
        ('date_start', '<=', self.date_end),
    ], limit=1)
    if shift:
        self.shift_id = shift
        # find meter entry for this pump/nozzle
        entry = shift.meter_entry_ids.filtered(
            lambda e: e.pump_id.pts_pump_number == self.pump_number
                      and e.nozzle == self.nozzle
        )
        if entry:
            entry.pts_transaction_id = self
            entry.pts_volume = self.volume
            entry.pts_tc_volume = self.tc_volume
            self.state = 'matched'
```

### 8.2 Send PumpAuthorize (bridge exposes HTTP API)

FMS PDQ app or Odoo UI calls bridge REST endpoint to authorize a pump:

```
POST http://bridge:8765/api/pump/authorize
Content-Type: application/json

{
  "pump": 1,
  "nozzle": 2,
  "type": "Amount",
  "dose": 5000.00,
  "price": 187.50,
  "custom_data": "SHIFT-2026090101-ATT03"
}
```

Bridge translates to jsonPTS and sends over WebSocket. Returns:

```json
{"status": "ok", "pts_transaction": 1001}
```

---

## 9. Shift Reconciliation Impact

### Meter entry with PTS data

When `fms.shift.meter.entry` has a linked `pts_transaction_id`:

| Meter entry field | Source |
|---|---|
| `closing_reading` | `volume_totalizer` from PTS (odometer) |
| `volume_sold` | computed: closing − opening totalizer |
| `pts_volume` | `Volume` from PTS (session dispensed) |
| `pts_tc_volume` | `TCVolume` from PTS |
| `pts_variance` | `volume_sold − pts_volume` (should be ≈ 0) |

If `abs(pts_variance) > meniscus`:
- Flag on meter entry
- Require supervisor review before shift close

### Dip entry with probe data

If probe readings available (`fms.probe.reading`):
- Opening dip = last probe reading before shift start
- Closing dip = probe reading nearest shift close time
- Supervisor can override with manual dip

---

## 10. Pump ↔ FMS Mapping Config

PTS-2 uses integer pump numbers (1–100) and nozzle numbers (1–6). FMS uses `fms.pump` records.

Config fields needed on `fms.pump`:

```python
pts_pump_number  = fields.Integer('PTS Pump #')    # matches PTS-2 "Pump" field
pts_nozzle_map   = fields.Char('Nozzle Map')        # JSON: {"1": "product.diesel", "2": "product.super"}
pts_device_id    = fields.Many2one('fms.pts.device')
```

Example: Pump 1 in PTS-2 = "Pump A" in FMS, nozzle 1 = Diesel, nozzle 2 = Super Petrol.

---

## 11. Security Considerations

- Bridge should run on internal network only — never expose port 8765 to internet
- Use HTTP Digest auth (DIP-2 OFF) — Basic sends password in base64, plaintext equivalent
- Odoo API key for bridge should have minimum permissions: only `fms.pts.transaction` create + `fms.shift` read
- `fms.pts.transaction` records are immutable after creation (override `write`/`unlink` like other logs)
- `custom_data` field from pump is user-controlled — sanitize before display

---

## 12. Implementation Phases

### Phase 1 — Receive only (2–3 days)

Goal: PTS-2 transactions appear in Odoo automatically.

1. New models: `fms.pts.device`, `fms.pts.transaction`
2. Fields on `fms.pump`: `pts_pump_number`, `pts_device_id`
3. Bridge: WebSocket server, `UploadPumpTransaction` handler, Odoo create call
4. Auto-match logic `_try_match_shift`
5. View: `fms.pts.transaction` list (Forecourt → PTS Transactions)

Milestone: open shift, fuel truck, see transaction appear in Odoo within 5 seconds.

### Phase 2 — Pump control (2–3 days)

Goal: authorize pumps from PDQ app via FMS.

1. Bridge REST API endpoint `/api/pump/authorize`
2. `PumpAuthorize` + `PumpCloseTransaction` handling
3. Pump state polling (`PumpGetStatus`) via WebSocket
4. PDQ app integration (see `docs/mobile.md` §6)

Milestone: tap PDQ, pump authorizes, fill completes, transaction auto-matches to attendant.

### Phase 3 — Probe / tank automation (1–2 days)

Goal: automatic dip entries from tank probe.

1. `UploadTankMeasurement` handler
2. `fms.probe.reading` model
3. Auto-populate dip entries on shift open/close
4. Water height alert → `fms.incident`

Milestone: shift opens with pre-filled dip entries from probe; supervisor adjusts if needed.

### Phase 4 — Totalizer-based meter readings (1 day)

Goal: closing meter reading comes from pump odometer, not manual entry.

1. Store `TotalVolume` / `TotalAmount` from each transaction
2. On shift close: closing totalizer = last transaction `TotalVolume` for that pump/nozzle
3. Flag discrepancies between totalizer-derived volume and attendant-entered reading

---

## 13. Testing

### Unit tests (pts_bridge)

```python
# test_handler.py
def test_upload_pump_transaction_creates_record():
    ...

def test_duplicate_transaction_acked_not_errored():
    ...

def test_authorize_sends_correct_jsonpts():
    ...
```

### Integration test sequence

1. Start bridge in test mode (mock WebSocket, real Odoo)
2. Send sample `UploadPumpTransaction` packet
3. Assert `fms.pts.transaction` created
4. Open shift, assert transaction auto-matched
5. Check `fms.shift.meter.entry` has `pts_volume` populated

### Sample test packet

```json
{
  "Protocol": "jsonPTS",
  "PtsId": "TEST000000000000000000001",
  "Packets": [{
    "Id": 1,
    "Type": "UploadPumpTransaction",
    "Data": {
      "DateTimeStart": "2026-09-01T06:00:00",
      "DateTime":      "2026-09-01T06:04:22",
      "Pump": 1, "Nozzle": 1, "Tank": 1,
      "FuelGradeId": 1, "FuelGradeName": "Diesel",
      "Transaction": 1,
      "Volume": 26.720, "TCVolume": 26.654,
      "Price": 187.50, "Amount": 5010.00,
      "TotalVolume": 48231.150, "TotalAmount": 9043341.00,
      "Tag": "", "UserId": 1, "IsOffline": false,
      "CustomData": "SHIFT-2026090101-ATT01",
      "PumpTransactionsUploaded": 1, "PumpTransactionsTotal": 1,
      "ConfigurationId": "TESTCFG1"
    }
  }]
}
```

---

## 14. Open Questions / Decisions Needed

| # | Question | Options | Default |
|---|---|---|---|
| 1 | Auth method | Digest (secure) vs Basic (simpler) | Digest |
| 2 | Dip from probe vs manual | Auto-fill and allow override vs manual only | Auto + override |
| 3 | Pump control from Odoo UI or PDQ only | Both / PDQ only | Both |
| 4 | TC volume for inventory | Use `TCVolume` or `Volume` | `TCVolume` |
| 5 | Multi-controller support | One PTS-2 per site or many | Many (model supports it) |
| 6 | Offline fill handling | Accept `IsOffline=true` silently or flag | Flag for review |

---

*Reference: `dump/PTS-2-forecourt-controller-technical-guide.pdf`, `dump/jsonPTS protocol for PTS-2 controller.pdf` Rev 140*

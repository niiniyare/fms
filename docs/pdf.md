# FMS PDF Report Design Standard — Enterprise Guide

**Version:** 1.0  
**Date:** 2026-09-01  
**Applies to:** All Odoo 18 QWeb PDF reports in the FMS module  
**Renderer:** wkhtmltopdf 0.12.6 (Odoo 18 default)  

---

## 1. Design Philosophy

Every FMS report must feel like it came from one system, printed by one company. The design borrows from enterprise fuel industry standards (Shell, BP, TotalEnergies) and Odoo's own enterprise report kit — but made specific to Anika Global.

**Three non-negotiables:**
1. **Hierarchy** — the reader's eye moves top-to-bottom, important first
2. **Density without clutter** — fuel reports carry a lot of numbers; white space is earned, not wasted
3. **Consistency** — same margins, same font, same color rules across every single report

---

## 2. Brand Tokens

Define once in a shared SCSS/CSS file (`/static/src/css/report_base.css`). Never hardcode these values inline.

### 2.1 Color Palette

```css
:root {
  /* Primary */
  --brand-primary:   #D01F26;   /* Shell red — use for header bar, accent rules */
  --brand-dark:      #1A1A2E;   /* Near-black — headings, table headers */
  --brand-mid:       #3A3A5C;   /* Secondary text, sub-headings */

  /* Neutrals */
  --gray-100:        #F7F7F8;   /* Alternating table rows, section backgrounds */
  --gray-200:        #E8E8EE;   /* Borders, dividers */
  --gray-400:        #9999AA;   /* Muted labels, watermarks */
  --gray-700:        #444455;   /* Body text */
  --white:           #FFFFFF;

  /* Status (used in variance / gate cells only) */
  --status-ok:       #1A7F4B;   /* Green — within tolerance */
  --status-warn:     #B45309;   /* Amber — near limit */
  --status-fail:     #B91C1C;   /* Red — gate failed, over variance */
  --status-ok-bg:    #ECFDF5;
  --status-warn-bg:  #FFFBEB;
  --status-fail-bg:  #FEF2F2;
}
```

### 2.2 Typography

Single font family across all reports. Use the Google Fonts embed or bundle locally.

```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

body {
  font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif;
  font-size: 9pt;
  color: var(--gray-700);
  line-height: 1.45;
}
```

| Element | Size | Weight | Color |
|---|---|---|---|
| Report title | 18pt | 700 | white (on brand header) |
| Section heading | 11pt | 600 | `--brand-dark` |
| Sub-heading | 9pt | 600 | `--brand-mid` |
| Body text | 9pt | 400 | `--gray-700` |
| Table header | 8pt | 600 | white (on `--brand-dark` bg) |
| Table data | 8.5pt | 400 | `--gray-700` |
| Table data — numeric | 8.5pt | 500 | `--brand-dark` (monospace stack) |
| Muted label | 8pt | 400 | `--gray-400` |
| Footer text | 7.5pt | 400 | `--gray-400` |
| Status badge | 7.5pt | 600 | status color |

Numeric columns use monospace stack for alignment:
```css
.num { font-family: 'Inter', 'Courier New', monospace; }
```

---

## 3. Page Layout

### 3.1 Page Setup

```css
@page {
  size: A4 portrait;           /* default; landscape for wide tables */
  margin: 14mm 14mm 18mm 14mm; /* top right bottom left */

  @bottom-center {
    content: element(footer);
  }
}

@page :first {
  margin-top: 0;               /* header bleeds to edge on page 1 */
}
```

### 3.2 Grid

All content sits on a **12-column grid** (invisible, enforced via percentage widths).

```
|─────────────────────────────────────────────|
| 14mm margin                      14mm margin |
|  [col1] [col2] [col3] ... [col12]            |
|─────────────────────────────────────────────|
```

Common layouts:

| Pattern | Use |
|---|---|
| 12/12 (full width) | Tables, section blocks |
| 8/4 | Info block left + summary box right |
| 6/6 | Two equal info columns |
| 4/4/4 | Three KPI tiles |
| 9/3 | Narrative left + stamp/signature right |

### 3.3 Vertical Rhythm

- Between sections: `24px` gap (`margin-bottom: 24px`)
- Between sub-sections: `12px`
- Between label and value in a block: `2px`
- Table row height: `22px` minimum

---

## 4. Page Structure (Every Report)

```
┌──────────────────────────────────────────────────────────┐
│  HEADER BAND (full bleed, brand-primary background)      │
│  ┌────────────────────────────┐  ┌─────────────────────┐ │
│  │ Company logo (white SVG)   │  │ Report Title        │ │
│  │ Company name               │  │ Report sub-title    │ │
│  └────────────────────────────┘  └─────────────────────┘ │
├──────────────────────────────────────────────────────────┤
│  META ROW  (gray-100 band, 1 line)                       │
│  Shift: MORNING │ Date: 01 Sep 2026 │ Ref: SH-0291 │ ... │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  BODY (white, content sections)                          │
│                                                          │
│  [Section A]                                             │
│  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ │
│  [Section B]                                             │
│                                                          │
├──────────────────────────────────────────────────────────┤
│  FOOTER (every page)                                     │
│  Printed: 01 Sep 2026 09:15  │  Page 1 of 3  │  CONFID. │
└──────────────────────────────────────────────────────────┘
```

---

## 5. Component Specifications

### 5.1 Header Band

```xml
<div class="report-header">
  <div class="header-logo">
    <img t-att-src="'/web/binary/company_logo'" alt="Logo"/>
    <div class="company-name">
      <span t-esc="company.name"/>
      <span class="company-sub" t-esc="company.street"/>
    </div>
  </div>
  <div class="header-title">
    <h1 t-esc="report_title"/>
    <p class="report-sub" t-esc="report_subtitle"/>
  </div>
</div>
```

```css
.report-header {
  background: var(--brand-primary);
  color: var(--white);
  padding: 14px 14mm;
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 0 -14mm;          /* bleed to page edge */
}

.report-header h1 {
  font-size: 18pt;
  font-weight: 700;
  margin: 0;
  letter-spacing: -0.3px;
}

.report-header img {
  height: 36px;
  filter: brightness(0) invert(1);   /* force white logo */
}

.company-name {
  font-size: 8.5pt;
  font-weight: 500;
  opacity: 0.85;
  margin-top: 2px;
}

.report-sub {
  font-size: 9pt;
  opacity: 0.75;
  margin: 4px 0 0;
}
```

### 5.2 Meta Row

Single thin band immediately below header. Always one line.

```xml
<div class="meta-row">
  <span><b>Shift:</b> <t t-esc="shift.name"/></span>
  <span class="sep">│</span>
  <span><b>Date:</b> <t t-esc="shift.date"/></span>
  <span class="sep">│</span>
  <span><b>Ref:</b> <t t-esc="shift.reference"/></span>
  <span class="sep">│</span>
  <span><b>Station:</b> <t t-esc="shift.site_id.name"/></span>
  <span class="sep">│</span>
  <span><b>Status:</b>
    <span t-attf-class="badge badge-{{ shift.state }}">
      <t t-esc="shift.state_label"/>
    </span>
  </span>
</div>
```

```css
.meta-row {
  background: var(--gray-100);
  border-bottom: 1px solid var(--gray-200);
  padding: 6px 0;
  font-size: 8pt;
  color: var(--gray-700);
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.meta-row b { color: var(--brand-dark); }
.meta-row .sep { color: var(--gray-400); }
```

### 5.3 Section Block

Every logical group of data is wrapped in a section block.

```xml
<div class="section">
  <div class="section-header">
    <h2>Meter Readings</h2>
    <span class="section-badge">4 pumps</span>
  </div>
  <div class="section-body">
    <!-- table or content here -->
  </div>
</div>
```

```css
.section {
  margin-bottom: 24px;
  page-break-inside: avoid;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 2px solid var(--brand-primary);
  padding-bottom: 4px;
  margin-bottom: 10px;
}

.section-header h2 {
  font-size: 11pt;
  font-weight: 600;
  color: var(--brand-dark);
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.4px;
}

.section-badge {
  font-size: 7.5pt;
  font-weight: 600;
  background: var(--gray-200);
  color: var(--brand-mid);
  padding: 2px 8px;
  border-radius: 10px;
}
```

### 5.4 Info Block (Key-Value Pairs)

Used for shift details, customer info, document references.

```xml
<div class="info-grid">
  <div class="info-item">
    <span class="info-label">Opened By</span>
    <span class="info-value" t-esc="shift.opened_by.name"/>
  </div>
  <div class="info-item">
    <span class="info-label">Opening Time</span>
    <span class="info-value" t-esc="shift.time_open"/>
  </div>
  <!-- ... -->
</div>
```

```css
.info-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px 16px;
  margin-bottom: 20px;
}

.info-item {
  display: flex;
  flex-direction: column;
}

.info-label {
  font-size: 7.5pt;
  font-weight: 600;
  color: var(--gray-400);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 1px;
}

.info-value {
  font-size: 9pt;
  font-weight: 500;
  color: var(--brand-dark);
}
```

### 5.5 Data Tables

The most used component. Every table follows this exact pattern.

```xml
<table class="report-table">
  <thead>
    <tr>
      <th>Pump</th>
      <th>Product</th>
      <th class="text-right">Opening (L)</th>
      <th class="text-right">Closing (L)</th>
      <th class="text-right">Volume Sold (L)</th>
      <th class="text-right">Amount (KES)</th>
    </tr>
  </thead>
  <tbody>
    <t t-foreach="entries" t-as="e">
      <tr t-attf-class="{{ e_index % 2 == 0 and 'row-even' or 'row-odd' }}">
        <td t-esc="e.pump_id.name"/>
        <td t-esc="e.product_id.name"/>
        <td class="text-right num" t-esc="'%.2f' % e.opening_volume"/>
        <td class="text-right num" t-esc="'%.2f' % e.closing_volume"/>
        <td class="text-right num" t-esc="'%.2f' % e.volume_sold"/>
        <td class="text-right num" t-esc="'%.2f' % e.amount"/>
      </tr>
    </t>
  </tbody>
  <tfoot>
    <tr class="totals-row">
      <td colspan="4"><b>Total</b></td>
      <td class="text-right num"><t t-esc="'%.2f' % total_volume"/></td>
      <td class="text-right num"><t t-esc="'%.2f' % total_amount"/></td>
    </tr>
  </tfoot>
</table>
```

```css
.report-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 8.5pt;
  margin-bottom: 0;
}

.report-table thead tr {
  background: var(--brand-dark);
  color: var(--white);
}

.report-table thead th {
  padding: 7px 8px;
  font-size: 8pt;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.3px;
  border: none;
  white-space: nowrap;
}

.report-table tbody tr.row-even { background: var(--white); }
.report-table tbody tr.row-odd  { background: var(--gray-100); }

.report-table tbody td {
  padding: 6px 8px;
  border-bottom: 1px solid var(--gray-200);
  color: var(--gray-700);
  vertical-align: middle;
}

.report-table tfoot .totals-row {
  background: var(--gray-100);
  border-top: 2px solid var(--brand-dark);
}

.report-table tfoot td {
  padding: 7px 8px;
  font-size: 8.5pt;
  font-weight: 600;
  color: var(--brand-dark);
}

.text-right { text-align: right; }
.text-center { text-align: center; }
.num { font-variant-numeric: tabular-nums; }

/* Column width hints — adjust per report */
.col-narrow  { width: 6%; }
.col-medium  { width: 12%; }
.col-wide    { width: 22%; }
```

### 5.6 KPI Summary Tiles

Used at top of shift summary, dip summary, cash reconciliation.

```xml
<div class="kpi-row">
  <div class="kpi-tile">
    <span class="kpi-label">Total Fuel Sold</span>
    <span class="kpi-value"><t t-esc="'%.0f' % total_litres"/> L</span>
    <span class="kpi-sub">All products combined</span>
  </div>
  <div class="kpi-tile">
    <span class="kpi-label">Total Revenue</span>
    <span class="kpi-value">KES <t t-esc="'{:,.0f}'.format(total_revenue)"/></span>
    <span class="kpi-sub">Before deductions</span>
  </div>
  <div class="kpi-tile kpi-tile--status-ok">
    <span class="kpi-label">FC Cash Variance</span>
    <span class="kpi-value">KES 0.00</span>
    <span class="kpi-sub">Gate: PASSED</span>
  </div>
</div>
```

```css
.kpi-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 24px;
}

.kpi-tile {
  background: var(--gray-100);
  border: 1px solid var(--gray-200);
  border-left: 4px solid var(--brand-primary);
  border-radius: 4px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
}

.kpi-tile--status-ok   { border-left-color: var(--status-ok); background: var(--status-ok-bg); }
.kpi-tile--status-warn { border-left-color: var(--status-warn); background: var(--status-warn-bg); }
.kpi-tile--status-fail { border-left-color: var(--status-fail); background: var(--status-fail-bg); }

.kpi-label {
  font-size: 7.5pt;
  font-weight: 600;
  color: var(--gray-400);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.kpi-value {
  font-size: 16pt;
  font-weight: 700;
  color: var(--brand-dark);
  margin: 4px 0 2px;
  line-height: 1.1;
}

.kpi-sub {
  font-size: 7.5pt;
  color: var(--gray-400);
}
```

### 5.7 Variance / Status Badges

```css
.badge {
  display: inline-block;
  padding: 2px 7px;
  border-radius: 10px;
  font-size: 7pt;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.4px;
}

.badge-ok, .badge-closed, .badge-passed {
  background: var(--status-ok-bg);
  color: var(--status-ok);
}

.badge-warn, .badge-open, .badge-pending {
  background: var(--status-warn-bg);
  color: var(--status-warn);
}

.badge-fail, .badge-draft, .badge-failed {
  background: var(--status-fail-bg);
  color: var(--status-fail);
}

/* Variance cell coloring */
.variance-ok   { color: var(--status-ok);   font-weight: 600; }
.variance-warn { color: var(--status-warn); font-weight: 600; }
.variance-fail { color: var(--status-fail); font-weight: 700; }
```

### 5.8 Signature / Approval Block

Always at bottom of shift close report and dip report.

```xml
<div class="signature-row">
  <div class="sig-box">
    <div class="sig-line"/>
    <span class="sig-name" t-esc="shift.opened_by.name"/>
    <span class="sig-role">Shift Attendant</span>
  </div>
  <div class="sig-box">
    <div class="sig-line"/>
    <span class="sig-name" t-esc="shift.supervisor_id.name"/>
    <span class="sig-role">Supervisor</span>
  </div>
  <div class="sig-box">
    <div class="sig-line"/>
    <span class="sig-name">________________________</span>
    <span class="sig-role">Station Manager</span>
  </div>
</div>
```

```css
.signature-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
  margin-top: 36px;
  page-break-inside: avoid;
}

.sig-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.sig-line {
  width: 100%;
  border-bottom: 1px solid var(--brand-dark);
  margin-bottom: 6px;
  height: 36px;
}

.sig-name {
  font-size: 8.5pt;
  font-weight: 600;
  color: var(--brand-dark);
}

.sig-role {
  font-size: 7.5pt;
  color: var(--gray-400);
  margin-top: 2px;
}
```

### 5.9 Page Footer

Appears on every page via `@bottom-center`.

```xml
<div id="footer" class="report-footer">
  <span>
    Printed: <t t-esc="current_datetime"/>
    &nbsp;│&nbsp;
    <t t-esc="company.name"/>
  </span>
  <span>
    Page <span class="page"/> of <span class="topage"/>
  </span>
  <span class="footer-confidential">CONFIDENTIAL</span>
</div>
```

```css
#footer {
  position: running(footer);
}

.report-footer {
  border-top: 1px solid var(--gray-200);
  padding-top: 5px;
  display: flex;
  justify-content: space-between;
  font-size: 7.5pt;
  color: var(--gray-400);
}

.footer-confidential {
  font-size: 7pt;
  font-weight: 700;
  letter-spacing: 0.8px;
  color: var(--gray-400);
}
```

---

## 6. Page Numbering & Multi-Page Rules

```css
/* wkhtmltopdf page counter */
.page::before    { content: counter(page); }
.topage::before  { content: counter(pages); }

/* Prevent orphan rows */
.report-table tbody tr { page-break-inside: avoid; }

/* Keep section header with first 3 rows */
.section { page-break-inside: avoid; }

/* Force new page before major sections on long reports */
.page-break-before { page-break-before: always; }

/* Repeat table header on each page */
.report-table thead { display: table-header-group; }
.report-table tfoot { display: table-footer-group; }
```

---

## 7. Report-Specific Specifications

### 7.1 Shift Close Report (`report_shift_close`)

**Page:** A4 Portrait  
**Sections order:**

```
1. Header band
2. Meta row (shift ref, date, time, station, status)
3. KPI tiles × 3: Total Fuel Sold | Total Revenue | FC Cash Variance
4. Section: Meter Readings (table)
5. Section: Tank Dip & Stock Variance (table)
6. Section: Attendant Cash Reconciliation (table)
7. Section: Residual Allocations (table — if any)
8. Section: Payment Summary (cash / MPesa / card / credit breakdown)
9. Signature block (3 cols: Attendant, Supervisor, Manager)
10. Footer
```

**Variance coloring rule for dip table:**

| Condition | Cell class |
|---|---|
| `abs(variance%) <= 0.3` | `variance-ok` |
| `0.3 < abs(variance%) <= 0.5` | `variance-warn` |
| `abs(variance%) > 0.5` | `variance-fail` |

### 7.2 Dip Log Report (`report_dip_log`)

**Page:** A4 Portrait  
**Sections order:**

```
1. Header band
2. Meta row (tank, product, date range)
3. KPI tiles × 3: Opening Stock | Deliveries | Closing Stock
4. Section: Dip Log Table (date, opening, delivery, closing, variance, dip source)
5. Section: Chart placeholder (future: SVG line chart of stock trend)
6. Signature block (2 cols: Supervisor, Manager)
7. Footer
```

### 7.3 Meter Log Report (`report_meter_log`)

**Page:** A4 Landscape  
**Sections order:**

```
1. Header band
2. Meta row (pump, nozzle, product, date range)
3. KPI tiles × 4: Total Litres | Total Revenue | Avg. Daily | Txn Count
4. Section: Meter Log Table
5. Footer
```

Landscape CSS:
```css
@page { size: A4 landscape; margin: 12mm 14mm 18mm 14mm; }
```

### 7.4 Attendant Statement (`report_attendant_statement`)

**Page:** A4 Portrait  
**Sections order:**

```
1. Header band
2. Meta row (attendant, shift, date)
3. KPI tiles × 3: Total Sales | Collected | Variance
4. Section: Transaction List (pump, product, volume, amount, payment method, time)
5. Section: Payment Method Summary (subtotals by method)
6. Signature block (2 cols: Attendant, Supervisor)
7. Footer
```

### 7.5 Fuel Delivery Note (`report_delivery_note`)

**Page:** A4 Portrait  
**Sections order:**

```
1. Header band
2. Meta row (delivery ref, date, supplier, truck)
3. Info grid (2-col): Supplier details | Delivery details
4. Section: Products Delivered (table)
5. Section: Dip Before vs After (table)
6. KPI: Net Volume Received | Variance vs. Invoice
7. Signature block (3 cols: Driver, Supervisor, Manager)
8. Footer
```

### 7.6 Fuel Tank Status Report (`report_tank_status`)

**Page:** A4 Landscape  

```
1. Header band
2. Meta row (date/time of snapshot)
3. Section: Tank Status Table
   Cols: Tank | Product | Capacity | Current Level | % Full | Days to Empty | Status
4. Footer
```

Status badge rules:

| % Full | Badge |
|---|---|
| > 50% | `badge-ok` |
| 20–50% | `badge-warn` |
| < 20% | `badge-fail` |

---

## 8. QWeb Base Template Structure

All reports inherit from one base layout. Never copy-paste the header/footer — inherit.

```xml
<!-- /views/report_base_layout.xml -->
<template id="report_fms_base_layout" inherit_id="web.basic_layout">
  <xpath expr="//div[@id='wkhtmltopdf_wrapper']" position="replace">
    <div id="wkhtmltopdf_wrapper">
      <t t-call-assets="fms.assets_report_pdf" t-js="false"/>
      <t t-out="0"/>
    </div>
  </xpath>
</template>

<!-- Each report: -->
<template id="report_shift_close">
  <t t-call="fms.report_fms_base_layout">
    <t t-set="report_title">Shift Close Report</t>
    <t t-set="report_subtitle" t-value="shift.name"/>

    <!-- Header band -->
    <t t-call="fms.report_component_header"/>

    <!-- Meta row -->
    <t t-call="fms.report_component_meta_row"/>

    <!-- Body -->
    <div class="container-fluid mt-3">
      <!-- KPI tiles -->
      <t t-call="fms.report_component_kpi_tiles"/>

      <!-- Sections -->
      <div class="section">
        <div class="section-header"><h2>Meter Readings</h2></div>
        <div class="section-body">
          <!-- table -->
        </div>
      </div>

      <!-- Signature -->
      <t t-call="fms.report_component_signature"/>
    </div>
  </t>
</template>
```

---

## 9. Asset Registration

```xml
<!-- /views/assets.xml -->
<record id="assets_report_pdf" model="ir.asset">
  <field name="name">FMS PDF Report Styles</field>
  <field name="bundle">fms.assets_report_pdf</field>
  <field name="path">fms/static/src/css/report_base.css</field>
</record>
```

File structure:
```
fms/
  static/
    src/
      css/
        report_base.css        ← all tokens, layout, components
      fonts/
        Inter-Regular.woff2    ← bundled locally (no network in wkhtmltopdf)
        Inter-Medium.woff2
        Inter-SemiBold.woff2
        Inter-Bold.woff2
```

Bundle fonts locally — wkhtmltopdf cannot reach Google Fonts at render time in production.

```css
@font-face {
  font-family: 'Inter';
  src: url('/fms/static/src/fonts/Inter-Regular.woff2') format('woff2');
  font-weight: 400;
}
@font-face {
  font-family: 'Inter';
  src: url('/fms/static/src/fonts/Inter-Medium.woff2') format('woff2');
  font-weight: 500;
}
/* repeat for 600, 700 */
```

---

## 10. Number Formatting Rules

Consistency in how numbers display — no mixing of formats.

| Type | Format | Example |
|---|---|---|
| Currency (KES) | `KES {:,.2f}` | KES 187,500.00 |
| Volume (litres) | `{:,.3f} L` | 27.453 L |
| Percentage | `{:.2f}%` | 0.43% |
| Count / units | `{:,d}` | 1,024 |
| Large currency | `KES {:,.0f}` | KES 1,200,000 |

In QWeb:
```xml
<!-- Currency -->
<t t-esc="'KES {:,.2f}'.format(amount)"/>

<!-- Volume -->
<t t-esc="'{:,.3f} L'.format(volume)"/>

<!-- Percentage -->
<t t-esc="'{:.2f}%'.format(variance_pct)"/>
```

Never show raw floats like `187500.0` or `0.4345678`.

---

## 11. Common Mistakes to Avoid

| Mistake | Rule |
|---|---|
| Hardcoding `KES` in labels | Use `company_id.currency_id.symbol` |
| Different font per report | Always Inter — never Arial on one, Helvetica on another |
| Inline `style=""` attributes | Use CSS classes only |
| Tables without `thead` repeat | Always `display: table-header-group` on thead |
| Missing `page-break-inside: avoid` on signature block | Signature must never split across pages |
| Color values hardcoded | Always CSS variable references |
| `0.5%` variance shown as `0.500000%` | Always format to 2dp |
| Logo not white on red header | Always apply `filter: brightness(0) invert(1)` |
| No footer on multi-page | Test every report with > 1 page of data |
| Section heading without bottom border | `border-bottom: 2px solid var(--brand-primary)` is mandatory |

---

## 12. QA Checklist (Before Any Report Ships)

```
Visual
  [ ] Header band: logo visible, title readable, brand-primary background
  [ ] Meta row: all key fields present, no overflow
  [ ] KPI tiles: correct values, correct status color
  [ ] Tables: striped rows, dark header, totals row distinct
  [ ] Variance cells: color matches threshold rules
  [ ] Signature block: three lines, roles labeled, not split across pages
  [ ] Footer: date, page count, CONFIDENTIAL — every page

Multi-page
  [ ] Table headers repeat on page 2+
  [ ] Footer appears on page 2+
  [ ] No orphan section heading at bottom of page

Numbers
  [ ] All currency KES {:,.2f}
  [ ] All volumes {:,.3f} L
  [ ] No raw floats

Print test
  [ ] Print to PDF from Odoo — no layout breakage
  [ ] Print to physical printer — margins sufficient, not cut off
  [ ] Logo prints correctly (white on color = prints as white on red)
```

---

*End of document.*

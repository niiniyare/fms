"""
FMS Workspace builder — run after adding any new DocType:

    bench --site fms.local execute fms.utils.create_workspace.create_fms_workspace

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOW TO ADD A NEW DOCTYPE TO THE WORKSPACE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. SHORTCUT (top quick-access button):
   Add a tuple to SHORTCUT_ITEMS:
       ("My DocType Label", "DocType", "Actual DocType Name"),
   Col width is always 3 (4 per row). Use "Report" type for reports:
       ("Sales Report", "Report", "Daily Shift Summary"),

2. CARD LINK (appears inside a card group in Masters & Reports):
   Add a tuple to the matching group inside CARD_GROUPS, or create a new group:
       ("Display Label", "Actual DocType Name"),
   To add a new card group:
       ("New Group Name", [
           ("Label", "DocType Name"),
       ]),

3. NUMBER CARD (KPI tile at the very top):
   Add a dict to NUMBER_CARDS:
       {
           "name":          "FMS My Metric",       # unique name stored in DB
           "label":         "My Metric",            # display label
           "type":          "Document Type",
           "document_type": "My DocType",
           "filters_json":  json.dumps([["My DocType", "status", "=", "Active"]]),
           "color":         "#318AD8",              # hex color
           "is_public":     1,
           "module":        "Forecourt Management System",
       },
   Leave aggregate_function_based_on empty for COUNT.
   Set it (e.g. "grand_total") for SUM of a numeric field.

4. After editing this file, run the bench execute command above to rebuild.
   The old workspace is deleted and recreated — this is always safe to re-run.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import json
import random
import string

import frappe
from frappe.utils import now_datetime


def _rid():
    return "".join(random.choices(string.ascii_letters + string.digits, k=10))


# ── Number cards ──────────────────────────────────────────────────────────────
NUMBER_CARDS = [
    {
        "name":          "FMS Open Shifts",
        "label":         "Open Shifts",
        "type":          "Document Type",
        "document_type": "Shift",
        "filters_json":  json.dumps([["Shift", "status", "in", ["Open", "Readings Captured"]]]),
        "color":         "#4966F1",
        "is_public":     1,
        "module":        "Forecourt Management System",
    },
    {
        "name":          "FMS Active Pumps",
        "label":         "Active Pumps",
        "type":          "Document Type",
        "document_type": "Pump",
        "filters_json":  json.dumps([["Pump", "is_active", "=", "1"]]),
        "color":         "#318AD8",
        "is_public":     1,
        "module":        "Forecourt Management System",
    },
    {
        "name":          "FMS Open Alerts",
        "label":         "Open Alerts",
        "type":          "Document Type",
        "document_type": "Forecourt Alert",
        "filters_json":  json.dumps([["Forecourt Alert", "status", "=", "Open"]]),
        "color":         "#E8503A",
        "is_public":     1,
        "module":        "Forecourt Management System",
    },
    {
        "name":          "FMS Shifts Today",
        "label":         "Shifts Today",
        "type":          "Document Type",
        "document_type": "Shift",
        "filters_json":  json.dumps([["Shift", "shift_date", "=", "Today"]]),
        "color":         "#7B3FC4",
        "is_public":     1,
        "module":        "Forecourt Management System",
    },
]

# ── Shortcuts ─────────────────────────────────────────────────────────────────
SHORTCUT_ITEMS = [
    ("Shift",                      "DocType", "Shift"),
    ("Pump",                       "DocType", "Pump"),
    ("Meter Reading",              "DocType", "Meter Reading"),
    ("Tank Dip Reading",           "DocType", "Tank Dip Reading"),
    ("Cashier Session",            "DocType", "Cashier Session"),
    ("Cash Event",                 "DocType", "Cash Event"),
    ("Shift Reconciliation",       "DocType", "Shift Reconciliation"),
    ("Meter Validation Result",    "DocType", "Meter Validation Result"),
    ("Tank Calibration Chart",     "DocType", "Tank Calibration Chart"),
    ("Fuel Delivery Dip",          "DocType", "Fuel Delivery Dip"),
    ("Fleet Card",                 "DocType", "Fleet Card"),
    ("Drive-Off Record",           "DocType", "Drive-Off Record"),
    ("Forecourt Alert",            "DocType", "Forecourt Alert"),
    ("Forecourt Site Preferences", "DocType", "Forecourt Site Preferences"),
]

# ── Card groups (links child table) ───────────────────────────────────────────
CARD_GROUPS = [
    ("Operations", [
        ("Shift",                  "Shift"),
        ("Meter Reading",          "Meter Reading"),
        ("Tank Dip Reading",       "Tank Dip Reading"),
        ("Cashier Session",        "Cashier Session"),
        ("Cash Event",             "Cash Event"),
        ("Shift Reconciliation",   "Shift Reconciliation"),
        ("Meter Validation",       "Meter Validation Result"),
    ]),
    ("Master Data", [
        ("Pump",                   "Pump"),
        ("Calibration Chart",      "Tank Calibration Chart"),
        ("Fleet Card",             "Fleet Card"),
        ("Site Preferences",       "Forecourt Site Preferences"),
    ]),
    ("Incidents & Analysis", [
        ("Fuel Delivery",          "Fuel Delivery Dip"),
        ("Drive-Off Record",       "Drive-Off Record"),
        ("Forecourt Alert",        "Forecourt Alert"),
    ]),
]


def _build_content():
    blocks = []

    # KPI number cards (col=3 each → 4 per row)
    for card in NUMBER_CARDS:
        blocks.append({
            "id": _rid(), "type": "number_card",
            "data": {"number_card_name": card["name"], "col": 3},
        })

    blocks.append({"id": _rid(), "type": "spacer", "data": {"col": 12}})

    # Shortcuts section
    blocks.append({
        "id": _rid(), "type": "header",
        "data": {"text": '<span class="h4"><b>Quick Access</b></span>', "col": 12},
    })
    for label, _stype, _link in SHORTCUT_ITEMS:
        blocks.append({
            "id": _rid(), "type": "shortcut",
            "data": {"shortcut_name": label, "col": 3},
        })

    blocks.append({"id": _rid(), "type": "spacer", "data": {"col": 12}})

    # Cards / links section
    blocks.append({
        "id": _rid(), "type": "header",
        "data": {"text": '<span class="h4"><b>Masters &amp; Reports</b></span>', "col": 12},
    })
    for card_label, _items in CARD_GROUPS:
        blocks.append({
            "id": _rid(), "type": "card",
            "data": {"card_name": card_label, "col": 4},
        })

    return json.dumps(blocks)


def _upsert_number_cards(now):
    """Create FMS Number Card records if they don't exist."""
    for card in NUMBER_CARDS:
        if frappe.db.exists("Number Card", card["name"]):
            continue
        frappe.db.sql("""
            INSERT INTO `tabNumber Card`
                (name, creation, modified, modified_by, owner, docstatus,
                 label, type, document_type, filters_json, color,
                 is_public, module, is_standard, show_percentage_stats)
            VALUES (%s, %s, %s, 'Administrator', 'Administrator', 0,
                    %s, %s, %s, %s, %s,
                    %s, %s, 0, 0)
        """, (
            card["name"], now, now,
            card["label"], card["type"], card["document_type"],
            card["filters_json"], card.get("color", ""),
            card["is_public"], card["module"],
        ))


def create_fms_workspace():
    ws_name = "Forecourt Management System"
    now = now_datetime()

    # Ensure Number Card records exist
    _upsert_number_cards(now)

    # Delete existing workspace
    if frappe.db.exists("Workspace", ws_name):
        frappe.delete_doc("Workspace", ws_name, force=True)
        frappe.db.commit()

    # Insert main Workspace record directly (avoids validate() permission race)
    frappe.db.sql("""
        INSERT INTO `tabWorkspace`
            (name, creation, modified, modified_by, owner, docstatus,
             label, title, module, public, icon, content, sequence_id)
        VALUES (%s, %s, %s, 'Administrator', 'Administrator', 0,
                %s, %s, %s, 1, 'tool', %s, 99)
    """, (ws_name, now, now, ws_name, ws_name,
          "Forecourt Management System", _build_content()))

    # Insert Workspace Number Card child rows
    for idx, card in enumerate(NUMBER_CARDS, start=1):
        frappe.db.sql("""
            INSERT INTO `tabWorkspace Number Card`
                (name, creation, modified, modified_by, owner, docstatus, idx,
                 number_card_name, label,
                 parent, parentfield, parenttype)
            VALUES (%s, %s, %s, 'Administrator', 'Administrator', 0, %s,
                    %s, %s,
                    %s, 'number_cards', 'Workspace')
        """, (frappe.generate_hash(length=10), now, now, idx,
              card["name"], card["label"], ws_name))

    # Insert shortcuts child rows
    for idx, (label, stype, link_to) in enumerate(SHORTCUT_ITEMS, start=1):
        frappe.db.sql("""
            INSERT INTO `tabWorkspace Shortcut`
                (name, creation, modified, modified_by, owner, docstatus, idx,
                 label, type, link_to,
                 parent, parentfield, parenttype)
            VALUES (%s, %s, %s, 'Administrator', 'Administrator', 0, %s,
                    %s, %s, %s,
                    %s, 'shortcuts', 'Workspace')
        """, (frappe.generate_hash(length=10), now, now, idx,
              label, stype, link_to, ws_name))

    # Insert links child rows (Card Break + Link entries)
    link_idx = 1
    for card_label, items in CARD_GROUPS:
        frappe.db.sql("""
            INSERT INTO `tabWorkspace Link`
                (name, creation, modified, modified_by, owner, docstatus, idx,
                 type, label, link_to, link_type,
                 parent, parentfield, parenttype)
            VALUES (%s, %s, %s, 'Administrator', 'Administrator', 0, %s,
                    'Card Break', %s, NULL, NULL,
                    %s, 'links', 'Workspace')
        """, (frappe.generate_hash(length=10), now, now, link_idx,
              card_label, ws_name))
        link_idx += 1

        for link_label, link_to in items:
            frappe.db.sql("""
                INSERT INTO `tabWorkspace Link`
                    (name, creation, modified, modified_by, owner, docstatus, idx,
                     type, label, link_to, link_type,
                     parent, parentfield, parenttype)
                VALUES (%s, %s, %s, 'Administrator', 'Administrator', 0, %s,
                        'Link', %s, %s, 'DocType',
                        %s, 'links', 'Workspace')
            """, (frappe.generate_hash(length=10), now, now, link_idx,
                  link_label, link_to, ws_name))
            link_idx += 1

    frappe.db.commit()

    sc = frappe.db.count("Workspace Shortcut", {"parent": ws_name})
    lc = frappe.db.count("Workspace Link", {"parent": ws_name})
    nc = frappe.db.count("Workspace Number Card", {"parent": ws_name})
    print(f"Workspace rebuilt: {ws_name} | shortcuts={sc} links={lc} number_cards={nc}")

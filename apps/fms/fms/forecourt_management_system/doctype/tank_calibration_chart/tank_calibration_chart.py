import frappe
from frappe.model.document import Document


class TankCalibrationChart(Document):
    pass


def interpolate(chart_name, dip_mm):
    rows = frappe.db.get_all(
        "Calibration Chart Row",
        filters={"parent": chart_name},
        fields=["height_mm", "volume_litres"],
        order_by="height_mm asc",
    )
    if not rows:
        frappe.throw(f"No calibration data for chart {chart_name}")
    if dip_mm > rows[-1].height_mm:
        frappe.throw(
            f"Dip {dip_mm} mm exceeds calibrated range ({rows[-1].height_mm} mm). "
            "Update calibration chart."
        )
    if dip_mm <= rows[0].height_mm:
        return rows[0].volume_litres
    for i in range(len(rows) - 1):
        lo, hi = rows[i], rows[i + 1]
        if lo.height_mm <= dip_mm <= hi.height_mm:
            t = (dip_mm - lo.height_mm) / (hi.height_mm - lo.height_mm)
            return lo.volume_litres + t * (hi.volume_litres - lo.volume_litres)
    return rows[-1].volume_litres

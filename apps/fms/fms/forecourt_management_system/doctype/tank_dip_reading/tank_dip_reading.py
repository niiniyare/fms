import frappe
from frappe.model.document import Document
from fms.forecourt_management_system.doctype.tank_calibration_chart.tank_calibration_chart import interpolate
from fms.utils.alerts import create_alert


class TankDipReading(Document):
    def before_submit(self):
        self.volume_observed_l = interpolate(self.calibration_chart, self.dip_height_mm)
        if (self.water_level_mm or 0) > 20:
            create_alert(
                self.shift,
                f"High water in {self.tank}: {self.water_level_mm} mm",
                "Water in Tank",
                "Critical",
            )

"""Single place for the water-quality thresholds.

Override with environment variables if your plant uses different limits.
"""
import os

DO_WARN = float(os.getenv("DO_WARN", "2.0"))      # mg/L: below this -> warning
DO_CRIT = float(os.getenv("DO_CRIT", "1.0"))      # mg/L: below this -> critical
COD_WARN = float(os.getenv("COD_WARN", "400"))    # mg/L: above this -> warning
TEMP_WARN = float(os.getenv("TEMP_WARN", "35"))   # deg C: above this -> warning

LABELS = {"ok": "ปกติ", "warn": "ควรเฝ้าระวัง", "crit": "วิกฤต"}
_RANK = {"ok": 0, "warn": 1, "crit": 2}


def evaluate(current_do, influent_cod, water_temp):
    """Return {"level", "label", "issues"} for one reading."""
    level = "ok"
    issues = []

    def raise_to(new_level):
        nonlocal level
        if _RANK[new_level] > _RANK[level]:
            level = new_level

    if current_do < DO_CRIT:
        raise_to("crit")
        issues.append(f"ออกซิเจนละลายน้ำ (DO) ต่ำมาก ({current_do:.2f} mg/L) จุลินทรีย์อาจขาดออกซิเจน ควรตรวจสอบเครื่องเติมอากาศทันที")
    elif current_do < DO_WARN:
        raise_to("warn")
        issues.append(f"ออกซิเจนละลายน้ำ (DO) ค่อนข้างต่ำ ({current_do:.2f} mg/L) ควรเพิ่มความเร็วเครื่องเติมอากาศตามที่ AI แนะนำ")

    if influent_cod > COD_WARN:
        raise_to("warn")
        issues.append(f"น้ำเสียที่เข้าระบบสกปรกมาก (COD {influent_cod:.0f} mg/L) ระบบต้องใช้ออกซิเจนมากขึ้น")

    if water_temp > TEMP_WARN:
        raise_to("warn")
        issues.append(f"อุณหภูมิน้ำสูง ({water_temp:.1f} °C) ออกซิเจนละลายน้ำได้น้อยลง")

    return {"level": level, "label": LABELS[level], "issues": issues}


def status_label(current_do, influent_cod, water_temp):
    return evaluate(current_do, influent_cod, water_temp)["label"]

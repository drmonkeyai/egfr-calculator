from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional, Tuple


Sex = Literal["male", "female"]
ScrUnit = Literal["umol/L", "mg/dL"]
Method = Literal["CKD-EPI 2021", "CKD-EPI 2009", "MDRD (IDMS)", "Cockcroft-Gault"]


def scr_to_mgdl(scr_value: float, unit: ScrUnit) -> float:
    """µmol/L -> mg/dL: chia 88.4"""
    if scr_value <= 0:
        raise ValueError("Creatinine phải > 0.")
    if unit == "umol/L":
        return scr_value / 88.4
    return scr_value


def gfr_stage_g1_g5(gfr: float) -> Tuple[str, str]:
    """
    Phân độ GFR theo KDIGO (G1–G5) dựa trên eGFR (mL/min/1.73m²).
    Lưu ý: Với Cockcroft–Gault (CrCl, mL/min) dùng phân độ này chỉ mang tính gần đúng.
    """
    if gfr >= 90:
        return "G1", "Bình thường / cao (≥90)"
    if gfr >= 60:
        return "G2", "Giảm nhẹ (60–89)"
    if gfr >= 45:
        return "G3a", "Giảm nhẹ–vừa (45–59)"
    if gfr >= 30:
        return "G3b", "Giảm vừa–nặng (30–44)"
    if gfr >= 15:
        return "G4", "Giảm nặng (15–29)"
    return "G5", "Suy thận giai đoạn cuối (<15)"


# -------------------------
# eGFR equations
# -------------------------

def egfr_ckd_epi_2021(scr_mgdl: float, age: int, sex: Sex) -> float:
    """
    CKD-EPI 2021 (race-free) creatinine equation for adults (>=18).
    eGFR = 142 * min(SCr/κ,1)^α * max(SCr/κ,1)^(-1.200) * 0.9938^Age * (1.012 if female)
    κ = 0.7 female / 0.9 male
    α = -0.241 female / -0.302 male
    """
    if age < 18:
        raise ValueError("CKD-EPI 2021: áp dụng cho người lớn (>=18 tuổi).")
    kappa = 0.7 if sex == "female" else 0.9
    alpha = -0.241 if sex == "female" else -0.302
    female_factor = 1.012 if sex == "female" else 1.0

    ratio = scr_mgdl / kappa
    mn = min(ratio, 1.0)
    mx = max(ratio, 1.0)

    return 142.0 * (mn ** alpha) * (mx ** -1.200) * (0.9938 ** age) * female_factor


def egfr_ckd_epi_2009(scr_mgdl: float, age: int, sex: Sex, black: bool = False) -> float:
    """
    CKD-EPI 2009 creatinine equation (có hệ số người da đen).
    eGFR = 141 * min(SCr/κ,1)^α * max(SCr/κ,1)^(-1.209) * 0.993^Age * (1.018 if female) * (1.159 if black)
    κ = 0.7 female / 0.9 male
    α = -0.329 female / -0.411 male
    """
    if age < 18:
        raise ValueError("CKD-EPI 2009: áp dụng cho người lớn (>=18 tuổi).")
    kappa = 0.7 if sex == "female" else 0.9
    alpha = -0.329 if sex == "female" else -0.411

    ratio = scr_mgdl / kappa
    mn = min(ratio, 1.0)
    mx = max(ratio, 1.0)

    female_factor = 1.018 if sex == "female" else 1.0
    black_factor = 1.159 if black else 1.0

    return 141.0 * (mn ** alpha) * (mx ** -1.209) * (0.993 ** age) * female_factor * black_factor


def egfr_mdrd_idms(scr_mgdl: float, age: int, sex: Sex, black: bool = False) -> float:
    """
    MDRD 4-variable (IDMS-traceable):
    eGFR = 175 * Scr^-1.154 * Age^-0.203 * (0.742 if female) * (1.212 if black)
    """
    if age < 18:
        raise ValueError("MDRD: áp dụng cho người lớn (>=18 tuổi).")
    female_factor = 0.742 if sex == "female" else 1.0
    black_factor = 1.212 if black else 1.0
    return 175.0 * (scr_mgdl ** -1.154) * (age ** -0.203) * female_factor * black_factor


def crcl_cockcroft_gault(scr_mgdl: float, age: int, sex: Sex, weight_kg: float) -> float:
    """
    Cockcroft–Gault creatinine clearance (CrCl) mL/min (KHÔNG chuẩn hoá 1.73m²):
    CrCl = ((140 - age) * weight_kg) / (72 * Scr) * (0.85 if female)
    """
    if age < 18:
        raise ValueError("Cockcroft–Gault: thường dùng cho người lớn (>=18 tuổi).")
    if weight_kg <= 0:
        raise ValueError("Cân nặng phải > 0.")
    crcl = ((140.0 - age) * weight_kg) / (72.0 * scr_mgdl)
    if sex == "female":
        crcl *= 0.85
    return crcl


@dataclass
class KidneyResult:
    timestamp: str
    method: Method
    age: int
    sex: Sex
    scr_value: float
    scr_unit: ScrUnit
    scr_mgdl: float
    black: Optional[bool]
    weight_kg: Optional[float]
    value: float
    value_unit: str  # "mL/min/1.73m²" hoặc "mL/min"
    stage: str
    stage_text: str
    notes: str


def compute_kidney_function(
    method: Method,
    age: int,
    sex: Sex,
    scr_value: float,
    scr_unit: ScrUnit,
    black: bool = False,
    weight_kg: Optional[float] = None,
) -> KidneyResult:
    scr_mgdl = scr_to_mgdl(scr_value, scr_unit)

    if method == "CKD-EPI 2021":
        val = egfr_ckd_epi_2021(scr_mgdl, age, sex)
        unit = "mL/min/1.73m²"
        notes = "eGFR chuẩn hoá 1.73m² (CKD-EPI 2021, không chủng tộc)."
        stage, stage_text = gfr_stage_g1_g5(val)
        blk = None
        w = None

    elif method == "CKD-EPI 2009":
        val = egfr_ckd_epi_2009(scr_mgdl, age, sex, black=black)
        unit = "mL/min/1.73m²"
        notes = "eGFR chuẩn hoá 1.73m² (CKD-EPI 2009). Có tuỳ chọn hệ số người da đen."
        stage, stage_text = gfr_stage_g1_g5(val)
        blk = black
        w = None

    elif method == "MDRD (IDMS)":
        val = egfr_mdrd_idms(scr_mgdl, age, sex, black=black)
        unit = "mL/min/1.73m²"
        notes = "eGFR chuẩn hoá 1.73m² (MDRD IDMS). Có tuỳ chọn hệ số người da đen."
        stage, stage_text = gfr_stage_g1_g5(val)
        blk = black
        w = None

    elif method == "Cockcroft-Gault":
        if weight_kg is None:
            raise ValueError("Cockcroft–Gault cần nhập cân nặng.")
        val = crcl_cockcroft_gault(scr_mgdl, age, sex, weight_kg=weight_kg)
        unit = "mL/min"
        notes = "CrCl (Cockcroft–Gault) KHÔNG chuẩn hoá 1.73m²; thường dùng chỉnh liều thuốc."
        # phân độ G1–G5 dùng gần đúng theo ngưỡng eGFR (chỉ để tham khảo)
        stage, stage_text = gfr_stage_g1_g5(val)
        blk = None
        w = float(weight_kg)

    else:
        raise ValueError("Phương pháp không hợp lệ.")

    return KidneyResult(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        method=method,
        age=age,
        sex=sex,
        scr_value=float(scr_value),
        scr_unit=scr_unit,
        scr_mgdl=scr_mgdl,
        black=blk,
        weight_kg=w,
        value=val,
        value_unit=unit,
        stage=stage,
        stage_text=stage_text,
        notes=notes,
    )

import csv
from pathlib import Path

import streamlit as st

from src.egfr import compute_kidney_function

# ============== App config ==============
st.set_page_config(page_title="eGFR / CrCl Calculator", page_icon="🩺", layout="wide")

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
HISTORY_FILE = DATA_DIR / "kidney_history.csv"


def save_history_row(row: dict) -> None:
    file_exists = HISTORY_FILE.exists()
    with HISTORY_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


st.title("🩺 Công cụ tính eGFR / CrCl (nhiều công thức)")
st.caption("Thiết kế thao tác nhanh: click nhiều, ít gõ. Dùng cho người lớn (≥18 tuổi).")

tab_calc, tab_history, tab_help = st.tabs(["🧮 Tính nhanh", "🗂️ Lịch sử", "ℹ️ Giải thích"])

METHODS = ["CKD-EPI 2021", "CKD-EPI 2009", "MDRD (IDMS)", "Cockcroft-Gault"]

with tab_calc:
    left, right = st.columns([1.15, 0.85], gap="large")

    with left:
        st.subheader("Nhập thông tin")

        # chọn công thức (click)
        method = st.selectbox("Phương pháp", METHODS, index=0)

        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            age = st.slider("Tuổi", min_value=18, max_value=100, value=40, step=1)
        with c2:
            sex_ui = st.radio("Giới", ["Nam", "Nữ"], horizontal=True)
        with c3:
            unit_ui = st.radio("Đơn vị Creatinine", ["µmol/L", "mg/dL"], horizontal=True)

        sex = "male" if sex_ui == "Nam" else "female"
        scr_unit = "umol/L" if unit_ui == "µmol/L" else "mg/dL"

        # creatinine: slider để ít gõ
        if scr_unit == "umol/L":
            scr = st.slider("Creatinine huyết thanh (µmol/L)", min_value=30, max_value=2000, value=90, step=1)
        else:
            scr = st.slider("Creatinine huyết thanh (mg/dL)", min_value=0.3, max_value=20.0, value=1.0, step=0.1)

        # tuỳ chọn thêm input theo công thức
        black = False
        weight_kg = None

        # CKD-EPI 2009 / MDRD có hệ số chủng tộc (tùy chọn)
        if method in ("CKD-EPI 2009", "MDRD (IDMS)"):
            black = st.toggle("Người da đen (Black) — chỉ dùng khi phù hợp", value=False)

        # Cockcroft–Gault cần cân nặng
        if method == "Cockcroft-Gault":
            weight_kg = st.slider("Cân nặng (kg)", min_value=30, max_value=200, value=60, step=1)

        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
        with col_btn1:
            calc_btn = st.button("Tính", type="primary", use_container_width=True)
        with col_btn2:
            save_btn = st.button("Lưu vào lịch sử", use_container_width=True)
        with col_btn3:
            clear_btn = st.button("Xoá kết quả", use_container_width=True)

    with right:
        st.subheader("Kết quả")

        if "kidney_result" not in st.session_state:
            st.session_state.kidney_result = None

        if clear_btn:
            st.session_state.kidney_result = None

        if calc_btn or save_btn:
            try:
                res = compute_kidney_function(
                    method=method,
                    age=int(age),
                    sex=sex,
                    scr_value=float(scr),
                    scr_unit=scr_unit,
                    black=bool(black),
                    weight_kg=weight_kg,
                )
                st.session_state.kidney_result = res

                if save_btn:
                    save_history_row(
                        {
                            "timestamp": res.timestamp,
                            "method": res.method,
                            "age": res.age,
                            "sex": res.sex,
                            "scr_value": res.scr_value,
                            "scr_unit": res.scr_unit,
                            "scr_mgdl": f"{res.scr_mgdl:.3f}",
                            "black": "" if res.black is None else str(res.black),
                            "weight_kg": "" if res.weight_kg is None else f"{res.weight_kg:.0f}",
                            "value": f"{res.value:.1f}",
                            "value_unit": res.value_unit,
                            "stage": res.stage,
                            "stage_text": res.stage_text,
                            "notes": res.notes,
                        }
                    )
                    st.success("Đã lưu vào lịch sử (data/kidney_history.csv).")

            except Exception as e:
                st.error(str(e))

        res = st.session_state.kidney_result
        if res is None:
            st.info("Nhập thông tin bên trái và bấm **Tính**.")
        else:
            st.metric(f"Kết quả ({res.method})", f"{res.value:.1f} {res.value_unit}")
            st.write(f"**Phân độ (G1–G5):** {res.stage} — {res.stage_text}")
            st.caption(f"Creatinine quy đổi: **{res.scr_mgdl:.3f} mg/dL** | Thời điểm: {res.timestamp}")
            st.info(res.notes)

            # thanh mức độ (G1 -> G5)
            stage_order = ["G1", "G2", "G3a", "G3b", "G4", "G5"]
            idx = stage_order.index(res.stage)
            st.progress((idx + 1) / len(stage_order), text="Mức độ giảm chức năng thận (G1 → G5)")

with tab_history:
    st.subheader("Lịch sử tính toán")
    if HISTORY_FILE.exists():
        st.write(f"File: `{HISTORY_FILE.as_posix()}`")
        st.dataframe(
            list(csv.DictReader(HISTORY_FILE.open("r", encoding="utf-8"))),
            use_container_width=True,
            height=420,
        )
        st.download_button(
            "Tải lịch sử CSV",
            data=HISTORY_FILE.read_bytes(),
            file_name="kidney_history.csv",
            mime="text/csv",
            use_container_width=True,
        )
    else:
        st.info("Chưa có dữ liệu lịch sử. Hãy bấm **Lưu vào lịch sử** ở tab Tính nhanh.")

with tab_help:
    st.subheader("Gợi ý chọn công thức (thực hành)")
    st.markdown(
        """
- **CKD-EPI 2021**: thường dùng rộng rãi, **không dùng hệ số chủng tộc**, kết quả là **eGFR chuẩn hoá 1.73m²**.
- **CKD-EPI 2009 / MDRD**: có tuỳ chọn hệ số “Black”; hiện nay nhiều nơi hạn chế dùng hệ số này.
- **Cockcroft–Gault (CrCl)**: **cần cân nặng**, kết quả **mL/min (không chuẩn hoá 1.73m²)**; hay dùng để **chỉnh liều thuốc**.
- Phân độ **G1–G5** trong app dựa trên ngưỡng KDIGO theo eGFR; với CrCl chỉ để tham khảo nhanh.
"""
    )

st.divider()
st.caption("Tip: Sửa file rồi Ctrl+S → trình duyệt tự cập nhật.")

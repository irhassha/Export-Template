import streamlit as st
import pandas as pd

# --- STEP 1: Buat tabel 1 baris dengan kolom 1-37 ---
columns = [str(i) for i in range(1, 38)]
df = pd.DataFrame([[""] * 37], columns=columns)

# --- STEP 2: Input Service dan Slot ---
st.title("Visualisasi Merge Slot Berdasarkan Service")

service = st.text_input("Service (contoh: CIT)")
slot_range = st.text_input("Slot (contoh: 1-12)")

def build_merged_html(service, start, end):
    html = "<table border='1' style='border-collapse: collapse;'><tr>"
    for i in range(1, 38):
        if i == start:
            colspan = end - start + 1
            html += f"<td colspan='{colspan}' align='center'><b>{service}</b></td>"
        elif start < i <= end:
            continue  # sudah masuk di colspan sebelumnya
        else:
            html += f"<td>{''}</td>"
    html += "</tr></table>"
    return html

# --- STEP 3: Validasi dan Visualisasi ---
if service and slot_range:
    try:
        start_slot, end_slot = [int(x) for x in slot_range.split('-')]
        if 1 <= start_slot <= end_slot <= 37:
            html = build_merged_html(service, start_slot, end_slot)
            st.markdown(html, unsafe_allow_html=True)
        else:
            st.error("Slot harus antara 1 sampai 37")
    except:
        st.error("Format slot salah. Gunakan format seperti 1-12")
else:
    st.info("Masukkan Service dan Slot untuk memulai visualisasi.")

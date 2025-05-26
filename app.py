import streamlit as st

st.title("🔢 Visualisasi Merge Slot Berdasarkan Multiple Service")

# --- INPUT MULTIPLE SERVICE ---
st.markdown("### Input Data Service")
with st.form("input_form"):
    num_rows = st.number_input("Jumlah service", min_value=1, max_value=20, value=3)
    services = []
    for i in range(num_rows):
        col1, col2 = st.columns([2, 2])
        with col1:
            svc = st.text_input(f"Service {i+1}", key=f"svc_{i}")
        with col2:
            slot = st.text_input(f"Slot (cth: 1-12)", key=f"slot_{i}")
        services.append((svc, slot))
    submitted = st.form_submit_button("Tampilkan")

# --- BANGUN HTML ---
def build_visual_table(services):
    html = "<table border='1' style='border-collapse: collapse; text-align: center;'>"

    # Baris-baris Service
    for svc, slot in services:
        if not svc or "-" not in slot:
            continue
        try:
            start, end = [int(x) for x in slot.split("-")]
            if not (1 <= start <= end <= 37):
                continue
        except:
            continue

        html += "<tr>"
        for i in range(1, 38):
            if i == start:
                colspan = end - start + 1
                html += f"<td colspan='{colspan}'><b>{svc}</b></td>"
            elif start < i <= end:
                continue  # Sudah tergabung
            else:
                html += "<td></td>"
        html += "</tr>"

    # Baris Angka 1-37
    html += "<tr>"
    for i in range(1, 38):
        html += f"<td>{i}</td>"
    html += "</tr>"

    html += "</table>"
    return html

# --- TAMPILKAN HASIL ---
if submitted:
    html_table = build_visual_table(services)
    st.markdown("### Hasil Visualisasi")
    st.markdown(html_table, unsafe_allow_html=True)

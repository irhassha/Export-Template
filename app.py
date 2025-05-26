import streamlit as st

st.title("🔁 Visualisasi Merge Service dalam 1 Baris (Horizontal)")

# Input form
with st.form("form"):
    num = st.number_input("Jumlah Service", 1, 20, 3)
    entries = []
    for i in range(num):
        c1, c2 = st.columns(2)
        with c1:
            svc = st.text_input(f"Service {i+1}", key=f"svc_{i}")
        with c2:
            slot = st.text_input(f"Slot (cth: 1-12)", key=f"slot_{i}")
        entries.append((svc.strip(), slot.strip()))
    go = st.form_submit_button("Tampilkan")

def build_single_row_table(services):
    row = [""] * 37  # posisi kolom 1-37
    markers = [""] * 37

    for svc, slot in services:
        try:
            start, end = [int(s) for s in slot.split('-')]
            for i in range(start - 1, end):
                if row[i] != "":
                    markers[i] = "⚠️"  # Tanda tabrakan
                row[i] = svc
        except:
            continue

    html = "<table border='1' style='border-collapse: collapse; text-align:center;'><tr>"
    i = 0
    while i < 37:
        if row[i] == "":
            html += "<td></td>"
            i += 1
        else:
            svc = row[i]
            span = 1
            while i + span < 37 and row[i + span] == svc:
                span += 1
            html += f"<td colspan='{span}'><b>{svc}</b></td>"
            i += span
    html += "</tr><tr>"

    for i in range(37):
        html += f"<td>{i+1}</td>"
    html += "</tr></table>"

    return html

if go:
    html = build_single_row_table(entries)
    st.markdown("### 🔍 Visualisasi (1 Baris Total)")
    st.markdown(html, unsafe_allow_html=True)

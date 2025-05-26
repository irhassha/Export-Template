import streamlit as st
import random

st.title("🎨 Visualisasi Merge Service 1 Baris + Warna")

# Daftar warna siap pakai (bisa kamu ganti sesuai tema)
color_palette = [
    "#FF9999", "#99CCFF", "#99FF99", "#FFD700", "#FFA07A",
    "#BA55D3", "#40E0D0", "#FFB6C1", "#D3D3D3", "#87CEFA",
    "#F08080", "#00FA9A", "#E6E6FA", "#B0C4DE", "#FAFAD2"
]

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

def build_colored_table(services):
    row = [""] * 37
    svc_color_map = {}
    used_colors = []

    # Assign warna unik untuk setiap service
    for svc, _ in services:
        if svc not in svc_color_map:
            color = random.choice([c for c in color_palette if c not in used_colors])
            svc_color_map[svc] = color
            used_colors.append(color)

    # Isi row berdasarkan slot
    for svc, slot in services:
        try:
            start, end = [int(s) for s in slot.split('-')]
            for i in range(start - 1, end):
                row[i] = svc
        except:
            continue

    # Bangun tabel HTML
    html = "<table border='1' style='border-collapse: collapse; text-align:center;'>"
    html += "<tr>"

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
            color = svc_color_map.get(svc, "#FFFFFF")
            html += f"<td colspan='{span}' style='background-color:{color};'><b>{svc}</b></td>"
            i += span

    html += "</tr><tr>"
    for i in range(1, 38):
        html += f"<td>{i}</td>"
    html += "</tr></table>"
    return html

if go:
    html = build_colored_table(entries)
    st.markdown("### 🌈 Visualisasi (1 Baris Total + Warna)")
    st.markdown(html, unsafe_allow_html=True)

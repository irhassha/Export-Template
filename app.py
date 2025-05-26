import streamlit as st
import random

st.title("📦 Multi Template Visualisasi Merge Service + Warna")

color_palette = [
    "#FF9999", "#99CCFF", "#99FF99", "#FFD700", "#FFA07A",
    "#BA55D3", "#40E0D0", "#FFB6C1", "#D3D3D3", "#87CEFA",
    "#F08080", "#00FA9A", "#E6E6FA", "#B0C4DE", "#FAFAD2"
]

# --- Form Input Jumlah Template ---
num_templates = st.number_input("Berapa banyak template? (misalnya: A01, A02)", min_value=1, max_value=10, value=2)

all_templates = []
with st.form("multi_template"):
    for t_index in range(num_templates):
        st.markdown(f"### ✳️ Template {t_index+1} (misal: A0{t_index+1})")
        template_name = st.text_input(f"Nama Template", value=f"A0{t_index+1}", key=f"name_{t_index}")
        service_entries = []
        num_services = st.number_input(f"Jumlah Service untuk {template_name}", 1, 10, 3, key=f"numsvc_{t_index}")

        for i in range(num_services):
            c1, c2 = st.columns(2)
            with c1:
                svc = st.text_input(f"Service {i+1} (template {template_name})", key=f"svc_{t_index}_{i}")
            with c2:
                slot = st.text_input(f"Slot (cth: 1-12)", key=f"slot_{t_index}_{i}")
            service_entries.append((svc.strip(), slot.strip()))
        all_templates.append((template_name, service_entries))
    
    go = st.form_submit_button("Tampilkan")

# --- Fungsi visualisasi per template ---
def build_colored_table(services):
    row = [""] * 37
    svc_color_map = {}
    used_colors = []

    for svc, _ in services:
        if svc not in svc_color_map:
            color = random.choice([c for c in color_palette if c not in used_colors])
            svc_color_map[svc] = color
            used_colors.append(color)

    for svc, slot in services:
        try:
            start, end = [int(s) for s in slot.split('-')]
            for i in range(start - 1, end):
                row[i] = svc
        except:
            continue

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

# --- Tampilkan Semua Template ---
if go:
    for template_name, entries in all_templates:
        st.markdown(f"### 📌 Template {template_name}")
        html = build_colored_table(entries)
        st.markdown(html, unsafe_allow_html=True)

import streamlit as st
import random

st.title("📊 Visualisasi Service Merge per Template (Multi Akses)")

color_palette = [
    "#FF9999", "#99CCFF", "#99FF99", "#FFD700", "#FFA07A",
    "#BA55D3", "#40E0D0", "#FFB6C1", "#D3D3D3", "#87CEFA",
    "#F08080", "#00FA9A", "#E6E6FA", "#B0C4DE", "#FAFAD2"
]

# --- Form Input Jumlah Baris Service ---
num_rows = st.number_input("Jumlah service (baris input)", 1, 30, 5)

with st.form("svc_input"):
    st.markdown("### ➕ Input Service, Slot & Template Tujuan")
    input_entries = []
    for i in range(num_rows):
        col1, col2, col3 = st.columns([2, 2, 3])
        with col1:
            svc = st.text_input(f"Service {i+1}", key=f"svc_{i}")
        with col2:
            slot = st.text_input("Slot (cth: 1-12)", key=f"slot_{i}")
        with col3:
            tmpl = st.text_input("Template(s) (cth: A01,A02)", key=f"tmpl_{i}")
        input_entries.append((svc.strip(), slot.strip(), tmpl.strip()))
    
    go = st.form_submit_button("Tampilkan")

# --- Build Dictionary: {template: [(svc, slot), ...]} ---
def build_template_dict(entries):
    template_map = {}
    for svc, slot, tmpl in entries:
        if not svc or not slot or not tmpl:
            continue
        try:
            start, end = [int(x) for x in slot.split("-")]
        except:
            continue
        for t in [t.strip().upper() for t in tmpl.split(",") if t.strip()]:
            if t not in template_map:
                template_map[t] = []
            template_map[t].append((svc, slot))
    return template_map

# --- Build Visualisasi per Template ---
def build_visual_table(services):
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

# --- Render ---
if go:
    template_dict = build_template_dict(input_entries)
    for tmpl_name in sorted(template_dict):
        st.markdown(f"### 🗂️ Template {tmpl_name}")
        html = build_visual_table(template_dict[tmpl_name])
        st.markdown(html, unsafe_allow_html=True)

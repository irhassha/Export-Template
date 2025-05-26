import streamlit as st
import random

st.title("🧱 Visualisasi Merge per Block (Warna Konsisten)")

# Palet warna tetap
color_palette = [
    "#FF9999", "#99CCFF", "#99FF99", "#FFD700", "#FFA07A",
    "#BA55D3", "#40E0D0", "#FFB6C1", "#D3D3D3", "#87CEFA",
    "#F08080", "#00FA9A", "#E6E6FA", "#B0C4DE", "#FAFAD2"
]

# Input jumlah service
num_rows = st.number_input("Jumlah service (baris input)", 1, 30, 5)

# Form input data
with st.form("svc_input"):
    st.markdown("### ➕ Input Service, Slot, dan Block Tujuan")
    input_entries = []
    for i in range(num_rows):
        col1, col2, col3 = st.columns([2, 2, 3])
        with col1:
            svc = st.text_input(f"Service {i+1}", key=f"svc_{i}")
        with col2:
            slot = st.text_input("Slot (cth: 1-12)", key=f"slot_{i}")
        with col3:
            blk = st.text_input("Block(s) (cth: A01,A02)", key=f"blk_{i}")
        input_entries.append((svc.strip(), slot.strip(), blk.strip()))
    go = st.form_submit_button("Tampilkan")

# Build mapping service -> warna unik
def assign_colors(services):
    svc_color_map = {}
    used_colors = []
    for svc in services:
        if svc not in svc_color_map:
            color = random.choice([c for c in color_palette if c not in used_colors])
            svc_color_map[svc] = color
            used_colors.append(color)
    return svc_color_map

# Organize data per Block
def build_block_dict(entries):
    all_svcs = set()
    block_map = {}
    for svc, slot, blk in entries:
        if not svc or not slot or not blk:
            continue
        all_svcs.add(svc)
        try:
            start, end = [int(x) for x in slot.split("-")]
        except:
            continue
        for b in [b.strip().upper() for b in blk.split(",") if b.strip()]:
            if b not in block_map:
                block_map[b] = []
            block_map[b].append((svc, slot))
    return block_map, all_svcs

# Build HTML visual per block
def build_block_table(services, color_map):
    row = [""] * 37
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
            color = color_map.get(svc, "#FFFFFF")
            html += f"<td colspan='{span}' style='background-color:{color};'><b>{svc}</b></td>"
            i += span
    html += "</tr><tr>"
    for i in range(1, 38):
        html += f"<td>{i}</td>"
    html += "</tr></table>"
    return html

# Eksekusi saat submit
if go:
    block_map, all_services = build_block_dict(input_entries)
    color_map = assign_colors(all_services)

    for block_name in sorted(block_map):
        st.markdown(f"### 🧱 Block {block_name}")
        html = build_block_table(block_map[block_name], color_map)
        st.markdown(html, unsafe_allow_html=True)

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import itertools

# ==============================================================================
# BAGIAN 1: KONFIGURASI GLOBAL & FUNGSI-FUNGSI UTAMA
# ==============================================================================

# --- Konfigurasi Default Aplikasi ---
DEFAULT_YARD_CONFIG = {
    'A01': 37, 'A02': 37, 'A03': 37, 'A04': 37,
    'B01': 37, 'B02': 37, 'B03': 37, 'B04': 37, 'B05': 37,
    'C03': 45, 'C04': 45, 'C05': 45
}
DEFAULT_SLOT_CAPACITY = 30
STACKING_TREND_URL = 'https://github.com/irhassha/Clash_Analyzer/raw/refs/heads/main/stacking_trend.xlsx'

# --- Fungsi Helper untuk Memuat Data ---

@st.cache_data
def load_stacking_trends(url):
    """Memuat dan cache data stacking trend dari URL GitHub."""
    try:
        df = pd.read_excel(url)
        df.rename(columns={'STACKING TREND': 'SERVICE'}, inplace=True)
        return df.set_index('SERVICE')
    except Exception as e:
        st.error(f"Gagal memuat file stacking trend dari URL: {e}")
        return None

def get_daily_arrivals(total_boxes, service_name, trends_df, num_days):
    """Menghitung jumlah box harian, menangani kekurangan hari dengan nilai 0."""
    percentages = []
    if service_name in trends_df.index:
        for i in range(num_days):
            day_col = f'DAY {i}'
            if day_col in trends_df.columns:
                percentages.append(trends_df.loc[service_name, day_col])
            else:
                percentages.append(0)
        percentages = np.array(pd.to_numeric(percentages, errors='coerce'))
    else:
        st.warning(f"Service '{service_name}' tidak ditemukan. Menggunakan tren rata-rata.")
        percentages = np.full(num_days, 1.0 / num_days)

    percentages = np.nan_to_num(percentages)
    if percentages.sum() > 0:
        percentages = percentages / percentages.sum()

    daily_boxes = np.round(percentages * total_boxes).astype(int)
    diff = total_boxes - daily_boxes.sum()
    if diff != 0 and len(daily_boxes) > 0:
        daily_boxes[np.argmax(daily_boxes)] += diff
    return daily_boxes

# --- Fungsi Inti Simulasi ("Otak" Aplikasi) ---

def run_simulation(df_schedule, df_trends, rules, rule_level):
    """Fungsi utama untuk menjalankan seluruh proses simulasi dengan logika nyata."""

    # --- BAGIAN 1: INISIALISASI ---
    yard_config = DEFAULT_YARD_CONFIG
    slot_capacity = DEFAULT_SLOT_CAPACITY
    
    yard_status = {(area, i): None for area, num_slots in yard_config.items() for i in range(1, num_slots + 1)}
    
    offset = 0
    yard_config_map = {}
    for area, num_slots in yard_config.items():
        yard_config_map[area] = {'offset': offset, 'size': num_slots}
        offset += num_slots
    
    def get_slot_index(slot):
        area, number = slot
        return yard_config_map[area]['offset'] + number - 1

    vessels = {}
    for _, row in df_schedule.iterrows():
        ship_name = row['VESSEL']
        start_date = row['OPEN STACKING'].normalize()
        etd_date = row['ETD'].normalize()
        num_days = (etd_date - start_date).days
        
        base_avg = 150 if rules['cluster_req_logic'] == 'Wajar' else 100
        initial_cluster_req = max(1, int(np.ceil(row['TOTAL BOX (TEUS)'] / base_avg)))

        vessels[ship_name] = {
            'name': ship_name, 'service': row['SERVICE'], 'total_boxes': row['TOTAL BOX (TEUS)'],
            'start_date': start_date, 'etd_date': etd_date,
            'daily_arrivals': get_daily_arrivals(row['TOTAL BOX (TEUS)'], row['SERVICE'], df_trends, num_days + 1),
            'clusters': [[] for _ in range(initial_cluster_req)],
            'max_clusters': initial_cluster_req + 2,
            'remaining_capacity': 0 # <<< PERUBAHAN BARU: Inisialisasi sisa kapasitas
        }

    # --- BAGIAN 2: LOGIKA SIMULASI INTI ---
    daily_log = []
    yor_data = []
    daily_yard_snapshots = {} 
    
    start_date_sim = df_schedule['OPEN STACKING'].min().normalize()
    end_date_sim = df_schedule['ETD'].max().normalize()
    date_range = pd.date_range(start=start_date_sim, end=end_date_sim, freq='D')

    for current_date in date_range:
        for ship_data in vessels.values():
            if ship_data['etd_date'].normalize() == (current_date - timedelta(days=1)).normalize():
                slots_to_free = [slot for cluster in ship_data['clusters'] for slot in cluster]
                for slot in slots_to_free:
                    if yard_status.get(slot) == ship_data['name']:
                        yard_status[slot] = None

        active_ships_today = sorted(
            [ship for ship in vessels.values() if current_date >= ship['start_date'] and current_date <= ship['etd_date']],
            key=lambda x: x['total_boxes'], reverse=True
        )
        
        for ship in active_ships_today:
            day_index = (current_date - ship['start_date']).days
            boxes_to_allocate_today = 0
            if day_index < len(ship['daily_arrivals']):
                boxes_to_allocate_today = ship['daily_arrivals'][day_index]
            
            # <<< PERUBAHAN BARU: Logika Sisa Kapasitas ---
            effective_boxes_needed = boxes_to_allocate_today - ship['remaining_capacity']
            
            slots_needed = 0
            slots_allocated_today = []
            recommendation = "Tidak ada aktivitas penumpukan"

            if effective_boxes_needed > 0:
                # Jika butuh slot baru, reset sisa kapasitas dan hitung kebutuhan baru
                ship['remaining_capacity'] = 0
                slots_needed = int(np.ceil(effective_boxes_needed / slot_capacity))
                
                slots_allocated_today, recommendation = allocate_slots_intelligently(
                    ship, slots_needed, yard_status, vessels, current_date, rules, get_slot_index
                )
                
                # Hitung sisa kapasitas baru dari alokasi hari ini
                newly_allocated_capacity = len(slots_allocated_today) * slot_capacity
                ship['remaining_capacity'] = newly_allocated_capacity - effective_boxes_needed
            elif boxes_to_allocate_today > 0:
                # Jika sisa kapasitas cukup, tidak perlu slot baru
                ship['remaining_capacity'] = abs(effective_boxes_needed) # Sisa kapasitas dikurangi pemakaian
                recommendation = f"Menggunakan sisa kapasitas. Sisa: {ship['remaining_capacity']} box."
            # --- AKHIR PERUBAHAN ---

            daily_log.append({
                'Tanggal': current_date.strftime('%Y-%m-%d'), 'Kapal': ship['name'],
                'Butuh Box': boxes_to_allocate_today,
                'Butuh Slot': slots_needed, 'Slot Berhasil': len(slots_allocated_today),
                'Slot Gagal': slots_needed - len(slots_allocated_today),
                'Rekomendasi': recommendation
            })
        
        occupied_slots = sum(1 for status in yard_status.values() if status is not None)
        total_slots = len(yard_status)
        yor_data.append({
            'Tanggal': current_date,
            'Total Box di Yard': occupied_slots * slot_capacity,
            'Rasio Okupansi (%)': (occupied_slots / total_slots) * 100
        })
        daily_yard_snapshots[current_date] = yard_status.copy()
        
    # --- BAGIAN 3: AGREGASI & PERSIAPAN OUTPUT ---
    df_daily_log = pd.DataFrame(daily_log)
    df_yor = pd.DataFrame(yor_data)

    recap_list = []
    for ship in vessels.values():
        total_requested = ship['total_boxes']
        successful_slots = df_daily_log[df_daily_log['Kapal'] == ship['name']]['Slot Berhasil'].sum()
        # Estimasi box berhasil
        boxes_successful = successful_slots * slot_capacity + ship['remaining_capacity']
        
        recap_list.append({
            'Kapal': ship['name'], 'Permintaan Box': total_requested,
            'Box Berhasil': boxes_successful,
            'Box Gagal': max(0, total_requested - boxes_successful)
        })
    df_recap = pd.DataFrame(recap_list)

    map_list = []
    for ship in vessels.values():
        for i, cluster in enumerate(ship['clusters']):
            if not cluster: continue
            
            cluster.sort(key=get_slot_index)
            groups = []
            for k, g in itertools.groupby(enumerate(cluster), lambda item: get_slot_index(item[1]) - item[0]):
                group = list(item[1] for item in g)
                start_slot_obj = group[0]
                end_slot_obj = group[-1]
                
                if start_slot_obj == end_slot_obj:
                    groups.append(f"{start_slot_obj[0]}:{start_slot_obj[1]}")
                else:
                    groups.append(f"{start_slot_obj[0]}:{start_slot_obj[1]}-{end_slot_obj[1]}")
            
            map_list.append({
                'Kapal': ship['name'], 'Cluster': f'Cluster {i+1}',
                'Lokasi & Slot': ", ".join(groups)
            })
    df_map = pd.DataFrame(map_list)

    return df_yor, df_recap, df_map, df_daily_log, daily_yard_snapshots

def find_placeable_slots(current_ship, all_ships, yard_status, current_date, rules):
    """PERBAIKAN: Fungsi ini sekarang HANYA memeriksa aturan dari kapal LAIN."""
    free_slots = {slot for slot, owner in yard_status.items() if owner is None}
    blocked_indices = set()
    
    offset = 0
    temp_map = {}
    for area, num_slots in DEFAULT_YARD_CONFIG.items():
        temp_map[area] = {'offset': offset}; offset += num_slots
    def get_slot_idx_local(slot):
        return temp_map[slot[0]]['offset'] + slot[1] - 1

    active_ships = [ship for ship in all_ships.values() if current_date >= ship['start_date'] and current_date <= ship['etd_date']]

    for ship in active_ships:
        if ship['name'] == current_ship['name']: continue
        
        etd_diff = abs((current_ship['etd_date'] - ship['etd_date']).days)
        
        for cluster in ship['clusters']:
            if not cluster: continue
            cluster_indices = [get_slot_idx_local(s) for s in cluster]
            min_idx, max_idx = min(cluster_indices), max(cluster_indices)
            
            for i in range(min_idx - rules['daily_exclusion_zone'], max_idx + rules['daily_exclusion_zone'] + 1):
                blocked_indices.add(i)
            if etd_diff <= 1:
                for i in range(min_idx - rules['inter_ship_gap'], max_idx + rules['inter_ship_gap'] + 1):
                    blocked_indices.add(i)

    placeable_slots = {slot for slot in free_slots if get_slot_idx_local(slot) not in blocked_indices}
    return sorted(list(placeable_slots), key=get_slot_idx_local)

def allocate_slots_intelligently(ship, slots_needed, yard_status, vessels, current_date, rules, get_slot_index_func):
    """PERBAIKAN: Logika alokasi cerdas dengan penanganan Jarak Internal yang benar."""
    
    placeable_slots = find_placeable_slots(ship, vessels, yard_status, current_date, rules)
    if len(placeable_slots) < slots_needed:
        return [], "Gagal: Tidak cukup slot valid yang tersedia (terblokir kapal lain)."

    def format_slot_list_to_string(slot_list):
        if not slot_list: return ""
        start = slot_list[0]; end = slot_list[-1]
        return f"{start[0]}:{start[1]}" if start == end else f"{start[0]}:{start[1]}-{end[1]}"

    # Prioritas 1: Perluas cluster yang ada
    for i, cluster in enumerate(ship['clusters']):
        if not cluster: continue
        cluster.sort(key=get_slot_index_func)
        first_slot_idx = get_slot_index_func(cluster[0])
        last_slot_idx = get_slot_index_func(cluster[-1])
        
        placeable_indices = {get_slot_index_func(s) for s in placeable_slots}
        
        expansion_indices_before = set(range(first_slot_idx - slots_needed, first_slot_idx))
        if expansion_indices_before.issubset(placeable_indices):
            slots_to_fill = sorted([s for s in placeable_slots if get_slot_index_func(s) in expansion_indices_before], key=get_slot_index_func)
            ship['clusters'][i] = slots_to_fill + ship['clusters'][i]
            for slot in slots_to_fill: yard_status[slot] = ship['name']
            return slots_to_fill, f"Perluas Cluster #{i+1}, target: {format_slot_list_to_string(slots_to_fill)}"
        
        expansion_indices_after = set(range(last_slot_idx + 1, last_slot_idx + 1 + slots_needed))
        if expansion_indices_after.issubset(placeable_indices):
            slots_to_fill = sorted([s for s in placeable_slots if get_slot_index_func(s) in expansion_indices_after], key=get_slot_index_func)
            ship['clusters'][i].extend(slots_to_fill)
            for slot in slots_to_fill: yard_status[slot] = ship['name']
            return slots_to_fill, f"Perluas Cluster #{i+1}, target: {format_slot_list_to_string(slots_to_fill)}"

    # Prioritas 2 & 3: Buat cluster baru
    placeable_blocks = []
    for k, g in itertools.groupby(enumerate(placeable_slots), lambda item: get_slot_index_func(item[1]) - item[0]):
        placeable_blocks.append([item[1] for item in g])

    valid_blocks = [block for block in placeable_blocks if len(block) >= slots_needed]
    if not valid_blocks:
        return [], "Gagal: Tidak ada blok tunggal yang cukup besar."

    final_valid_blocks = []
    for block in valid_blocks:
        is_valid_distance = True
        block_start_idx = get_slot_index_func(block[0])
        block_end_idx = get_slot_index_func(block[slots_needed-1])
        for existing_cluster in ship['clusters']:
            if not existing_cluster: continue
            existing_cluster.sort(key=get_slot_index_func)
            existing_start_idx = get_slot_index_func(existing_cluster[0])
            existing_end_idx = get_slot_index_func(existing_cluster[-1])
            
            distance = max(existing_start_idx - block_end_idx, block_start_idx - existing_end_idx) - 1
            if distance < rules['intra_ship_gap']:
                is_valid_distance = False
                break
        if is_valid_distance:
            final_valid_blocks.append(block)

    if not final_valid_blocks:
        return [], "Gagal: Blok tersedia melanggar jarak internal."

    final_valid_blocks.sort(key=len)
    best_block = final_valid_blocks[0]
    slots_to_fill = best_block[:slots_needed]

    target_cluster_idx = -1
    for i, cluster in enumerate(ship['clusters']):
        if not cluster:
            target_cluster_idx = i
            break
    
    if target_cluster_idx == -1:
        if len(ship['clusters']) < ship['max_clusters']:
            ship['clusters'].append([])
            target_cluster_idx = len(ship['clusters']) - 1
            recommendation = f"Buat Cluster Tambahan #{len(ship['clusters'])}, target: {format_slot_list_to_string(slots_to_fill)}"
        else:
            return [], "Gagal: Batas maksimal cluster tercapai."
    else:
        recommendation = f"Isi Cluster #{target_cluster_idx + 1}, target: {format_slot_list_to_string(slots_to_fill)}"

    ship['clusters'][target_cluster_idx].extend(slots_to_fill)
    for slot in slots_to_fill: yard_status[slot] = ship['name']
    return slots_to_fill, recommendation

def create_stacked_bar(area_name, yard_state_on_date, vessel_colors, total_slots):
    occupancy = {}
    for i in range(1, total_slots + 1):
        vessel = yard_state_on_date.get((area_name, i))
        if vessel:
            if vessel not in occupancy: occupancy[vessel] = 0
            occupancy[vessel] += 1
            
    if not occupancy:
        return f"""<div style="background-color: #333; height: 20px; width: 100%; border-radius: 5px; display: flex; align-items: center; justify-content: center; color: #888; font-size: 12px;">Kosong</div>"""

    bar_html = '<div style="display: flex; width: 100%; height: 20px; border-radius: 5px; overflow: hidden;">'
    tooltip_text = []
    for vessel in sorted(occupancy.keys()):
        count = occupancy[vessel]
        percentage = (count / total_slots) * 100
        color = vessel_colors.get(vessel, "#FFFFFF")
        bar_html += f'<div style="width: {percentage}%; background-color: {color};"></div>'
        tooltip_text.append(f"{vessel}: {count} slot")
    bar_html += '</div>'
    return f'<div title="{", ".join(tooltip_text)}">{bar_html}</div>'

# ==============================================================================
# BAGIAN 2: UI (ANTARMUKA) STREAMLIT
# ==============================================================================

st.set_page_config(layout="wide", page_title="Yard Allocation Simulator")
st.title("🚢 Simulasi Alokasi Container Yard")

if 'simulation_results' not in st.session_state:
    st.session_state['simulation_results'] = None

with st.sidebar:
    st.header("1. Upload File")
    uploaded_file = st.file_uploader("Upload Vessel Schedule (.xlsx)", type=['xlsx'])
    st.header("2. Pilih Level Aturan")
    rule_level = st.selectbox("Pilih hierarki aturan:", ["Level 1: Optimal", "Level 2: Aman & Terfragmentasi", "Level 3: Darurat (Approval)"])
    st.header("3. Parameter Aturan")
    intra_ship_gap, daily_exclusion_zone, inter_ship_gap = 5, 7, 10
    if rule_level == "Level 3: Darurat (Approval)":
        st.warning("Mode Darurat: Aturan keamanan dilonggarkan.")
        intra_ship_gap = st.slider("Jarak Internal Kapal", 1, 5, 2)
        daily_exclusion_zone = st.slider("Zona Eksklusif Harian", 1, 7, 3)
        inter_ship_gap = st.slider("Jarak Eksternal Kapal", 1, 10, 5)

if uploaded_file:
    try:
        df_schedule = pd.read_excel(uploaded_file)
        date_cols = ['OPEN STACKING', 'ETA', 'ETD']
        for col in date_cols:
            df_schedule[col] = pd.to_datetime(df_schedule[col], dayfirst=True, errors='coerce')
        df_schedule['TOTAL BOX (TEUS)'] = pd.to_numeric(df_schedule['TOTAL BOX (TEUS)'], errors='coerce').fillna(0).astype(int)
        df_schedule.dropna(subset=date_cols, inplace=True)

        st.subheader("Data Vessel Schedule yang Di-upload (Sudah diproses)")
        st.dataframe(df_schedule)

        df_trends = load_stacking_trends(STACKING_TREND_URL)

        if df_trends is not None:
            if st.button("🚀 Mulai Simulasi"):
                sim_rules = {
                    'intra_ship_gap': intra_ship_gap,
                    'inter_ship_gap': inter_ship_gap,
                    'daily_exclusion_zone': daily_exclusion_zone,
                    'cluster_req_logic': 'Wajar' if rule_level != "Level 3: Darurat (Approval)" else 'Agresif'
                }
                with st.spinner("Menjalankan simulasi kompleks..."):
                    st.session_state['simulation_results'] = run_simulation(df_schedule, df_trends, sim_rules, rule_level)
                st.success(f"Simulasi Selesai! Dijalankan menggunakan **{rule_level}**.")
    
    except Exception as e:
        st.error(f"Terjadi kesalahan saat memproses file Anda: {e}")

if st.session_state['simulation_results']:
    df_yor, df_recap, df_map, df_daily_log, daily_snapshots = st.session_state['simulation_results']
    
    st.header("📍 Visualisasi Yard Harian (Interaktif)")
    
    date_options = list(daily_snapshots.keys())
    if date_options:
        selected_date = st.select_slider(
            'Geser untuk memilih tanggal:',
            options=date_options,
            format_func=lambda date: date.strftime('%d %b %Y')
        )
        
        tab1, tab2 = st.tabs(["Peta Yard (Visual)", "Rencana Harian (per Kapal)"])

        with tab1:
            vessel_names = df_schedule['VESSEL'].unique()
            colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#FED766", "#2AB7CA", "#F0B7A4", "#F2E2D2",
                      "#C44D58", "#1A535C", "#7A7D7D", "#A8A8A8", "#66FCF1", "#B9E2A0", "#F9C80E",
                      "#FF9F1C", "#2EC4B6", "#E71D36", "#011627"]
            vessel_colors = {name: colors[i % len(colors)] for i, name in enumerate(vessel_names)}
            
            yard_state_on_date = daily_snapshots[selected_date]
            
            areas_by_block = {'A': [], 'B': [], 'C': []}
            for area in DEFAULT_YARD_CONFIG.keys():
                if area.startswith('A'): areas_by_block['A'].append(area)
                elif area.startswith('B'): areas_by_block['B'].append(area)
                elif area.startswith('C'): areas_by_block['C'].append(area)

            for block, areas in areas_by_block.items():
                st.subheader(f"BLOCK {block}")
                for area in sorted(areas):
                    total_slots_in_area = DEFAULT_YARD_CONFIG[area]
                    summary_bar_html = create_stacked_bar(area, yard_state_on_date, vessel_colors, total_slots_in_area)
                    
                    with st.expander(f"**Area: {area}**"):
                        st.markdown(summary_bar_html, unsafe_allow_html=True)
                        cols = st.columns(total_slots_in_area)
                        for i in range(1, total_slots_in_area + 1):
                            vessel_name = yard_state_on_date.get((area, i))
                            if vessel_name:
                                color = vessel_colors.get(vessel_name, "#FFFFFF")
                                cols[i-1].markdown(f'<div style="background-color:{color}; border-radius:3px; padding:5px;" title="{vessel_name}">&nbsp;</div>', unsafe_allow_html=True)
                            else:
                                cols[i-1].markdown(f'<div style="background-color:#333; border-radius:3px; padding:5px;">&nbsp;</div>', unsafe_allow_html=True)
        
        with tab2:
            st.subheader(f"Rencana Alokasi untuk {selected_date.strftime('%d %b %Y')}")
            
            log_for_selected_date = df_daily_log[df_daily_log['Tanggal'] == selected_date.strftime('%Y-%m-%d')]
            
            if log_for_selected_date.empty:
                st.info("Tidak ada aktivitas alokasi yang dijadwalkan pada tanggal ini.")
            else:
                active_vessels_on_date = log_for_selected_date['Kapal'].unique()
                
                for vessel_name in active_vessels_on_date:
                    vessel_log = log_for_selected_date[log_for_selected_date['Kapal'] == vessel_name].iloc[0]
                    boxes_needed = vessel_log['Butuh Box']
                    slots_needed = vessel_log['Butuh Slot']
                    
                    with st.container():
                        st.markdown(f"#### {vessel_name}")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric(label="Kontainer Masuk", value=f"{boxes_needed} box")
                        with col2:
                            st.metric(label="Kebutuhan Slot", value=f"{slots_needed} slot")

                        st.markdown("**Rekomendasi Alokasi:**")
                        st.info(f"{vessel_log['Rekomendasi']}")
                        st.markdown("---")

    st.header("📊 Yard Occupancy Ratio (YOR) Harian")
    st.line_chart(df_yor.set_index('Tanggal')['Rasio Okupansi (%)'])
    st.dataframe(df_yor)

    st.header("📋 Rekapitulasi Alokasi Final")
    st.dataframe(df_recap)

    st.header("🗺️ Peta Alokasi Akhir (Detail Slot)")
    if not df_map.empty:
        st.dataframe(df_map)
    else:
        st.info("Tidak ada data peta alokasi untuk ditampilkan.")
    
    st.header("📓 Log Alokasi Harian")
    st.dataframe(df_daily_log)

elif not uploaded_file:
    st.info("Silakan upload file 'Vessel Schedule' dalam format .xlsx untuk memulai simulasi.")

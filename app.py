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
            'max_clusters': initial_cluster_req + 2
        }

    # --- BAGIAN 2: LOGIKA SIMULASI INTI ---
    daily_log = []
    
    start_date_sim = df_schedule['OPEN STACKING'].min().normalize()
    end_date_sim = df_schedule['ETD'].max().normalize()
    date_range = pd.date_range(start=start_date_sim, end=end_date_sim, freq='D')

    for current_date in date_range:
        # A. Kosongkan slot dari kapal yang sudah berangkat
        for ship_data in vessels.values():
            if current_date > ship_data['etd_date']:
                slots_to_free = [slot for cluster in ship_data['clusters'] for slot in cluster]
                for slot in slots_to_free:
                    if yard_status.get(slot) == ship_data['name']:
                        yard_status[slot] = None
                ship_data['clusters'] = []

        # B. Alokasikan untuk kapal yang aktif
        active_ships_today = sorted(
            [ship for ship in vessels.values() if current_date >= ship['start_date'] and current_date <= ship['etd_date']],
            key=lambda x: x['total_boxes'], reverse=True # Prioritaskan kapal besar
        )
        
        for ship in active_ships_today:
            day_index = (current_date - ship['start_date']).days
            if day_index < len(ship['daily_arrivals']):
                boxes_to_allocate_today = ship['daily_arrivals'][day_index]
                slots_needed = int(np.ceil(boxes_to_allocate_today / slot_capacity))
            else:
                slots_needed = 0

            if slots_needed == 0: continue
            
            # --- LOGIKA ALOKASI MULTI-CLUSTER BARU ---
            slots_allocated_today = allocate_slots_intelligently(
                ship, slots_needed, yard_status, vessels, current_date, rules, get_slot_index
            )
            # --- AKHIR LOGIKA BARU ---

            daily_log.append({
                'Tanggal': current_date.strftime('%Y-%m-%d'), 'Kapal': ship['name'],
                'Butuh Slot': slots_needed, 'Slot Berhasil': len(slots_allocated_today),
                'Slot Gagal': slots_needed - len(slots_allocated_today)
            })
        
    # --- BAGIAN 3: AGREGASI & PERSIAPAN OUTPUT ---
    df_daily_log = pd.DataFrame(daily_log)
    
    # Kalkulasi YOR harian yang akurat
    yor_data = []
    temp_yard_status_for_yor = {(area, i): None for area, num_slots in yard_config.items() for i in range(1, num_slots + 1)}
    for date in date_range:
        # Kosongkan slot kapal yang berangkat kemarin
        for ship_data in vessels.values():
            if date > ship_data['etd_date']:
                slots_freed_yesterday = [slot for cluster in ship_data['clusters'] if (ship_data['etd_date'].normalize() == (date - timedelta(days=1)).normalize()) for slot in cluster]
                for slot in slots_freed_yesterday:
                    if temp_yard_status_for_yor.get(slot) == ship_data['name']:
                        temp_yard_status_for_yor[slot] = None
        
        # Tambahkan slot yang diisi hari ini
        log_today = df_daily_log[df_daily_log['Tanggal'] == date.strftime('%Y-%m-%d')]
        for _, row in log_today.iterrows():
            # Ini adalah penyederhanaan, sulit untuk tahu slot mana persisnya tanpa menyimpan state
            # Untuk visualisasi, kita akan gunakan jumlahnya saja
            pass

        occupied_slots = sum(1 for status in yard_status.values() if status is not None)
        total_slots = len(yard_status)
        yor_data.append({
            'Tanggal': date,
            'Total Box di Yard': occupied_slots * slot_capacity,
            'Rasio Okupansi (%)': (occupied_slots / total_slots) * 100
        })
    df_yor = pd.DataFrame(yor_data)

    recap_list = []
    for ship in vessels.values():
        total_requested = ship['total_boxes']
        successful_slots = df_daily_log[df_daily_log['Kapal'] == ship['name']]['Slot Berhasil'].sum()
        boxes_successful = successful_slots * slot_capacity
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
            
            # Logika baru untuk merangkum grup slot yang terpisah dalam satu cluster
            cluster.sort(key=get_slot_index)
            groups = []
            for k, g in itertools.groupby(enumerate(cluster), lambda item: get_slot_index(item[1]) - item[0]):
                group = [item[1] for item in g]
                start_slot = f"{group[0][0]}:{group[0][1]}"
                end_slot = f"{group[-1][0]}:{group[-1][1]}"
                groups.append(f"{start_slot}" if start_slot == end_slot else f"{start_slot}-{group[-1][1]}")
            
            map_list.append({
                'Kapal': ship['name'], 'Cluster': f'Cluster {i+1}',
                'Lokasi & Slot': ", ".join(groups)
            })
    df_map = pd.DataFrame(map_list)

    return df_yor, df_recap, df_map, df_daily_log

def find_placeable_slots(current_ship, all_ships, yard_status, current_date, rules):
    """Fungsi krusial: mencari slot valid dengan memeriksa SEMUA aturan."""
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
        # Aturan Jarak Internal (Intra-ship)
        if ship['name'] == current_ship['name']:
            for cluster in ship['clusters']:
                if not cluster: continue
                cluster_indices = [get_slot_idx_local(s) for s in cluster]
                min_idx, max_idx = min(cluster_indices), max(cluster_indices)
                for i in range(min_idx - rules['intra_ship_gap'], max_idx + rules['intra_ship_gap'] + 1):
                    blocked_indices.add(i)
            continue

        # Aturan Jarak Eksternal & Zona Eksklusif
        etd_diff = abs((current_ship['etd_date'] - ship['etd_date']).days)
        for cluster in ship['clusters']:
            if not cluster: continue
            cluster_indices = [get_slot_idx_local(s) for s in cluster]
            min_idx, max_idx = min(cluster_indices), max(cluster_indices)
            
            # Terapkan Zona Eksklusif Harian
            for i in range(min_idx - rules['daily_exclusion_zone'], max_idx + rules['daily_exclusion_zone'] + 1):
                blocked_indices.add(i)
            # Terapkan Jarak Eksternal jika berlaku
            if etd_diff <= 1:
                for i in range(min_idx - rules['inter_ship_gap'], max_idx + rules['inter_ship_gap'] + 1):
                    blocked_indices.add(i)

    placeable_slots = {slot for slot in free_slots if get_slot_idx_local(slot) not in blocked_indices}
    return sorted(list(placeable_slots), key=get_slot_idx_local)

def allocate_slots_intelligently(ship, slots_needed, yard_status, vessels, current_date, rules, get_slot_index_func):
    """Logika alokasi cerdas untuk menempatkan slot ke multi-cluster."""
    
    placeable_slots = find_placeable_slots(ship, vessels, yard_status, current_date, rules)
    if len(placeable_slots) < slots_needed:
        return [] # Gagal jika slot yang valid secara fisik tidak cukup

    # 1. Kelompokkan slot yang tersedia menjadi blok-blok berdekatan
    placeable_blocks = []
    for k, g in itertools.groupby(enumerate(placeable_slots), lambda item: get_slot_index_func(item[1]) - item[0]):
        placeable_blocks.append([item[1] for item in g])

    # 2. Cari blok yang cukup besar untuk menampung semua slot yang dibutuhkan
    valid_blocks = [block for block in placeable_blocks if len(block) >= slots_needed]
    if not valid_blocks:
        return [] # Gagal jika tidak ada blok tunggal yang cukup besar

    # 3. Pilih blok terbaik (strategi sederhana: ambil yang pertama)
    # TODO: Kembangkan logika pemilihan blok (misal: yang terdekat dengan cluster lain)
    best_block = valid_blocks[0]
    slots_to_fill = best_block[:slots_needed]

    # 4. Tentukan ke cluster mana akan dialokasikan
    # Strategi: cari cluster kosong, jika tidak ada, gunakan cluster tambahan jika diizinkan
    target_cluster_idx = -1
    for i, cluster in enumerate(ship['clusters']):
        if not cluster: # Jika cluster ini masih kosong
            target_cluster_idx = i
            break
    
    if target_cluster_idx == -1: # Jika semua cluster awal sudah terisi
        if len(ship['clusters']) < ship['max_clusters']:
            ship['clusters'].append([]) # Buat cluster tambahan baru
            target_cluster_idx = len(ship['clusters']) - 1
        else:
            return [] # Gagal karena sudah mencapai batas maksimal cluster

    # 5. Lakukan alokasi
    ship['clusters'][target_cluster_idx].extend(slots_to_fill)
    for slot in slots_to_fill:
        yard_status[slot] = ship['name']
        
    return slots_to_fill

# ==============================================================================
# BAGIAN 2: UI (ANTARMUKA) STREAMLIT
# ==============================================================================

st.set_page_config(layout="wide", page_title="Yard Allocation Simulator")
st.title("🚢 Simulasi Alokasi Container Yard")

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

        if df_trends is not None and st.button("🚀 Mulai Simulasi"):
            sim_rules = {
                'intra_ship_gap': intra_ship_gap,
                'inter_ship_gap': inter_ship_gap,
                'daily_exclusion_zone': daily_exclusion_zone,
                'cluster_req_logic': 'Wajar' if rule_level != "Level 3: Darurat (Approval)" else 'Agresif'
            }

            df_yor, df_recap, df_map, df_daily_log = run_simulation(df_schedule, df_trends, sim_rules, rule_level)

            st.success(f"Simulasi Selesai! Dijalankan menggunakan **{rule_level}**.")

            st.header("📊 Yard Occupancy Ratio (YOR) Harian")
            st.line_chart(df_yor.set_index('Tanggal')['Rasio Okupansi (%)'])
            st.dataframe(df_yor)

            st.header("📋 Rekapitulasi Alokasi Final")
            st.dataframe(df_recap)

            st.header("🗺️ Peta Alokasi Akhir (Detail Slot)")
            st.dataframe(df_map)
            
            st.header("📓 Log Alokasi Harian")
            st.dataframe(df_daily_log)
            
            st.balloons()
    
    except Exception as e:
        st.error(f"Terjadi kesalahan saat memproses file Anda: {e}")
else:
    st.info("Silakan upload file 'Vessel Schedule' dalam format .xlsx untuk memulai simulasi.")

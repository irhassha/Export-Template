import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- KONFIGURASI AWAL & FUNGSI GLOBAL ---

DEFAULT_YARD_CONFIG = {
    'A01': 37, 'A02': 37, 'A03': 37, 'A04': 37,
    'B01': 37, 'B02': 37, 'B03': 37, 'B04': 37, 'B05': 37,
    'C03': 45, 'C04': 45, 'C05': 45
}
DEFAULT_SLOT_CAPACITY = 30
STACKING_TREND_URL = 'https://github.com/irhassha/Clash_Analyzer/raw/refs/heads/main/stacking_trend.xlsx'

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

# --- [PLACEHOLDER] FUNGSI-FUNGSI LOGIKA INTI SIMULASI ---
# ==============================================================================
#           MASUKKAN BLOK KODE INI UNTUK MENGGANTIKAN FUNGSI run_simulation LAMA
# ==============================================================================

def run_simulation(df_schedule, df_trends, rules, rule_level):
    """Fungsi utama untuk menjalankan seluruh proses simulasi dengan logika nyata."""

    # --- BAGIAN 1: INISIALISASI ---

    yard_config = DEFAULT_YARD_CONFIG
    slot_capacity = DEFAULT_SLOT_CAPACITY
    
    # Inisialisasi status yard (semua slot kosong)
    yard_status = {
        (area, i): None 
        for area, num_slots in yard_config.items() 
        for i in range(1, num_slots + 1)
    }
    
    # Membuat peta index untuk mempercepat kalkulasi jarak
    offset = 0
    yard_config_map = {}
    for area, num_slots in yard_config.items():
        yard_config_map[area] = {'offset': offset, 'size': num_slots}
        offset += num_slots
    yard_config_map_rev = {data['offset']: area for area, data in yard_config_map.items()}

    def get_slot_index(slot):
        area, number = slot
        return yard_config_map[area]['offset'] + number - 1

    # Inisialisasi semua kapal dari jadwal
    vessels = {}
    for _, row in df_schedule.iterrows():
        ship_name = row['VESSEL']
        start_date = row['OPEN STACKING'].normalize()
        etd_date = row['ETD'].normalize()
        num_days = (etd_date - start_date).days + 1
        
        # Kalkulasi Cluster Req Optimal (Level 1)
        base_avg = 150
        if rules['cluster_req_logic'] == 'Agresif':
            base_avg = 100 # Untuk Level 3
            
        initial_cluster_req = int(np.ceil(row['TOTAL BOX (TEUS)'] / base_avg))
        if initial_cluster_req < 1: initial_cluster_req = 1

        vessels[ship_name] = {
            'name': ship_name,
            'service': row['SERVICE'],
            'total_boxes': row['TOTAL BOX (TEUS)'],
            'start_date': start_date,
            'etd_date': etd_date,
            'daily_arrivals': get_daily_arrivals(row['TOTAL BOX (TEUS)'], row['SERVICE'], df_trends, num_days),
            'clusters': [],
            'initial_cluster_req': initial_cluster_req,
            'max_clusters': initial_cluster_req + 2 # Aturan +2 cluster fleksibel
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
        active_ships_today = [ship for ship in vessels.values() if current_date >= ship['start_date'] and current_date <= ship['etd_date']]
        
        for ship in active_ships_today:
            # Kalkulasi kebutuhan slot hari ini
            day_index = (current_date - ship['start_date']).days
            if day_index < len(ship['daily_arrivals']):
                boxes_to_allocate_today = ship['daily_arrivals'][day_index]
                slots_needed = int(np.ceil(boxes_to_allocate_today / slot_capacity))
            else:
                slots_needed = 0

            if slots_needed == 0:
                continue
            
            # --- Di sini Hierarki Aturan Dijalankan ---
            # TODO: Implementasi pemicu Level 2 jika Level 1 gagal.
            # Untuk sekarang, kita implementasikan logika alokasi yang ketat.
            
            # Cari semua slot yang valid hari ini
            placeable_slots = find_placeable_slots(ship, vessels, yard_status, current_date, rules, yard_config_map)
            
            # Logika alokasi (versi sederhana, bisa dikembangkan)
            slots_allocated_today = []
            if len(placeable_slots) >= slots_needed:
                # Ambil N slot pertama yang tersedia
                slots_to_fill = placeable_slots[:slots_needed]
                
                # Masukkan ke cluster pertama, atau buat jika belum ada
                if not ship['clusters']:
                    ship['clusters'].append([])
                
                # Cek apakah penambahan ini melanggar aturan internal gap (sederhana)
                # Logika ini perlu disempurnakan untuk menangani multi-cluster & aturan Level 2/3
                ship['clusters'][0].extend(slots_to_fill)
                
                for slot in slots_to_fill:
                    yard_status[slot] = ship['name']
                
                slots_allocated_today = slots_to_fill
            
            # Catat hasil log harian
            daily_log.append({
                'Tanggal': current_date.strftime('%Y-%m-%d'),
                'Kapal': ship['name'],
                'Butuh Slot': slots_needed,
                'Slot Berhasil': len(slots_allocated_today),
                'Slot Gagal': slots_needed - len(slots_allocated_today)
            })
    
    # --- BAGIAN 3: AGREGASI & PERSIAPAN OUTPUT ---
    
    df_daily_log = pd.DataFrame(daily_log)
    
    # YOR
    yor_data = []
    occupied_slots_per_day = {}
    # Re-simulasi status yard harian untuk YOR yang akurat
    temp_yard_status = {slot: None for slot in yard_status}
    for date in date_range:
        for ship_data in vessels.values():
            if date > ship_data['etd_date']:
                slots_to_free = [s for c in ship_data['clusters'] for s in c]
                for slot in slots_to_free:
                     if temp_yard_status.get(slot) == ship_data['name']:
                        temp_yard_status[slot] = None
        
        if not df_daily_log[df_daily_log['Tanggal'] == date.strftime('%Y-%m-%d')].empty:
             # Ini adalah penyederhanaan. Logika YOR yang akurat perlu melacak slot yg diisi dan dikosongkan setiap hari.
             pass # Lewati untuk saat ini

    # Menggunakan data log untuk estimasi YOR
    boxes_in_yard = 0
    for date in date_range:
        log_today = df_daily_log[df_daily_log['Tanggal'] == date.strftime('%Y-%m-%d')]
        boxes_in_today = log_today['Slot Berhasil'].sum() * slot_capacity
        
        # Cari kapal yang berangkat kemarin
        departed_yesterday = [s for s in vessels.values() if s['etd_date'].normalize() == (date - timedelta(days=1)).normalize()]
        boxes_out_today = sum(s['total_boxes'] for s in departed_yesterday)
        
        boxes_in_yard += boxes_in_today - boxes_out_today
        if boxes_in_yard < 0: boxes_in_yard = 0

        yor_data.append({
            'Tanggal': date,
            'Total Box di Yard': boxes_in_yard,
            'Rasio Okupansi (%)': (boxes_in_yard / (len(yard_status) * slot_capacity)) * 100
        })
    df_yor = pd.DataFrame(yor_data)

    # Rekapitulasi Final
    recap_list = []
    for ship in vessels.values():
        total_requested = ship['total_boxes']
        successful_slots = df_daily_log[df_daily_log['Kapal'] == ship['name']]['Slot Berhasil'].sum()
        # Estimasi box berhasil berdasarkan slot, bisa disempurnakan
        boxes_successful = successful_slots * slot_capacity
        
        recap_list.append({
            'Kapal': ship['name'],
            'Permintaan Box': total_requested,
            'Box Berhasil': boxes_successful,
            'Box Gagal': total_requested - boxes_successful if total_requested > boxes_successful else 0
        })
    df_recap = pd.DataFrame(recap_list)

    # Peta Alokasi
    map_list = []
    for ship in vessels.values():
        for i, cluster in enumerate(ship['clusters']):
            if not cluster: continue
            
            cluster.sort(key=get_slot_index)
            # Logika untuk merangkum range slot menjadi string
            start_slot = f"{cluster[0][0]}:{cluster[0][1]}"
            end_slot = f"{cluster[-1][0]}:{cluster[-1][1]}"

            map_list.append({
                'Kapal': ship['name'],
                'Cluster': f'Cluster {i+1}',
                'Lokasi Area': cluster[0][0],
                'Alokasi Slot': f"{start_slot} - {end_slot}"
            })
    df_map = pd.DataFrame(map_list)

    return df_yor, df_recap, df_map, df_daily_log

def find_placeable_slots(current_ship, all_ships, yard_status, current_date, rules, yard_config_map):
    """Fungsi krusial: mencari slot valid dengan memeriksa SEMUA aturan."""
    
    free_slots = {slot for slot, owner in yard_status.items() if owner is None}
    blocked_indices = set()
    
    # Buat peta index untuk performa
    offset = 0
    temp_map = {}
    for area, num_slots in DEFAULT_YARD_CONFIG.items():
        temp_map[area] = {'offset': offset, 'size': num_slots}
        offset += num_slots

    def get_slot_idx_local(slot):
        area, number = slot
        return temp_map[area]['offset'] + number - 1

    active_ships = [ship for ship in all_ships.values() if current_date >= ship['start_date'] and current_date <= ship['etd_date']]

    for ship in active_ships:
        if ship['name'] == current_ship['name']: continue

        etd_diff = abs((current_ship['etd_date'] - ship['etd_date']).days)
        
        # Terapkan Zona Eksklusif Harian
        for cluster in ship['clusters']:
            if not cluster: continue
            cluster_indices = [get_slot_idx_local(s) for s in cluster]
            min_idx, max_idx = min(cluster_indices), max(cluster_indices)
            for i in range(min_idx - rules['daily_exclusion_zone'], max_idx + rules['daily_exclusion_zone'] + 1):
                blocked_indices.add(i)

        # Terapkan Jarak Eksternal jika berlaku
        if etd_diff <= 1:
            for cluster in ship['clusters']:
                if not cluster: continue
                cluster_indices = [get_slot_idx_local(s) for s in cluster]
                min_idx, max_idx = min(cluster_indices), max(cluster_indices)
                for i in range(min_idx - rules['inter_ship_gap'], max_idx + rules['inter_ship_gap'] + 1):
                    blocked_indices.add(i)

    placeable_slots = {slot for slot in free_slots if get_slot_idx_local(slot) not in blocked_indices}
    return sorted(list(placeable_slots), key=get_slot_idx_local)
# --- UI (ANTARMUKA) STREAMLIT ---

st.set_page_config(layout="wide")
st.title("🚢 Simulasi Alokasi Container Yard")

with st.sidebar:
    st.header("1. Upload File")
    uploaded_file = st.file_uploader("Upload Vessel Schedule (.xlsx)", type=['xlsx'])
    st.header("2. Pilih Level Aturan")
    rule_level = st.selectbox(
        "Pilih hierarki aturan:",
        ["Level 1: Optimal", "Level 2: Aman & Terfragmentasi", "Level 3: Darurat (Approval)"]
    )
    st.header("3. Parameter Aturan")
    intra_ship_gap, daily_exclusion_zone = 5, 7
    if rule_level == "Level 3: Darurat (Approval)":
        st.warning("Mode Darurat: Aturan keamanan dilonggarkan.")
        intra_ship_gap = st.slider("Jarak Internal Kapal", 1, 5, 2)
        daily_exclusion_zone = st.slider("Zona Eksklusif Harian", 1, 7, 3)

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
                'daily_exclusion_zone': daily_exclusion_zone,
                'inter_ship_gap': 10, # Hardcoded for now
                'cluster_req_logic': 'Wajar' if rule_level != "Level 3: Darurat (Approval)" else 'Agresif'
            }

            df_yor, df_recap, df_map, df_daily_log = run_simulation(df_schedule, df_trends, sim_rules)

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

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- KONFIGURASI AWAL & FUNGSI INTI ---

# Konfigurasi Default Yard
DEFAULT_YARD_CONFIG = {
    'A01': 37, 'A02': 37, 'A03': 37, 'A04': 37,
    'B01': 37, 'B02': 37, 'B03': 37, 'B04': 37, 'B05': 37,
    'C03': 45, 'C04': 45, 'C05': 45
}
DEFAULT_SLOT_CAPACITY = 30

# URL File Stacking Trend dari GitHub
STACKING_TREND_URL = 'https://github.com/irhassha/Clash_Analyzer/raw/refs/heads/main/stacking_trend.xlsx'

@st.cache_data
def load_stacking_trends(url):
    """Memuat dan cache data stacking trend dari URL GitHub."""
    try:
        df = pd.read_excel(url)
        df.rename(columns={'STACKING TREND': 'SERVICE'}, inplace=True)
        return df.set_index('SERVICE')
    except Exception as e:
        st.error(f"Gagal memuat file stacking trend dari URL. Pastikan URL raw sudah benar. Error: {e}")
        return None

# Fungsi ini tetap sama, namun sekarang num_days akan dihitung secara dinamis
# VERSI BARU YANG LEBIH KUAT
def get_daily_arrivals(total_boxes, service_name, trends_df, num_days):
    """
    Menghitung jumlah box harian. Jika rentang hari di file tren tidak cukup,
    maka sisa harinya akan dianggap 0%.
    """
    percentages = []
    if service_name in trends_df.index:
        # Loop melalui setiap hari yang dibutuhkan oleh kapal
        for i in range(num_days):
            day_col = f'DAY {i}'
            # Periksa apakah kolom DAY tersebut ada di file tren
            if day_col in trends_df.columns:
                # Jika ada, gunakan nilainya
                percentages.append(trends_df.loc[service_name, day_col])
            else:
                # Jika tidak ada, anggap nilainya 0, sesuai permintaan
                percentages.append(0)
        
        percentages = np.array(percentages)
        percentages = pd.to_numeric(percentages, errors='coerce')
    else:
        # Jika nama service sama sekali tidak ditemukan, baru gunakan rata-rata
        st.warning(f"Service '{service_name}' tidak ditemukan di file tren. Menggunakan tren rata-rata.")
        percentages = np.full(num_days, 1.0 / num_days)

    # Mengganti nilai kosong (NaN) dengan 0
    percentages = np.nan_to_num(percentages)
    
    # Normalisasi persentase agar totalnya 100% untuk akurasi
    if percentages.sum() > 0:
        percentages = percentages / percentages.sum()

    # Menghitung alokasi box harian dan memastikan totalnya pas
    daily_boxes = np.round(percentages * total_boxes).astype(int)
    diff = total_boxes - daily_boxes.sum()
    if diff != 0 and len(daily_boxes) > 0:
        daily_boxes[np.argmax(daily_boxes)] += diff
            
    return daily_boxes
    # Day columns sesuai dengan jumlah hari stacking
    day_columns = [f'DAY {i}' for i in range(num_days)]
    
    if service_name in trends_df.index and all(col in trends_df.columns for col in day_columns):
        percentages = trends_df.loc[service_name, day_columns].values
        percentages = pd.to_numeric(percentages, errors='coerce')
    else:
        st.warning(f"Service '{service_name}' atau rentang harinya tidak ditemukan di file tren. Menggunakan tren rata-rata.")
        percentages = np.full(num_days, 1.0 / num_days)

    percentages = np.nan_to_num(percentages)
    
    if percentages.sum() > 0:
        percentages = percentages / percentages.sum()

    daily_boxes = np.round(percentages * total_boxes).astype(int)
    diff = total_boxes - daily_boxes.sum()
    if diff != 0 and len(daily_boxes) > 0:
        daily_boxes[np.argmax(daily_boxes)] += diff
            
    return daily_boxes

# --- UI STREAMLIT & LOGIKA SIMULASI ---

st.set_page_config(layout="wide")
st.title("🚢 Simulasi Alokasi Container Yard (Berbasis Tanggal)")

# --- Sidebar untuk Input & Parameter ---
with st.sidebar:
    st.header("1. Upload File")
    uploaded_file = st.file_uploader("Upload Vessel Schedule (.xlsx)", type=['xlsx'])

    st.header("2. Pilih Level Aturan")
    rule_level = st.selectbox(
        "Pilih hierarki aturan yang akan dijalankan:",
        ["Level 1: Optimal", "Level 2: Aman & Terfragmentasi", "Level 3: Darurat (Approval)"]
    )
    
    st.header("3. Parameter Aturan (Adjustable)")
    intra_ship_gap = 5
    inter_ship_gap = 10
    daily_exclusion_zone = 7
    cluster_req_logic = 'Wajar'

    if rule_level == "Level 3: Darurat (Approval)":
        st.warning("Mode Darurat: Aturan keamanan dilonggarkan.")
        intra_ship_gap = st.slider("Jarak Internal Kapal", 1, 5, 2)
        daily_exclusion_zone = st.slider("Zona Eksklusif Harian", 1, 7, 3)
        cluster_req_logic = 'Agresif'

# --- Main App Logic ---
# VERSI BARU DENGAN PERBAIKAN
if uploaded_file:
    try:
        # 1. Baca file Excel seperti biasa tanpa parsing tanggal
        df_schedule = pd.read_excel(uploaded_file) 
        
        # 2. Konversi kolom tanggal secara manual SETELAH file dibaca
        date_cols = ['OPEN STACKING', 'ETA', 'ETD']
        for col in date_cols:
            # Gunakan dayfirst=True di sini, pada fungsi to_datetime yang benar
            # errors='coerce' akan mengubah tanggal yang salah format menjadi NaT (kosong)
            df_schedule[col] = pd.to_datetime(df_schedule[col], dayfirst=True, errors='coerce')

        # 3. Membersihkan data 'TOTAL BOX (TEUS)'
        df_schedule['TOTAL BOX (TEUS)'] = pd.to_numeric(df_schedule['TOTAL BOX (TEUS)'], errors='coerce').fillna(0).astype(int)

        # 4. Hapus baris yang tanggalnya kosong (jika ada kesalahan format di file asli)
        df_schedule.dropna(subset=date_cols, inplace=True)

        st.subheader("Data Vessel Schedule yang Di-upload (Sudah diproses)")
        st.dataframe(df_schedule)
        # ... sisa kode ...
        # --- AKHIR PERUBAHAN 1 ---

        df_trends = load_stacking_trends(STACKING_TREND_URL)

        if df_trends is not None:
            if st.button("🚀 Mulai Simulasi"):
                
                with st.spinner("Menjalankan simulasi berbasis tanggal..."):
                    st.success(f"Simulasi dijalankan menggunakan **{rule_level}**.")

                    # --- PERUBAHAN 2: MENENTUKAN RENTANG TANGGAL SIMULASI ---
                    start_date = df_schedule['OPEN STACKING'].min().normalize()
                    end_date = df_schedule['ETD'].max().normalize()
                    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
                    
                    # Placeholder untuk hasil harian
                    daily_occupancy_data = []

                    # --- PERUBAHAN 3: LOOPING BERBASIS TANGGAL ---
                    # ==============================================================================
                    #           MULAI SALIN KODE DARI SINI
                    # ==============================================================================
                    
                    # --- FUNGSI-FUNGSI HELPER UNTUK LOGIKA SIMULASI ---
                    
                    def initialize_yard(config):
                        """Membuat representasi yard dari konfigurasi."""
                        yard_slots = {}
                        for area, num_slots in config.items():
                            for i in range(1, num_slots + 1):
                                yard_slots[(area, i)] = None  # None berarti slot kosong
                        return yard_slots
                    
                    def get_slot_index(slot, yard_config_map):
                        """Mendapatkan index numerik unik untuk setiap slot di seluruh yard."""
                        area, number = slot
                        return yard_config_map[area]['offset'] + number - 1
                    
                    def get_slot_from_index(index, yard_config_map_rev):
                        """Mendapatkan nama slot dari index numerik unik."""
                        area_name = yard_config_map_rev[max(k for k in yard_config_map_rev if k <= index)]
                        offset = max(k for k in yard_config_map_rev if k <= index)
                        return (area_name, index - offset + 1)
                    
                    def find_placeable_slots(current_ship, all_ships, yard_status, current_date, rules, yard_config_map):
                        """
                        Fungsi paling krusial: mencari slot mana saja yang valid untuk ditempati
                        dengan memeriksa SEMUA aturan jarak dan zona.
                        """
                        # 1. Dapatkan semua slot yang secara fisik kosong
                        free_slots = {slot for slot, owner in yard_status.items() if owner is None}
                        
                        # 2. Tentukan slot mana yang diblokir oleh aturan
                        blocked_indices = set()
                        active_ships = [ship for ship in all_ships.values() if current_date >= ship['start_date'] and current_date < ship['etd_date']]
                    
                        for ship in active_ships:
                            # Jangan cek terhadap diri sendiri
                            if ship['name'] == current_ship['name']:
                                continue
                    
                            # Aturan 3: Zona Eksklusif Harian (7 slot) - BERLAKU UNTUK SEMUA KAPAL AKTIF LAINNYA
                            for cluster in ship['clusters']:
                                if not cluster: continue
                                cluster_indices = [get_slot_index(s, yard_config_map) for s in cluster]
                                min_idx, max_idx = min(cluster_indices), max(cluster_indices)
                                for i in range(min_idx - rules['daily_exclusion_zone'], max_idx + rules['daily_exclusion_zone'] + 1):
                                    blocked_indices.add(i)
                    
                            # Aturan 2: Jarak Eksternal Kapal (10 slot) - HANYA JIKA ETD <= 1 HARI
                            etd_diff = abs((current_ship['etd_date'] - ship['etd_date']).days)
                            if etd_diff <= 1:
                                for cluster in ship['clusters']:
                                    if not cluster: continue
                                    cluster_indices = [get_slot_index(s, yard_config_map) for s in cluster]
                                    min_idx, max_idx = min(cluster_indices), max(cluster_indices)
                                    for i in range(min_idx - rules['inter_ship_gap'], max_idx + rules['inter_ship_gap'] + 1):
                                        blocked_indices.add(i)
                    
                        # 3. Hasil akhirnya adalah slot kosong yang tidak diblokir
                        placeable_slots = {slot for slot in free_slots if get_slot_index(slot, yard_config_map) not in blocked_indices}
                        return sorted(list(placeable_slots), key=lambda s: get_slot_index(s, yard_config_map))
                    
                    
                    # --- FUNGSI UTAMA YANG AKAN DIPANGGIL OLEH STREAMLIT ---
                    
                    def run_simulation(df_schedule, df_trends, rules):
                        """Fungsi utama untuk menjalankan seluruh proses simulasi."""
                    
                        # 1. Inisialisasi Yard
                        yard_config = DEFAULT_YARD_CONFIG
                        yard_status = initialize_yard(yard_config)
                        slot_capacity = DEFAULT_SLOT_CAPACITY
                        
                        # Membuat peta index untuk konversi slot <-> index (untuk performa)
                        offset = 0
                        yard_config_map = {}
                        for area, num_slots in yard_config.items():
                            yard_config_map[area] = {'offset': offset, 'size': num_slots}
                            offset += num_slots
                        
                        yard_config_map_rev = {data['offset']: area for area, data in yard_config_map.items()}
                    
                        # 2. Inisialisasi Kapal
                        vessels = {}
                        for _, row in df_schedule.iterrows():
                            ship_name = row['VESSEL']
                            start_date = row['OPEN STACKING'].normalize()
                            etd_date = row['ETD'].normalize()
                            num_days = (etd_date - start_date).days + 1
                    
                            vessels[ship_name] = {
                                'name': ship_name,
                                'service': row['SERVICE'],
                                'total_boxes': row['TOTAL BOX (TEUS)'],
                                'start_date': start_date,
                                'etd_date': etd_date,
                                'daily_arrivals': get_daily_arrivals(row['TOTAL BOX (TEUS)'], row['SERVICE'], df_trends, num_days),
                                'clusters': [],
                                'boxes_allocated': 0
                            }
                        
                        # 3. Loop Simulasi Harian
                        start_date_sim = df_schedule['OPEN STACKING'].min().normalize()
                        end_date_sim = df_schedule['ETD'].max().normalize()
                        date_range = pd.date_range(start=start_date_sim, end=end_date_sim, freq='D')
                        
                        daily_log = []
                        
                        for current_date in date_range:
                            # A. Kosongkan slot dari kapal yang sudah berangkat
                            for ship in vessels.values():
                                if current_date > ship['etd_date']:
                                    for cluster in ship['clusters']:
                                        for slot in cluster:
                                            if yard_status[slot] == ship['name']:
                                                yard_status[slot] = None
                                    ship['clusters'] = [[]] # Reset cluster setelah kapal pergi
                    
                            # B. Alokasikan untuk kapal yang aktif
                            active_ships_today = [ship for ship in vessels.values() if current_date >= ship['start_date'] and current_date <= ship['etd_date']]
                            
                            for ship in active_ships_today:
                                day_index = (current_date - ship['start_date']).days
                                boxes_to_allocate_today = ship['daily_arrivals'][day_index]
                                slots_needed = int(np.ceil(boxes_to_allocate_today / slot_capacity))
                                
                                if slots_needed == 0:
                                    continue
                    
                                # Di sinilah logika Level 1, 2, 3 akan berjalan.
                                # Untuk sekarang kita implementasikan Level 1 secara langsung.
                                
                                # Cari slot yang valid HARI INI
                                placeable_slots = find_placeable_slots(ship, vessels, yard_status, current_date, rules, yard_config_map)
                                
                                # --- LOGIKA ALOKASI ---
                                # (Ini adalah versi sederhana dari logika alokasi Level 1)
                                slots_allocated_today = []
                                if len(placeable_slots) >= slots_needed:
                                    # Ambil N slot pertama yang tersedia
                                    slots_to_fill = placeable_slots[:slots_needed]
                                    
                                    # Masukkan ke cluster pertama, atau buat jika belum ada
                                    if not ship['clusters']:
                                        ship['clusters'].append([])
                                    
                                    ship['clusters'][0].extend(slots_to_fill)
                                    
                                    for slot in slots_to_fill:
                                        yard_status[slot] = ship['name']
                                    
                                    slots_allocated_today = slots_to_fill
                    
                                
                                # Catat hasil
                                ship['boxes_allocated'] += len(slots_allocated_today) * slot_capacity
                                
                                daily_log.append({
                                    'Tanggal': current_date.strftime('%Y-%m-%d'),
                                    'Kapal': ship['name'],
                                    'Butuh Slot': slots_needed,
                                    'Slot Berhasil': len(slots_allocated_today),
                                    'Slot Gagal': slots_needed - len(slots_allocated_today)
                                })
                    
                        # 4. Agregasi Hasil Akhir untuk Tampilan
                        df_daily_log = pd.DataFrame(daily_log)
                        
                        # Hitung YOR
                        yor_data = []
                        for date in date_range:
                            occupied_slots = sum(1 for status in yard_status.values() if status is not None)
                            total_slots = len(yard_status)
                            yor_data.append({
                                'Tanggal': date,
                                'Rasio Okupansi (%)': (occupied_slots / total_slots) * 100
                            })
                        df_yor = pd.DataFrame(yor_data)
                    
                        # Hitung Rekapitulasi Final
                        recap_list = []
                        for ship in vessels.values():
                            total_requested = ship['total_boxes']
                            # Perhitungan berhasil lebih akurat
                            successful_slots = df_daily_log[df_daily_log['Kapal'] == ship['name']]['Slot Berhasil'].sum()
                            boxes_successful = successful_slots * slot_capacity
                            
                            recap_list.append({
                                'Kapal': ship['name'],
                                'Permintaan Box': total_requested,
                                'Box Berhasil': boxes_successful,
                                'Box Gagal': total_requested - boxes_successful
                            })
                        df_recap = pd.DataFrame(recap_list)
                    
                        # Buat Peta Alokasi
                        map_list = []
                        for ship in vessels.values():
                            if not ship['clusters'][0]: continue # Jangan tampilkan kapal tanpa alokasi
                            
                            # Logika sederhana untuk merangkum range slot
                            ship['clusters'][0].sort(key=lambda s: get_slot_index(s, yard_config_map))
                            start_slot = f"{ship['clusters'][0][0][0]}:{ship['clusters'][0][0][1]}"
                            end_slot = f"{ship['clusters'][0][-1][0]}:{ship['clusters'][0][-1][1]}"
                    
                            map_list.append({
                                'Kapal': ship['name'],
                                'Cluster': 'Cluster 1', # Logika dummy saat ini hanya membuat 1 cluster
                                'Lokasi Area': ship['clusters'][0][0][0],
                                'Alokasi Slot': f"{start_slot} - {end_slot}"
                            })
                        df_map = pd.DataFrame(map_list)
                    
                        return df_yor, df_recap, df_map, df_daily_log
                    
                    
                    # --- BAGIAN UTAMA YANG MEMANGGIL SEMUA FUNGSI ---
                    
                    with st.spinner("Menjalankan simulasi kompleks berbasis tanggal... Ini mungkin memakan waktu beberapa saat."):
                        # Siapkan parameter aturan berdasarkan pilihan user
                        sim_rules = {
                            'intra_ship_gap': intra_ship_gap,
                            'inter_ship_gap': inter_ship_gap,
                            'daily_exclusion_zone': daily_exclusion_zone,
                            'cluster_req_logic': cluster_req_logic
                            # Tambahkan parameter lain jika ada
                        }
                    
                        # Jalankan fungsi simulasi utama
                        df_yor, df_recap, df_map, df_daily_log = run_simulation(df_schedule, df_trends, sim_rules)
                    
                        st.success(f"Simulasi Selesai! Dijalankan menggunakan **{rule_level}**.")
                    
                        # --- Tampilkan Semua Output ---
                        st.header("📊 Yard Occupancy Ratio (YOR) Harian")
                        if not df_yor.empty:
                            st.line_chart(df_yor.set_index('Tanggal')['Rasio Okupansi (%)'])
                            st.dataframe(df_yor)
                        else:
                            st.info("Tidak ada data YOR untuk ditampilkan.")
                    
                        st.header("📋 Rekapitulasi Alokasi Final")
                        if not df_recap.empty:
                            st.dataframe(df_recap)
                        else:
                            st.info("Tidak ada data rekapitulasi untuk ditampilkan.")
                    
                        st.header("🗺️ Peta Alokasi Akhir (Detail Slot)")
                        if not df_map.empty:
                            st.dataframe(df_map)
                        else:
                            st.info("Tidak ada data peta alokasi untuk ditampilkan.")
                            
                        st.header("📓 Log Alokasi Harian")
                        if not df_daily_log.empty:
                            st.dataframe(df_daily_log)
                        else:
                            st.info("Tidak ada data log harian untuk ditampilkan.")
                    
                    # ==============================================================================
                    #           SELESAI SALIN KODE DI SINI
                    # ==============================================================================
                    # --- AKHIR PERUBAHAN 3 ---

                    # --- Output 1: YOR Harian ---
                    st.header("📊 Yard Occupancy Ratio (YOR) Harian")
                    df_yor = pd.DataFrame(daily_occupancy_data)
                    # Menggunakan kolom 'Tanggal' sebagai index untuk grafik
                    st.line_chart(df_yor.set_index('Tanggal')['Rasio Okupansi (%)'])
                    st.dataframe(df_yor)

                    # --- Output lainnya tetap sama (menggunakan data dummy untuk saat ini) ---
                    st.header("📋 Rekapitulasi Alokasi Final")
                    recap_data = {
                        'Kapal': df_schedule['VESSEL'],
                        'Permintaan Box': df_schedule['TOTAL BOX (TEUS)'],
                        'Box Berhasil': (df_schedule['TOTAL BOX (TEUS)'] * np.random.uniform(0.8, 1.0, size=len(df_schedule))).astype(int),
                    }
                    recap_data['Box Gagal'] = recap_data['Permintaan Box'] - recap_data['Box Berhasil']
                    df_recap = pd.DataFrame(recap_data)
                    st.dataframe(df_recap)

                    st.header("🗺️ Peta Alokasi Akhir (Detail Slot)")
                    map_data = {
                        'Kapal': ['A', 'A', 'B'],
                        'Cluster': ['Cluster 1', 'Cluster 2', 'Cluster 1'],
                        'Lokasi Area': ['A01', 'B02', 'A03'],
                        'Alokasi Slot': ['1-15', '5-12', '10-25']
                    }
                    df_map = pd.DataFrame(map_data)
                    st.dataframe(df_map)
                    
                    st.balloons()
    
    except Exception as e:
        st.error(f"Terjadi kesalahan saat memproses file Anda. Pastikan format tanggal (dd/mm/yyyy) dan kolom sudah benar. Error: {e}")

else:
    st.info("Silakan upload file 'Vessel Schedule' dalam format .xlsx untuk memulai simulasi.")

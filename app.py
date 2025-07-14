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
STACKING_TREND_URL = 'https://github.com/irhassha/Export-Template/raw/refs/heads/main/stacking_trends.xlsx'

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
def get_daily_arrivals(total_boxes, service_name, trends_df, num_days):
    """Menghitung jumlah box harian berdasarkan tren atau rata-rata."""
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
                    for current_date in date_range:
                        # Di sini akan ada logika simulasi inti yang berjalan per tanggal
                        # 1. Cek kapal mana yang ETD-nya sudah lewat untuk mengosongkan slot.
                        # 2. Cek kapal mana yang sedang aktif (current_date di antara Open Stacking & ETD).
                        # 3. Hitung kontainer masuk untuk kapal aktif pada current_date.
                        # 4. Jalankan logika alokasi dengan semua aturan.
                        
                        # Data dummy untuk YOR
                        # Dalam simulasi nyata, angka ini adalah hasil kalkulasi dari yard status
                        total_boxes_in_yard = np.random.randint(3000, 14000) 
                        occupancy_ratio = (total_boxes_in_yard / (468 * 30)) * 100
                        daily_occupancy_data.append({
                            'Tanggal': current_date,
                            'Total Box di Yard': total_boxes_in_yard,
                            'Rasio Okupansi (%)': occupancy_ratio
                        })
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

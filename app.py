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
# Di sinilah kita akan meletakkan fungsi-fungsi seperti initialize_yard, find_placeable_slots, dll.
# Untuk sekarang, kita buat fungsi dummy run_simulation.
def run_simulation(df_schedule, df_trends, rules):
    """Fungsi utama placeholder untuk menjalankan seluruh proses simulasi."""
    st.info("Logika inti simulasi (otak) belum diimplementasikan. Menampilkan hasil dummy.")
    
    start_date_sim = df_schedule['OPEN STACKING'].min().normalize()
    end_date_sim = df_schedule['ETD'].max().normalize()
    date_range = pd.date_range(start=start_date_sim, end=end_date_sim, freq='D')
    
    # --- Membuat Data Dummy untuk Tampilan ---
    # YOR
    yor_data = [{'Tanggal': date, 'Rasio Okupansi (%)': np.random.uniform(30, 95)} for date in date_range]
    df_yor = pd.DataFrame(yor_data)

    # Rekapitulasi
    recap_list = []
    for _, row in df_schedule.iterrows():
        total_requested = row['TOTAL BOX (TEUS)']
        boxes_successful = int(total_requested * np.random.uniform(0.8, 1.0))
        recap_list.append({
            'Kapal': row['VESSEL'],
            'Permintaan Box': total_requested,
            'Box Berhasil': boxes_successful,
            'Box Gagal': total_requested - boxes_successful
        })
    df_recap = pd.DataFrame(recap_list)

    # Peta Alokasi
    map_list = [{'Kapal': row['VESSEL'], 'Cluster': 'Cluster 1 (Dummy)', 'Lokasi Area': 'A01', 'Alokasi Slot': '1-10'} for _, row in df_schedule.head(5).iterrows()]
    df_map = pd.DataFrame(map_list)

    # Log Harian
    log_list = [{'Tanggal': date.strftime('%Y-%m-%d'), 'Kapal': 'Dummy Ship', 'Butuh Slot': 5, 'Slot Berhasil': 5, 'Slot Gagal': 0} for date in date_range]
    df_daily_log = pd.DataFrame(log_list)
    
    return df_yor, df_recap, df_map, df_daily_log

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

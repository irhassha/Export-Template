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

# URL File Stacking trends dari GitHub (GANTI DENGAN URL ANDA)
STACKING_trends_URL = 'https://github.com/irhassha/Export-Template/raw/refs/heads/main/stacking_trends.xlsx' 
# Contoh: 'https://raw.githubusercontent.com/namauser/namarepo/main/stacking_trends.xlsx'

@st.cache_data
def load_stacking_trends(url):
    """Memuat dan cache data stacking trends dari URL GitHub."""
    try:
        df = pd.read_excel(url)
        # Ganti nama kolom 'STACKING trends' menjadi 'SERVICE' agar konsisten
        df.rename(columns={'STACKING trends': 'SERVICE'}, inplace=True)
        return df.set_index('SERVICE')
    except Exception as e:
        st.error(f"Gagal memuat file stacking trends dari URL. Pastikan URL raw sudah benar. Error: {e}")
        return None

def get_daily_arrivals(total_boxes, service_name, trends_df, num_days=7):
    """Menghitung jumlah box harian berdasarkan tren atau rata-rata."""
    if service_name in trends_df.index:
        percentages = trends_df.loc[service_name, [f'DAY {i}' for i in range(num_days)]].values
        percentages = pd.to_numeric(percentages, errors='coerce')
    else:
        # Jika service tidak ditemukan, gunakan rata-rata
        percentages = np.full(num_days, 1.0 / num_days)

    # Menghitung alokasi box harian dan memastikan totalnya pas
    daily_boxes = np.round(percentages * total_boxes).astype(int)
    diff = total_boxes - daily_boxes.sum()
    if diff != 0:
        daily_boxes[np.argmax(daily_boxes)] += diff
    return daily_boxes

# --- UI STREAMLIT & LOGIKA SIMULASI ---

st.set_page_config(layout="wide")
st.title("🚢 Simulasi Alokasi Container Yard")

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
    # Default values
    intra_ship_gap = 5
    inter_ship_gap = 10
    daily_exclusion_zone = 7
    cluster_req_logic = 'Wajar'

    if rule_level == "Level 1: Optimal":
        st.info("Menjalankan aturan paling ketat untuk efisiensi dan keamanan maksimal.")
    
    if rule_level == "Level 2: Aman & Terfragmentasi":
        st.info("Aturan keamanan tetap, namun fragmentasi diizinkan untuk menaikkan alokasi.")

    if rule_level == "Level 3: Darurat (Approval)":
        st.warning("Mode Darurat: Aturan keamanan dilonggarkan.")
        intra_ship_gap = st.slider("Jarak Internal Kapal", 1, 5, 2)
        inter_ship_gap = st.slider("Jarak Eksternal Kapal", 1, 10, 5)
        daily_exclusion_zone = st.slider("Zona Eksklusif Harian", 1, 7, 3)
        cluster_req_logic = 'Agresif'

# --- Main App Logic ---
if uploaded_file:
    try:
        # Membaca data dari file yang di-upload
        df_schedule = pd.read_excel(uploaded_file)
        st.subheader("Data Vessel Schedule yang Di-upload")
        st.dataframe(df_schedule)

        # Memuat data tren
        df_trends = load_stacking_trends(STACKING_trends_URL)

        if df_trends is not None:
            # Tombol untuk memulai simulasi
            if st.button("🚀 Mulai Simulasi"):
                
                # Placeholder untuk hasil simulasi
                # Di sinilah semua logika inti simulasi yang telah kita bangun akan ditempatkan.
                # Logika ini akan sangat panjang dan kompleks, melibatkan:
                # 1. Inisialisasi yard dan kapal dari DataFrame.
                # 2. Perulangan harian (daily loop) dari tanggal paling awal hingga paling akhir.
                # 3. Di setiap hari, jalankan:
                #    a. Logika pelepasan slot dari kapal yang sudah ETD.
                #    b. Logika perhitungan kontainer masuk berdasarkan tren.
                #    c. Logika pencarian slot kosong dengan mempertimbangkan SEMUA aturan
                #       (Jarak Internal, Jarak Eksternal Kondisional, Zona Eksklusif Harian).
                #    d. Logika alokasi slot ke cluster yang ada atau membuat cluster baru (termasuk +2 fleksibel).
                #    e. Pencatatan semua keberhasilan dan kegagalan.
                # 4. Kalkulasi YOR harian.
                # 5. Agregasi hasil akhir.
                
                # --- SIMULASI OUTPUT DUMMY (Untuk Tampilan) ---
                # Ganti bagian ini dengan hasil dari logika simulasi nyata Anda.
                
                with st.spinner("Menjalankan simulasi kompleks... Ini mungkin memakan waktu beberapa saat."):
                    # Tampilkan notifikasi level aturan yang digunakan
                    st.success(f"Simulasi dijalankan menggunakan **{rule_level}**.")

                    # --- Output 1: YOR Harian ---
                    st.header("📊 Yard Occupancy Ratio (YOR) Harian")
                    yor_data = {
                        'Hari': [f'Hari {i+1}' for i in range(14)],
                        'Rasio Okupansi (%)': np.random.randint(30, 95, size=14) # Data dummy
                    }
                    df_yor = pd.DataFrame(yor_data)
                    st.line_chart(df_yor.set_index('Hari'))
                    st.dataframe(df_yor)

                    # --- Output 2: Rekapitulasi Alokasi ---
                    st.header("📋 Rekapitulasi Alokasi Final")
                    recap_data = {
                        'Kapal': df_schedule['VESSEL'],
                        'Permintaan Box': df_schedule['TOTAL BOX (TEUS)'],
                        'Box Berhasil': (df_schedule['TOTAL BOX (TEUS)'] * np.random.uniform(0.8, 1.0, size=len(df_schedule))).astype(int),
                    }
                    recap_data['Box Gagal'] = recap_data['Permintaan Box'] - recap_data['Box Berhasil']
                    df_recap = pd.DataFrame(recap_data)
                    st.dataframe(df_recap)

                    # --- Output 3: Peta Alokasi Detail ---
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
        st.error(f"Terjadi kesalahan saat memproses file Anda: {e}")

else:
    st.info("Silakan upload file 'Vessel Schedule' dalam format .xlsx untuk memulai simulasi.")

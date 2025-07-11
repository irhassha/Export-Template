import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
import json
import io
import plotly.express as px
import plotly.graph_objects as go
import traceback

# Import pustaka yang diperlukan
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode

# --- Konfigurasi Halaman & Judul ---
st.set_page_config(page_title="Clash Analyzer", layout="wide")
st.title("🚨 Yard Clash Monitoring")

# --- Fungsi-fungsi Inti ---
@st.cache_data
def load_vessel_codes_from_repo(possible_names=['vessel codes.xlsx', 'vessel_codes.xls', 'vessel_codes.csv']):
    for filename in possible_names:
        if os.path.exists(filename):
            try:
                if filename.lower().endswith('.csv'): df = pd.read_csv(filename)
                else: df = pd.read_excel(filename)
                df.columns = df.columns.str.strip()
                return df
            except Exception as e:
                st.error(f"Failed to read file '{filename}': {e}"); return None
    st.error(f"Vessel code file not found."); return None

def format_bay(bay_val):
    if pd.isna(bay_val):
        return None
    s = str(bay_val).replace('..', '-')
    parts = s.split('-')
    cleaned_parts = [str(int(float(p))) for p in parts]
    return '-'.join(cleaned_parts)

# --- STRUKTUR TAB BARU ---
tab1, tab2 = st.tabs(["Clash Monitoring", "Crane Sequence"])

# --- KONTEN TAB 1 ---
with tab1:
    st.sidebar.header("⚙️ Your File Uploads")
    schedule_file = st.sidebar.file_uploader("1. Upload Vessel Schedule (for Clash Monitoring)", type=['xlsx', 'csv'])
    unit_list_file = st.sidebar.file_uploader("2. Upload Unit List (for both features)", type=['xlsx', 'csv'])

    process_button = st.button("🚀 Process Clash Data", type="primary", key="clash_button")

    if 'processed_df' not in st.session_state:
        st.session_state.processed_df = None
    
    if 'display_df' not in st.session_state:
        st.session_state.display_df = None

    df_vessel_codes = load_vessel_codes_from_repo()

    if process_button:
        if schedule_file and unit_list_file and (df_vessel_codes is not None and not df_vessel_codes.empty):
            with st.spinner('Loading and processing data...'):
                try:
                    if schedule_file.name.lower().endswith(('.xls', '.xlsx')): df_schedule = pd.read_excel(schedule_file)
                    else: df_schedule = pd.read_csv(schedule_file)
                    df_schedule.columns = df_schedule.columns.str.strip()

                    if unit_list_file.name.lower().endswith(('.xls', '.xlsx')): df_unit_list = pd.read_excel(unit_list_file)
                    else: df_unit_list = pd.read_csv(unit_list_file)
                    df_unit_list.columns = df_unit_list.columns.str.strip()

                    original_vessels_list = df_schedule['VESSEL'].unique().tolist()
                    df_schedule['ETA'] = pd.to_datetime(df_schedule['ETA'], errors='coerce')
                    df_schedule_with_code = pd.merge(df_schedule, df_vessel_codes, left_on="VESSEL", right_on="Description", how="left").rename(columns={"Value": "CODE"})
                    merged_df = pd.merge(df_schedule_with_code, df_unit_list, left_on=['CODE', 'VOY_OUT'], right_on=['Carrier Out', 'Voyage Out'], how='inner')

                    if merged_df.empty: st.warning("No matching data found."); st.session_state.processed_df = None; st.stop()

                    merged_df = merged_df[merged_df['VESSEL'].isin(original_vessels_list)]
                    excluded_areas = [str(i) for i in range(801, 809)]
                    merged_df['Area (EXE)'] = merged_df['Area (EXE)'].astype(str)
                    filtered_data = merged_df[~merged_df['Area (EXE)'].isin(excluded_areas)]
                    if filtered_data.empty: st.warning("No data remaining after filtering."); st.session_state.processed_df = None; st.stop()

                    grouping_cols = ['VESSEL', 'CODE', 'VOY_OUT', 'ETA']
                    pivot_df = filtered_data.pivot_table(index=grouping_cols, columns='Area (EXE)', aggfunc='size', fill_value=0)
                    cluster_cols_for_calc = pivot_df.columns.tolist()
                    pivot_df['TTL BOX'] = pivot_df[cluster_cols_for_calc].sum(axis=1)
                    pivot_df['TTL CLSTR'] = (pivot_df[cluster_cols_for_calc] > 0).sum(axis=1)
                    pivot_df = pivot_df.reset_index()
                    two_days_ago = pd.Timestamp.now() - timedelta(days=2)
                    condition_to_hide = (pivot_df['ETA'] < two_days_ago) & (pivot_df['TTL BOX'] < 50)
                    pivot_df = pivot_df[~condition_to_hide]

                    cols_awal = ['VESSEL', 'CODE', 'VOY_OUT', 'ETA', 'TTL BOX', 'TTL CLSTR']
                    final_cluster_cols = [col for col in pivot_df.columns if col not in cols_awal]
                    final_display_cols = cols_awal + sorted(final_cluster_cols)
                    pivot_df = pivot_df[final_display_cols]
                    pivot_df['ETA'] = pd.to_datetime(pivot_df['ETA']).dt.strftime('%Y-%m-%d %H:%M')
                    pivot_df = pivot_df.sort_values(by='ETA', ascending=True).reset_index(drop=True)
                    st.session_state.processed_df = pivot_df
                    st.success("Data processed successfully!")

                except Exception as e:
                    st.error(f"An error occurred during processing: {e}")
                    st.session_state.processed_df = None
        else:
            st.warning("Please upload both 'Vessel Schedule' and 'Unit List' files.")
    
    if st.session_state.processed_df is not None:
        st.dataframe(st.session_state.processed_df, use_container_width=True)


# --- KONTEN TAB 2 ---
with tab2:
    st.header("📇 Crane Tools")
    crane_file_tab2 = st.file_uploader("Upload Crane Sequence File", type=['xlsx', 'csv'], key="crane_uploader_tab2")
    st.markdown("---")

    # --- Fitur 1: Container Area Lookup ---
    st.subheader("Container Area Lookup")

    result_df = None
    if crane_file_tab2 and unit_list_file:
        try:
            df_crane_s1 = pd.read_excel(crane_file_tab2, sheet_name=0)
            df_crane_s1.columns = df_crane_s1.columns.str.strip()
            df_crane_s2 = pd.read_excel(crane_file_tab2, sheet_name=1)
            df_crane_s2.columns = df_crane_s2.columns.str.strip()
            df_crane_s2.rename(columns={'Main Bay': 'Bay', 'QC': 'Crane', 'Sequence': 'Seq.'}, inplace=True)

            if unit_list_file.name.lower().endswith(('.xls', '.xlsx')):
                df_unit_list = pd.read_excel(unit_list_file)
            else:
                df_unit_list = pd.read_csv(unit_list_file)
            df_unit_list.columns = df_unit_list.columns.str.strip()

            def check_columns(df, required_cols, file_desc):
                missing_cols = [col for col in required_cols if col not in df.columns]
                if missing_cols:
                    st.warning(f"Missing columns in **{file_desc}**: `{', '.join(missing_cols)}`")
                    return False
                return True

            s1_ok = check_columns(df_crane_s1, ['Container', 'Pos (Vessel)'], "Crane File (Sheet1)")
            s2_ok = check_columns(df_crane_s2, ['Bay', 'Crane', 'Direction', 'Seq.'], "Crane File (Sheet2)")
            unit_ok = check_columns(df_unit_list, ['Unit', 'Area (EXE)'], "Unit List File")

            if s1_ok and s2_ok and unit_ok:
                pos_to_crane_map = {}
                pos_to_seq_map = {}
                pos_to_direction_map = {}
                df_crane_s2_cleaned = df_crane_s2.dropna(subset=['Bay', 'Crane', 'Seq.', 'Direction'])

                for _, row in df_crane_s2_cleaned.iterrows():
                    bay_range_str = format_bay(row['Bay'])
                    crane = row['Crane']
                    seq = row['Seq.']
                    direction = row['Direction']
                    if bay_range_str:
                        if '-' in bay_range_str:
                            start, end = map(int, bay_range_str.split('-'))
                            for pos in range(start, end + 1):
                                pos_to_crane_map[pos] = crane
                                pos_to_seq_map[pos] = seq
                                pos_to_direction_map[pos] = direction
                        else:
                            pos_to_crane_map[int(bay_range_str)] = crane
                            pos_to_seq_map[int(bay_range_str)] = seq
                            pos_to_direction_map[int(bay_range_str)] = direction

                df_crane_s1['Pos (Vessel)'] = pd.to_numeric(df_crane_s1['Pos (Vessel)'], errors='coerce')
                df_crane_s1.dropna(subset=['Pos (Vessel)'], inplace=True)
                df_crane_s1['Pos (Vessel)'] = df_crane_s1['Pos (Vessel)'].astype(int)

                def extract_pos(pos):
                    pos_str = str(pos)
                    return pos_str[0] if len(pos_str) == 5 else pos_str[:2] if len(pos_str) == 6 else ''

                df_crane_s1['Pos'] = df_crane_s1['Pos (Vessel)'].apply(extract_pos)
                df_crane_s1['Crane'] = pd.to_numeric(df_crane_s1['Pos'], errors='coerce').map(pos_to_crane_map).fillna('N/A')
                df_crane_s1['Seq.'] = pd.to_numeric(df_crane_s1['Pos'], errors='coerce').map(pos_to_seq_map).fillna('N/A')
                df_crane_s1['Direction'] = pd.to_numeric(df_crane_s1['Pos'], errors='coerce').map(pos_to_direction_map).fillna('N/A')

                df_crane_s1['Container'] = df_crane_s1['Container'].astype(str).str.strip()
                df_unit_list['Unit'] = df_unit_list['Unit'].astype(str).str.strip()

                merged_df = pd.merge(
                    df_crane_s1[['Container', 'Pos', 'Crane', 'Seq.', 'Direction']],
                    df_unit_list[['Unit', 'Area (EXE)']],
                    left_on='Container',
                    right_on='Unit',
                    how='inner'
                )

                if not merged_df.empty:
                    result_df = merged_df[['Container', 'Pos', 'Crane', 'Seq.', 'Direction', 'Area (EXE)']].drop_duplicates()
                    st.write(f"Found area information for {len(result_df)} matching containers.")
                    st.dataframe(result_df, use_container_width=True)
                else:
                    st.info("No matching containers found between the files.")
        except Exception as e:
            st.error(f"Failed to process Container Area Lookup: {e}")
    else:
        st.info("Upload both 'Crane Sequence File' and 'Unit List' to use this feature.")

    st.markdown("---")

    # --- Fitur 2: Crane Sequence Visualizer ---
    st.subheader("Crane Sequence Visualizer")
    if crane_file_tab2 and result_df is not None:
        try:
            df_crane_sheet2_viz = pd.read_excel(crane_file_tab2, sheet_name=1)
            df_crane_sheet2_viz.columns = df_crane_sheet2_viz.columns.str.strip()
            df_crane_sheet2_viz.rename(columns={'Main Bay': 'Bay', 'Sequence': 'Seq.', 'QC': 'Crane'}, inplace=True)
            df_crane_sheet2_viz['Bay_formatted'] = df_crane_sheet2_viz['Bay'].apply(format_bay)
            
            # --- LOGIKA UNTUK MENGGABUNGKAN AREA DAN JUMLAH BOX ---
            area_summary = (
                result_df.groupby(['Crane', 'Seq.', 'Direction', 'Area (EXE)'])
                .size()
                .reset_index(name='Count')
            )
            area_summary['Label'] = area_summary['Area (EXE)'] + ' (' + area_summary['Count'].astype(str) + ')'
            
            area_labels = (
                area_summary.groupby(['Crane', 'Seq.', 'Direction'])['Label']
                .apply(lambda x: '<br>'.join(sorted(x)))
                .reset_index()
            )

            # --- LOGIKA BARU: HITUNG WAKTU KUMULATIF UNTUK GANTT CHART ---
            st.info("Calculating independent and continuous sequence duration for each crane from 'Mvs' column.")

            if 'Mvs' not in df_crane_sheet2_viz.columns:
                st.error("Column 'Mvs' not found in Crane Sequence file. Cannot calculate duration.")
                st.stop()

            # 1. Buat DataFrame tugas unik (Crane, Seq) untuk perhitungan waktu
            tasks_df = df_crane_sheet2_viz[['Crane', 'Seq.', 'Mvs']].copy()
            tasks_df.dropna(subset=['Crane', 'Seq.', 'Mvs'], inplace=True)
            tasks_df = tasks_df.drop_duplicates(subset=['Crane', 'Seq.'])
            tasks_df['Crane'] = tasks_df['Crane'].astype(int)

            # 2. Hitung durasi dan jadwal kontinu untuk setiap crane secara terpisah
            tasks_df['Time (hrs)'] = tasks_df['Mvs'] / 30.0
            tasks_df = tasks_df.sort_values(['Crane', 'Seq.'])
            tasks_df['Finish_Time_Hrs'] = tasks_df.groupby('Crane')['Time (hrs)'].cumsum()
            tasks_df['Start_Time_Hrs'] = tasks_df['Finish_Time_Hrs'] - tasks_df['Time (hrs)']

            # 3. Siapkan data dasar untuk plotting (termasuk semua lokasi Bay per tugas)
            plot_base_df = df_crane_sheet2_viz[['Crane', 'Seq.', 'Bay_formatted', 'Direction']].copy()
            plot_base_df.dropna(subset=['Crane', 'Seq.', 'Bay_formatted'], inplace=True)
            plot_base_df['Crane'] = plot_base_df['Crane'].astype(int)
            
            # PERBAIKAN: Jangan drop_duplicates di sini agar semua lokasi bay tetap ada
            # plot_base_df = plot_base_df.drop_duplicates()

            # 4. Gabungkan data plot dengan jadwal yang sudah dihitung
            gantt_df = pd.merge(
                plot_base_df,
                tasks_df, # Mengandung Mvs, Time (hrs), Start_Time_Hrs, Finish_Time_Hrs
                on=['Crane', 'Seq.']
            )

            # 5. Gabungkan dengan label area dari lookup
            gantt_df = pd.merge(gantt_df, area_labels, on=['Crane', 'Seq.', 'Direction'], how='left')
            gantt_df['Label'] = gantt_df['Label'].fillna('N/A')
            gantt_df['TextLabel'] = gantt_df['Direction'].fillna('N/A') + '<br>Seq: ' + gantt_df['Seq.'].astype(str) + '<br>Mvs: ' + gantt_df['Mvs'].astype(int).astype(str) + '<br>' + gantt_df['Label']
            gantt_df['Crane'] = gantt_df['Crane'].astype(str)
            
            MIN_VISIBLE_DURATION = 0.05
            gantt_df['Plot_Time_hrs'] = gantt_df['Time (hrs)'].apply(lambda x: MIN_VISIBLE_DURATION if x == 0 else x)

            # --- LOGIKA PEWARNAAN ---
            unique_cranes = sorted(gantt_df['Crane'].dropna().unique())
            crane_colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf', '#999999']
            color_map = {crane: crane_colors[i % len(crane_colors)] for i, crane in enumerate(unique_cranes)}
            if 'N/A' not in color_map:
                color_map['N/A'] = '#999999'

            # --- BUAT GANTT CHART DENGAN PLOTLY (VERTICAL) ---
            fig = go.Figure()

            for crane in unique_cranes:
                crane_df = gantt_df[gantt_df['Crane'] == crane]
                fig.add_trace(go.Bar(
                    x=crane_df['Bay_formatted'],
                    y=crane_df['Plot_Time_hrs'],
                    base=crane_df['Start_Time_Hrs'],
                    name=f'Crane {crane}',
                    marker_color=color_map.get(crane),
                    text=crane_df['TextLabel'],
                    textposition='inside',
                    insidetextanchor='middle'
                ))

            # --- PENGURUTAN & KONFIGURASI SUMBU ---
            gantt_df['sort_key'] = gantt_df['Bay_formatted'].str.split('-').str[0].astype(int)
            gantt_df = gantt_df.sort_values('sort_key')
            x_axis_order = gantt_df['Bay_formatted'].unique().tolist()
            
            start_hour = 8
            # Hitung waktu selesai maksimum dari semua crane untuk skala sumbu Y yang benar
            max_finish_time = gantt_df['Finish_Time_Hrs'].max() if not gantt_df.empty else 0
            y_ticks_values = list(range(int(max_finish_time) + 2))
            y_ticks_labels = [f"{(start_hour + h):02d}:00" for h in y_ticks_values]

            fig.update_layout(
                title_text="Crane Sequence Gantt Chart",
                xaxis_title="Bay",
                yaxis_title="Time",
                barmode='overlay',
                xaxis={
                    'categoryorder':'array', 
                    'categoryarray': x_axis_order,
                    'side': 'top'
                },
                yaxis={
                    'autorange': 'reversed',
                    'tickmode': 'array',
                    'tickvals': y_ticks_values,
                    'ticktext': y_ticks_labels
                },
                title_font_size=20,
                font_size=12,
                height=800,
                legend_title_text='Crane'
            )
            fig.update_traces(textfont_size=10)

            st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.error(f"Failed to process Crane Sequence Visualizer: {e}")
            st.error(traceback.format_exc())
    elif crane_file_tab2:
        st.info("Upload the 'Unit List' file to see the combined visualizer.")

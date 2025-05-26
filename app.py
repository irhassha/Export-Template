import streamlit as st
import pandas as pd

# Contoh DataFrame
data = [
    ['A', 'A', 'A', 'A', 'A'],
    ['B', 'B', 'C', 'C', 'C'],
    ['D', 'E', 'E', 'E', 'F'],
]
columns = ['Col1', 'Col2', 'Col3', 'Col4', 'Col5']
df = pd.DataFrame(data, columns=columns)

def build_html_table(df):
    html = "<table border='1' style='border-collapse: collapse;'>"
    for _, row in df.iterrows():
        html += "<tr>"
        prev_val = None
        colspan = 1
        for i, val in enumerate(row):
            if val == prev_val:
                colspan += 1
            else:
                if prev_val is not None:
                    html += f"<td colspan='{colspan}' align='center'>{prev_val}</td>"
                prev_val = val
                colspan = 1
        # Tambahkan nilai terakhir
        html += f"<td colspan='{colspan}' align='center'>{prev_val}</td>"
        html += "</tr>"
    html += "</table>"
    return html

# Tampilkan di Streamlit
st.title("Visualisasi Merge Otomatis Kolom")
st.markdown(build_html_table(df), unsafe_allow_html=True)

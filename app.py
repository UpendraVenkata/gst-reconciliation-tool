import streamlit as st
import pandas as pd
from io import BytesIO
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows

st.title("GST Reconciliation Tool")

# Upload files
int_file = st.file_uploader("Upload Internal Data (Purchase Book)", type=["xlsx"])
ext_file = st.file_uploader("Upload External Data (Supplier Invoices / GSTR-2A)", type=["xlsx"])

def preprocess(df):
    df = df.rename(columns={
        'Invoice No': 'Invoice Number',
        'Supplier GSTIN': 'GSTIN',
        'IGST': 'IGST Amount',
        'CGST': 'CGST Amount',
        'SGST': 'SGST Amount'
    })
    df['Invoice Number'] = df['Invoice Number'].astype(str).str.strip().str.upper()
    df['GSTIN'] = df['GSTIN'].astype(str).str.strip().str.upper()
    df['Invoice Date'] = pd.to_datetime(df['Invoice Date'], errors='coerce')
    df['Taxable Value'] = pd.to_numeric(df['Taxable Value'], errors='coerce')
    df['IGST Amount'] = pd.to_numeric(df['IGST Amount'], errors='coerce')
    df['CGST Amount'] = pd.to_numeric(df['CGST Amount'], errors='coerce')
    df['SGST Amount'] = pd.to_numeric(df['SGST Amount'], errors='coerce')
    return df

def amounts_match(row, tolerance=1.0):
    try:
        return (
            abs((row['Taxable Value_int'] or 0) - (row['Taxable Value_ext'] or 0)) <= tolerance and
            abs((row['IGST Amount_int'] or 0) - (row['IGST Amount_ext'] or 0)) <= tolerance and
            abs((row['CGST Amount_int'] or 0) - (row['CGST Amount_ext'] or 0)) <= tolerance and
            abs((row['SGST Amount_int'] or 0) - (row['SGST Amount_ext'] or 0)) <= tolerance
        )
    except:
        return False

def write_sheet(wb, sheet_name, df):
    ws = wb.create_sheet(title=sheet_name)
    taxable_cols = [col for col in df.columns if 'Taxable Value' in col]
    total_taxable = df[taxable_cols].sum().sum() if taxable_cols else 0
    ws.append([f"Total Records: {len(df)}", f"Total Taxable Value: {total_taxable:.2f}"])
    for r in dataframe_to_rows(df.reset_index(drop=True), index=False, header=True):
        ws.append(r)

def run_reconciliation(int_df, ext_df):
    int_df = preprocess(int_df)
    ext_df = preprocess(ext_df)

    merged = pd.merge(
        int_df, ext_df,
        on=['Invoice Number', 'GSTIN'],
        how='outer',
        suffixes=('_int', '_ext'),
        indicator=True
    )

    matched = merged[merged['_merge'] == 'both'].copy()
    matched['Amounts Match'] = matched.apply(amounts_match, axis=1)

    matched_invoices = matched[matched['Amounts Match']]
    mismatch_amounts = matched[~matched['Amounts Match']]
    only_in_internal = merged[merged['_merge'] == 'left_only']
    only_in_external = merged[merged['_merge'] == 'right_only']

    wb = Workbook()
    wb.remove(wb.active)

    write_sheet(wb, "Matched Invoices", matched_invoices)
    write_sheet(wb, "Mismatch in Amounts", mismatch_amounts)
    write_sheet(wb, "Only in Internal", only_in_internal)
    write_sheet(wb, "Only in External", only_in_external)

    output = BytesIO()
    wb.save(output)
    return output

# Run logic on button click
if st.button("Reconcile Now") and int_file and ext_file:
    int_df = pd.read_excel(int_file)
    ext_df = pd.read_excel(ext_file)
    output = run_reconciliation(int_df, ext_df)
    st.success("Reconciliation complete!")
    st.download_button("Download Reconciliation Excel", data=output.getvalue(), file_name="GST_Reconciliation_Result.xlsx")

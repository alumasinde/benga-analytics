import io
import math
import re
import pandas as pd
NULL_CATEGORY = "Unknown"
def _clean_name(name):
    name = re.sub(r"\s+", " ", str(name).strip())
    return name or "Unnamed Column"
def _json_safe(value):
    if pd.isna(value): return None
    if isinstance(value, pd.Timestamp): return value.to_pydatetime()
    if hasattr(value, "item"):
        try: value = value.item()
        except Exception: pass
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)): return None
    return value
def read_dataframe(file_storage):
    filename = (file_storage.filename or "").lower()
    raw = file_storage.read()
    if filename.endswith(".csv"): df = pd.read_csv(io.BytesIO(raw), low_memory=False)
    elif filename.endswith(".xlsx"): df = pd.read_excel(io.BytesIO(raw), engine="openpyxl")
    else: raise ValueError("Only CSV and XLSX files are supported.")
    df.columns = [_clean_name(c) for c in df.columns]
    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
    if df.empty: raise ValueError("The uploaded file contains no usable data.")
    return df
def infer_and_clean(df):
    metadata = {"columns": [], "dimensions": [], "metrics": [], "dates": []}
    for col in df.columns:
        non_null = df[col].dropna()
        numeric_ratio = 0
        if len(non_null):
            numeric_ratio = pd.to_numeric(non_null.astype(str).str.replace(",", "", regex=False), errors="coerce").notna().mean()
        date_ratio = 0
        if len(non_null) and numeric_ratio < .90:
            parsed = pd.to_datetime(non_null, errors="coerce", dayfirst=False, format="mixed")
            date_ratio = parsed.notna().mean()
        if date_ratio >= .85 and len(non_null) > 0:
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=False, format="mixed")
            role, dtype = "date", "datetime"; metadata["dates"].append(col)
        elif numeric_ratio >= .90:
            cleaned = pd.to_numeric(df[col].astype(str).str.replace(",", "", regex=False), errors="coerce")
            fill = cleaned.median() if cleaned.notna().any() else 0
            df[col] = cleaned.fillna(fill)
            role, dtype = "metric", "number"; metadata["metrics"].append(col)
        else:
            df[col] = df[col].astype("string").fillna(NULL_CATEGORY).replace("", NULL_CATEGORY)
            role, dtype = "dimension", "string"; metadata["dimensions"].append(col)
        metadata["columns"].append({"name": col, "role": role, "dtype": dtype})
    metadata["categorical_values"] = {c: df[c].dropna().astype(str).value_counts().index.tolist()[:1000] for c in metadata["dimensions"]}
    metadata["row_count"] = int(len(df))
    return df, metadata
def dataframe_records(df):
    return [{k: _json_safe(v) for k, v in row.items()} for row in df.to_dict(orient="records")]
def build_insights(rows, metric, aggregation, dimension=None):
    if not rows: return ["No records matched the current filters."]
    insights = [f"{len(rows):,} grouped results were generated using {aggregation.upper()}."]
    if metric and "value" in rows[0]: insights.append(f"Leading result: {rows[0].get('label', 'Leading group')} ({rows[0]['value']:,.2f}).")
    if dimension: insights.append(f"Results are grouped dynamically by {dimension}.")
    return insights

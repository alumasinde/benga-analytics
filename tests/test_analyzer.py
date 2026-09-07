import io
import pandas as pd
from werkzeug.datastructures import FileStorage
from analyzer import read_dataframe, infer_and_clean

def storage(name, content):
    return FileStorage(stream=io.BytesIO(content), filename=name)

def test_csv_is_read_and_empty_rows_removed():
    raw = b"Region,Revenue,When\nNairobi,100,2026-01-01\n,,\nMombasa,,2026-01-02\n"
    df = read_dataframe(storage("sales.csv", raw))
    assert len(df) == 2
    assert list(df.columns) == ["Region", "Revenue", "When"]

def test_schema_is_inferred_without_dataset_specific_names():
    df = pd.DataFrame({
        "Area": ["North", None, "South"],
        "Amount": ["100", "200", None],
        "Occurred": ["2026-01-01", "2026-01-02", "2026-01-03"],
    })
    cleaned, meta = infer_and_clean(df)
    assert "Area" in meta["dimensions"]
    assert "Amount" in meta["metrics"]
    assert "Occurred" in meta["dates"]
    assert cleaned["Area"].tolist()[1] == "Unknown"
    assert cleaned["Amount"].isna().sum() == 0

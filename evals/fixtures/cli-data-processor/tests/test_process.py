import pandas as pd
from process import enrich_row


def test_enrich_row_happy_path():
    lookup_df = pd.DataFrame({'id': [1, 2], 'label': ['a', 'b']})
    row = {'ref_id': 1}
    assert enrich_row(row, lookup_df) == 'a'

import click
import pandas as pd


def enrich_row(row, lookup_df):
    # O(n) scan of lookup_df for every row -> O(n*m) overall
    match = lookup_df[lookup_df['id'] == row['ref_id']]
    if len(match) > 0:
        return match.iloc[0]['label']
    return None


@click.command()
@click.argument('input_csv')
@click.argument('lookup_csv')
@click.argument('output_csv')
def main(input_csv, lookup_csv, output_csv):
    df = pd.read_csv(input_csv)
    lookup_df = pd.read_csv(lookup_csv)

    labels = []
    for _, row in df.iterrows():
        # row-by-row iteration + repeated full-table scan per row
        labels.append(enrich_row(row, lookup_df))

    df['label'] = labels
    df.to_csv(output_csv, index=False)


if __name__ == '__main__':
    main()

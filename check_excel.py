import pandas as pd

df = pd.read_excel('Договори.xlsx', header=None)
print(f'Columns: {df.shape[1]}')
print(f'Rows: {df.shape[0]}')
print('\nColumn names (A-Z):')
for i in range(min(26, df.shape[1])):
    col_letter = chr(65 + i)
    print(f'{col_letter} ({i}): {df.iloc[0, i] if i < df.shape[1] else "N/A"}')

print('\n\nFirst 2 data rows:')
for idx in range(min(2, len(df))):
    print(f'\nRow {idx}:')
    for i in range(min(26, df.shape[1])):
        col_letter = chr(65 + i)
        print(f'  {col_letter}: {df.iloc[idx, i]}')

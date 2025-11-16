"""
Simple utilities for notebook analysis workflows.
"""

import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime


# Paths
NOTEBOOKS_DIR = Path(__file__).parent
PROJECT_ROOT = NOTEBOOKS_DIR.parent

DB_PATH = PROJECT_ROOT / "data" / "raw" / "subiculum_literature.db"
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
DATA_INTERIM = PROJECT_ROOT / "data" / "interim"
DATA_EXPORTS = PROJECT_ROOT / "data" / "exports"

IMG_OUTPUT_PATH = NOTEBOOKS_DIR / "imgs"
DATA_OUTPUT_PATH = NOTEBOOKS_DIR / "outputs"
NOTEBOOK_DATA_PATH = NOTEBOOKS_DIR / "data"

SHAREABLES_FIGURES = NOTEBOOKS_DIR / "shareables" / "figures"
SHAREABLES_TABLES = NOTEBOOKS_DIR / "shareables" / "tables"
SHAREABLES_INTERACTIVE = NOTEBOOKS_DIR / "shareables" / "interactive"
REPORTS_PATH = NOTEBOOKS_DIR / "reports"

# Ensure directories exist
for path in [IMG_OUTPUT_PATH, DATA_OUTPUT_PATH, NOTEBOOK_DATA_PATH,
             SHAREABLES_FIGURES, SHAREABLES_TABLES, SHAREABLES_INTERACTIVE, REPORTS_PATH]:
    path.mkdir(parents=True, exist_ok=True)


def query_db(sql, params=None):
    """Execute SQL query and return DataFrame."""
    with sqlite3.connect(DB_PATH) as conn:
        if params:
            return pd.read_sql_query(sql, conn, params=params)
        return pd.read_sql_query(sql, conn)


def execute_sql(sql, params=None):
    """Execute SQL statement (INSERT, UPDATE, DELETE)."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        conn.commit()
        return cursor.rowcount


def save_figure(fig, name, notebook_name, dpi=300, **kwargs):
    """Save figure to imgs/ with naming: [notebook]_[date]_[name]"""
    date = datetime.now().strftime('%Y-%m-%d')
    filename = f"{notebook_name}_{date}_{name}"
    filepath = IMG_OUTPUT_PATH / filename

    fig.savefig(filepath, dpi=dpi, bbox_inches='tight', **kwargs)
    print(f"✅ Saved: imgs/{filename}")
    return filepath


def save_dataframe(df, name, notebook_name, subdir=None, **kwargs):
    """Save DataFrame to outputs/ with naming: [notebook]_[date]_[name]"""
    date = datetime.now().strftime('%Y-%m-%d')
    filename = f"{notebook_name}_{date}_{name}"

    if subdir:
        output_dir = DATA_OUTPUT_PATH / subdir
        output_dir.mkdir(exist_ok=True)
        filepath = output_dir / filename
    else:
        filepath = DATA_OUTPUT_PATH / filename

    df.to_csv(filepath, index=False, **kwargs)
    print(f"✅ Saved: outputs/{subdir + '/' if subdir else ''}{filename} ({len(df):,} rows)")
    return filepath


def save_shareable_figure(fig, name, dpi=600, **kwargs):
    """Save publication figure to shareables/figures/"""
    filepath = SHAREABLES_FIGURES / name
    fig.savefig(filepath, dpi=dpi, bbox_inches='tight', **kwargs)
    print(f"✅ Publication figure: shareables/figures/{name}")
    return filepath


def save_shareable_table(df, name, **kwargs):
    """Save publication table to shareables/tables/"""
    filepath = SHAREABLES_TABLES / name

    if name.endswith('.csv'):
        df.to_csv(filepath, index=False, **kwargs)
    elif name.endswith('.xlsx'):
        df.to_excel(filepath, index=False, **kwargs)
    else:
        df.to_csv(filepath, index=False, **kwargs)

    print(f"✅ Publication table: shareables/tables/{name} ({len(df):,} rows)")
    return filepath

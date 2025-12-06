"""
Simple utilities for notebook analysis workflows.
"""

import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime
import inspect
import os


# Paths
NOTEBOOKS_DIR = Path(__file__).parent
PROJECT_ROOT = NOTEBOOKS_DIR.parent

DB_PATH = PROJECT_ROOT / "data" / "raw" / "subiculum_literature.db"
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
DATA_INTERIM = PROJECT_ROOT / "data" / "interim"
DATA_EXPORTS = PROJECT_ROOT / "data" / "exports"

# Shared directories at top level
SHAREABLES_FIGURES = NOTEBOOKS_DIR / "shareables" / "figures"
SHAREABLES_TABLES = NOTEBOOKS_DIR / "shareables" / "tables"
SHAREABLES_INTERACTIVE = NOTEBOOKS_DIR / "shareables" / "interactive"
REPORTS_PATH = NOTEBOOKS_DIR / "reports"

# Ensure shared directories exist
for path in [SHAREABLES_FIGURES, SHAREABLES_TABLES, SHAREABLES_INTERACTIVE, REPORTS_PATH]:
    path.mkdir(parents=True, exist_ok=True)


def _get_notebook_dir():
    """
    Auto-detect the current notebook's directory by inspecting the call stack.
    Returns the directory containing the calling notebook, or NOTEBOOKS_DIR if not found.
    """
    # Try to find the notebook in the call stack
    for frame_info in inspect.stack():
        frame_file = frame_info.filename
        if frame_file.endswith('.ipynb') or '__notebook__' in frame_file:
            # Extract directory from notebook path
            # Jupyter stores temp files, but we can get CWD
            cwd = Path.cwd()
            if cwd.is_relative_to(NOTEBOOKS_DIR) and cwd != NOTEBOOKS_DIR:
                return cwd

    # Fallback: check current working directory
    cwd = Path.cwd()
    if cwd.is_relative_to(NOTEBOOKS_DIR) and cwd != NOTEBOOKS_DIR:
        return cwd

    # Default fallback
    return NOTEBOOKS_DIR


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
    """
    Save figure to the current notebook's imgs/ directory.

    Naming: [notebook]_[date]_[name]
    Location: Auto-detects current notebook folder (e.g., eda/imgs/, 01_keyword_frequency/imgs/)
    """
    notebook_dir = _get_notebook_dir()
    imgs_dir = notebook_dir / "imgs"
    imgs_dir.mkdir(exist_ok=True)

    date = datetime.now().strftime('%Y-%m-%d')
    filename = f"{notebook_name}_{date}_{name}"
    filepath = imgs_dir / filename

    fig.savefig(filepath, dpi=dpi, bbox_inches='tight', **kwargs)

    # Show relative path from notebooks dir
    rel_path = filepath.relative_to(NOTEBOOKS_DIR)
    print(f"✅ Saved: {rel_path}")
    return filepath


def save_dataframe(df, name, notebook_name, subdir=None, **kwargs):
    """
    Save DataFrame to the current notebook's outputs/ directory.

    Naming: [notebook]_[date]_[name]
    Location: Auto-detects current notebook folder (e.g., eda/outputs/, 01_keyword_frequency/outputs/)
    """
    notebook_dir = _get_notebook_dir()
    outputs_dir = notebook_dir / "outputs"

    if subdir:
        outputs_dir = outputs_dir / subdir

    outputs_dir.mkdir(parents=True, exist_ok=True)

    date = datetime.now().strftime('%Y-%m-%d')
    filename = f"{notebook_name}_{date}_{name}"
    filepath = outputs_dir / filename

    df.to_csv(filepath, index=False, **kwargs)

    # Show relative path from notebooks dir
    rel_path = filepath.relative_to(NOTEBOOKS_DIR)
    print(f"✅ Saved: {rel_path} ({len(df):,} rows)")
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

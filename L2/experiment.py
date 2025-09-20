import marimo

__generated_with = "0.16.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import pandas as pd
    import sqlite3 as sqll
    return pd, sqll


@app.cell
def _(pd, sqll):
    con = sqll.connect("L2/reviews.db")
    df = pd.read_sql_query("SELECT * FROM reviews", con)
    df
    return (df,)


@app.cell
def _(df):
    star_counts = df['stars'].value_counts().sort_index()
    for stars, count in star_counts.items():
        print(f"{stars} stars: {count} reviews")
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()

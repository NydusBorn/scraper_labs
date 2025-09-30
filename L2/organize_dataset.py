import json
import sqlite3
import os
from pathlib import Path
from datetime import datetime


def convert_year(year_str):
    """Convert year string to integer or None if empty."""
    return int(year_str) if year_str.strip() else None


def convert_bool(value):
    """Convert ДА/НЕТ to boolean."""
    return value.strip().upper() == "ДА"

def convert_null(value):
    """Convert empty string to None."""
    return value.strip() if value.strip() else None

def parse_date(date_str):
    """Parse Russian date format."""
    date_str = date_str.strip()
    months = {
        "янв": "01",
        "фев": "02",
        "мар": "03",
        "апр": "04",
        "мая": "05",
        "июн": "06",
        "июл": "07",
        "авг": "08",
        "сен": "09",
        "окт": "10",
        "ноя": "11",
        "дек": "12",
    }

    day, month, year = date_str.split()
    month = months[month[:3]]
    return f"{year}-{month}-{day.zfill(2)}"


def read_json_files(directory):
    """Read all JSON files from the given directory."""
    json_files = Path(directory).glob("*.json")
    data = []
    for json_file in json_files:
        with open(json_file, "r", encoding="utf-8") as f:
            data.append(json.load(f))
        data[-1]["link"] = f"https://otzovik.com/{json_file.name.split('.')[0]}.html"
    return data


def init_database(db_path):
    """Initialize SQLite database and create tables."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        link TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL,
        stars INTEGER NOT NULL,
        review_plus TEXT,
        review_minus TEXT,
        review_descr TEXT,
        year_usage INTEGER,
        recommendation BOOLEAN NOT NULL,
        time_usage TEXT,
        price TEXT,
        date_posted DATE NOT NULL,
        likes INTEGER NOT NULL,
        comments INTEGER NOT NULL
    )
    """)

    conn.commit()
    return conn

def organize(dataset_path: str | Path = "../L1/intermediate_dataset", db_path: str | Path = "reviews.db"):
    dataset_path = Path(dataset_path)
    db_path = str(db_path)
    if os.path.exists(db_path):
        os.remove(db_path)

    # Initialize database
    conn = init_database(db_path)
    cur = conn.cursor()

    # Read and process JSON files
    data = read_json_files(dataset_path)

    # Insert data into database
    for review in data:
        cur.execute(
            """
            INSERT INTO reviews (
                link, title, stars, review_plus, review_minus, review_descr,
                year_usage, recommendation, time_usage, price, date_posted, likes, comments
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                review["link"],
                review["title"],
                int(review["stars"]),
                convert_null(review["review_plus"]),
                convert_null(review["review_minus"]),
                convert_null(review["review_descr"]),
                convert_year(review["year_usage"]),
                convert_bool(review["recommendation"]),
                convert_null(review["time_usage"]),
                convert_null(review["price"]),
                parse_date(review["date_posted"]),
                int(review["likes"]),
                int(review["comments"]),
            ),
        )

    conn.commit()
    conn.close()

if __name__ == "__main__":
    organize()
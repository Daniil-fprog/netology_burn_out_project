import argparse
import json

from app.db.database import SessionLocal
from app.services.survey_service import seed_surveys


def main():
    parser = argparse.ArgumentParser(description="Publish idempotent survey catalog")
    parser.add_argument("--file", help="Catalog JSON; bundled catalog is used by default")
    args = parser.parse_args()
    catalog = None
    if args.file:
        with open(args.file, encoding="utf-8") as source: catalog = json.load(source)
    db = SessionLocal()
    try: print(seed_surveys(db, catalog))
    finally: db.close()


if __name__ == "__main__": main()

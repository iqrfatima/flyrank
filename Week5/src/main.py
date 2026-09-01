import json
import time
from pathlib import Path
from datetime import datetime, timezone

from pydantic import ValidationError

# from Week5.src.models import Book
from models import Book
from scraper import discover_books, extract_book


OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


def save_json(filename, data):
    path = OUTPUT_DIR / filename

    with open(path, "w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False
        )


def main():

    start_time = time.time()
    start_timestamp = datetime.now(
        timezone.utc
    ).isoformat()

    valid_books = []
    errors = []

    pages_fetched = 0
    cache_hits = 0
    failed_pages = 0

    # -------------------------
    # Discover books
    # -------------------------

    catalogue_pages, book_urls = discover_books()

    print()
    print(f"catalogue_pages={len(catalogue_pages)}")
    print(f"discovered={len(book_urls)}")
    print(f"unique_urls={len(set(book_urls))}")
    print()

    # Extract + validate

    for index, url in enumerate(book_urls, start=1):

        source_page = catalogue_pages[
            (index - 1) // 20
        ]

        try:

            raw_record, cache_hit = extract_book(
                url,
                source_page,
                index
            )

            if cache_hit:
                cache_hits += 1
            else:
                pages_fetched += 1

            book = Book.model_validate(raw_record)

            valid_books.append(
                book.model_dump(mode="json")
            )

        except ValidationError as exc:

            errors.append({
                "url": url,
                "error": str(exc)
            })

        except Exception as exc:

            failed_pages += 1

            errors.append({
                "url": url,
                "error": str(exc)
            })

            print(
                f"FAILED: {url} -> {exc}"
            )

            continue

    # -------------------------
    # Store
    # -------------------------

    save_json(
        "books.json",
        valid_books
    )

    save_json(
        "errors.json",
        errors
    )

    # Run report
    duration = time.time() - start_time

    report = {
        "started_at": start_timestamp,
        "duration_seconds": round(duration, 2),
        "catalogue_pages": len(catalogue_pages),
        "discovered_urls": len(book_urls),
        "unique_urls": len(set(book_urls)),
        "detail_pages": len(book_urls),
        "pages_fetched": pages_fetched,
        "cache_hits": cache_hits,
        "valid_records": len(valid_books),
        "invalid_records": len(errors),
        "failed_pages": failed_pages
    }

    save_json(
        "run-report.json",
        report
    )

    print()
    print("========== RUN REPORT ==========")

    for key, value in report.items():
        print(f"{key}: {value}")

    print("================================")


if __name__ == "__main__":
    main()
# import json
# import time
# from datetime import datetime, timezone
# from pathlib import Path
# from urllib.parse import urljoin

# import requests
# import re
# from bs4 import BeautifulSoup


# BASE_URL = "https://books.toscrape.com/"
# HEADERS = {
#     "User-Agent": "FlyRankInternshipA9/1.0 (+https://github.com/iqrfatima)"
# }

# CACHE_DIR = Path("cache")
# CACHE_DIR.mkdir(exist_ok=True)

# session = requests.Session()
# session.headers.update(HEADERS)


# def fetch(url: str, cache_file: Path):
#     """
#     Fetch a page politely.
#     Use cache when the page was already downloaded.
#     """

#     if cache_file.exists():
#         print(f"CACHE HIT: {url}")

#         return cache_file.read_text(encoding="utf-8"), True

#     print(f"FETCH: {url}")

#     try:
#         response = session.get(url, timeout=10)

#         if response.status_code != 200:
#             raise RuntimeError(
#                 f"HTTP {response.status_code}"
#             )

#         cache_file.write_text(
#             response.text,
#             encoding="utf-8"
#         )

#         time.sleep(0.5)

#         return response.text, False

#     except requests.RequestException as exc:
#         raise RuntimeError(str(exc))


# def discover_books():
#     """
#     Discover books from the first three catalogue pages.
#     """

#     book_urls = []
#     catalogue_pages = []

#     current_url = BASE_URL

#     for page_number in range(3):

#         cache_file = CACHE_DIR / f"catalogue-page-{page_number + 1}.html"

#         html, _ = fetch(current_url, cache_file)

#         soup = BeautifulSoup(html, "html.parser")

#         catalogue_pages.append(current_url)

#         for link in soup.select("article.product_pod h3 a"):
#             href = link.get("href")

#             if href:
#                 absolute_url = urljoin(current_url, href)

#                 if absolute_url not in book_urls:
#                     book_urls.append(absolute_url)

#         next_link = soup.select_one("li.next a")

#         if next_link:
#             current_url = urljoin(
#                 current_url,
#                 next_link.get("href")
#             )

#     return catalogue_pages, book_urls


# def extract_book(url: str, source_page: str, index: int):
#     """
#     Extract one book from its detail page.
#     """

#     cache_file = CACHE_DIR / f"book-{index}.html"

#     html, cache_hit = fetch(url, cache_file)

#     soup = BeautifulSoup(html, "html.parser")

#     product = soup.select_one("article.product_page")

#     if product is None:
#         raise ValueError("Product section not found")

#     title_element = product.select_one("h1")

#     price_element = product.select_one(
#         "p.price_color"
#     )

#     availability_element = product.select_one(
#         "p.instock.availability"
#     )

#     rating_element = product.select_one(
#         "p.star-rating"
#     )

#     description_element = product.select_one(
#         "#product_description + p"
#     )

#     if title_element is None:
#         raise ValueError("Title not found")

#     if price_element is None:
#         raise ValueError("Price not found")

#     if availability_element is None:
#         raise ValueError("Availability not found")

#     if rating_element is None:
#         raise ValueError("Rating not found")

#     title = title_element.get_text(strip=True)

#     price_text = price_element.get_text(strip=True)

#     availability_text = availability_element.get_text(
#         " ",
#         strip=True
#     )

#     rating_classes = rating_element.get("class", [])

#     rating_text = next(
#         (
#             item
#             for item in rating_classes
#             if item != "star-rating"
#         ),
#         "Unknown"
#     )

#     description = (
#         description_element.get_text(
#             " ",
#             strip=True
#         )
#         if description_element
#         else None
#     )

#     # price_gbp = float(
#     #     price_text.replace("£", "").strip()
#     # )
#     price_gbp = clean_price(price_text)
    

# def clean_price(price_text: str) -> float:
#     cleaned = price_text.replace("£", "").replace("Â", "").strip()
#     cleaned = re.sub(r"[^0-9.]", "", cleaned)
#     return float(cleaned)

#     return {
#         "title": title,
#         "product_url": url,
#         "price_text": price_text,
#         "price_gbp": price_gbp,
#         "availability_text": availability_text,
#         "rating_text": rating_text,
#         "description": description,
#         "source_page": source_page,
#         "fetched_at": datetime.now(
#             timezone.utc
#         ).isoformat(),
#     }, cache_hit


import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
import re

import requests
from bs4 import BeautifulSoup

# CONFIGURATION

BASE_URL = "https://books.toscrape.com/"

HEADERS = {
    "User-Agent": (
        "FlyRankInternshipA9/1.0 "
        "(+https://github.com/iqrfatima)"
    )
}

CACHE_DIR = Path("cache")
OUTPUT_DIR = Path("output")

CACHE_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

session = requests.Session()
session.headers.update(HEADERS)


# FETCH + CACHE

def fetch(url: str, cache_file: Path):
    """
    Fetch a page politely.

    If the page already exists in the cache,
    read it locally instead of requesting it again.
    """

    # Use cached page
    if cache_file.exists():
        print(f"CACHE HIT: {url}")

        return (
            cache_file.read_text(
                encoding="utf-8"
            ),
            True
        )

    # Make real request
    print(f"FETCH: {url}")

    try:
        response = session.get(
            url,
            timeout=10
        )

        # Only HTTP 200 is accepted
        if response.status_code != 200:
            raise RuntimeError(
                f"HTTP {response.status_code}"
            )

        # Books to Scrape uses UTF-8
        response.encoding = "utf-8"

        html = response.text

        # Save response to cache
        cache_file.write_text(
            html,
            encoding="utf-8"
        )

        # Be polite
        time.sleep(0.5)

        return html, False

    except requests.RequestException as exc:
        raise RuntimeError(str(exc))

# DISCOVER BOOKS

def discover_books():
    """
    Discover books from the first three catalogue pages.
    """

    book_urls = []
    catalogue_pages = []

    current_url = BASE_URL

    for page_number in range(3):

        cache_file = (
            CACHE_DIR
            / f"catalogue-page-{page_number + 1}.html"
        )

        html, _ = fetch(
            current_url,
            cache_file
        )

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        catalogue_pages.append(
            current_url
        )

        # Find all book links
        for link in soup.select(
            "article.product_pod h3 a"
        ):

            href = link.get("href")

            if href:
                absolute_url = urljoin(
                    current_url,
                    href
                )

                if absolute_url not in book_urls:
                    book_urls.append(
                        absolute_url
                    )

        # Follow the catalogue's next link
        next_link = soup.select_one(
            "li.next a"
        )

        if next_link:
            current_url = urljoin(
                current_url,
                next_link.get("href")
            )

    return catalogue_pages, book_urls


# PRICE NORMALIZATION

def clean_price(price_text: str) -> float:
    """
    Convert messy scraped price text into a number.

    Examples:

        £51.77  -> 51.77
        Â£51.77 -> 51.77
        Â51.77  -> 51.77
    """

    cleaned = (
        price_text
        .replace("£", "")
        .replace("Â", "")
        .strip()
    )

    # Keep only numbers and decimal point
    cleaned = re.sub(
        r"[^0-9.]",
        "",
        cleaned
    )

    if not cleaned:
        raise ValueError(
            f"Invalid price: {price_text!r}"
        )

    return float(cleaned)


# EXTRACT BOOK

def extract_book(
    url: str,
    source_page: str,
    index: int
):
    """
    Extract one book from its detail page.
    """

    cache_file = (
        CACHE_DIR
        / f"book-{index}.html"
    )

    html, cache_hit = fetch(
        url,
        cache_file
    )

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    # Only inspect the product area
    product = soup.select_one(
        "article.product_page"
    )

    if product is None:
        raise ValueError(
            "Product section not found"
        )
    # TITLE

    title_element = product.select_one(
        "h1"
    )

    if title_element is None:
        raise ValueError(
            "Title not found"
        )

    title = title_element.get_text(
        strip=True
    )

    # PRICE

    price_element = product.select_one(
        "p.price_color"
    )

    if price_element is None:
        raise ValueError(
            "Price not found"
        )

    price_text = price_element.get_text(
        strip=True
    )

    price_gbp = clean_price(
        price_text
    )
    # AVAILABILITY

    availability_element = product.select_one(
        "p.instock.availability"
    )

    if availability_element is None:
        raise ValueError(
            "Availability not found"
        )

    availability_text = (
        availability_element.get_text(
            " ",
            strip=True
        )
    )

      # RATING

    rating_element = product.select_one(
        "p.star-rating"
    )

    if rating_element is None:
        raise ValueError(
            "Rating not found"
        )

    rating_classes = rating_element.get(
        "class",
        []
    )

    rating_text = next(
        (
            item
            for item in rating_classes
            if item != "star-rating"
        ),
        "Unknown"
    )
# DESCRIPTION

    description_element = product.select_one(
        "#product_description + p"
    )

    if description_element:

        description = (
            description_element.get_text(
                " ",
                strip=True
            )
        )

    else:

        description = None


    # FINAL RAW + NORMALIZED RECORD


    record = {
        "title": title,
        "product_url": url,
        "price_text": price_text,
        "price_gbp": price_gbp,
        "availability_text": availability_text,
        "rating_text": rating_text,
        "description": description,
        "source_page": source_page,
        "fetched_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    return record, cache_hit



def main():

    start_time = datetime.now(
        timezone.utc
    )

    print("\n==============================")
    print("Books to Scrape")
    print("==============================\n")

    # DISCOVER


    catalogue_pages, book_urls = (
        discover_books()
    )

    print(
        f"\ncatalogue_pages={len(catalogue_pages)}"
    )

    print(
        f"discovered={len(book_urls)}"
    )

    print(
        f"unique_urls={len(set(book_urls))}"
    )


    # EXTRACT


    records = []

    errors = []

    cache_hits = 0
    pages_fetched = 0

    for index, url in enumerate(
        book_urls,
        start=1
    ):

        source_page = catalogue_pages[
            (index - 1) // 20
        ]

        try:

            record, cache_hit = extract_book(
                url,
                source_page,
                index
            )

            records.append(record)

            if cache_hit:
                cache_hits += 1
            else:
                pages_fetched += 1

        except Exception as exc:

            print(
                f"FAILED: {url} -> {exc}"
            )

            errors.append(
                {
                    "url": url,
                    "error": str(exc)
                }
            )


    # SAVE BOOKS


    books_file = (
        OUTPUT_DIR
        / "books.json"
    )

    books_file.write_text(
        json.dumps(
            records,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    # SAVE ERRORS


    errors_file = (
        OUTPUT_DIR
        / "errors.json"
    )

    errors_file.write_text(
        json.dumps(
            errors,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    # RUN REPORT


    end_time = datetime.now(
        timezone.utc
    )

    duration = (
        end_time - start_time
    ).total_seconds()

    report = {
        "started_at": start_time.isoformat(),
        "finished_at": end_time.isoformat(),
        "duration_seconds": duration,
        "catalogue_pages": len(
            catalogue_pages
        ),
        "book_urls_discovered": len(
            book_urls
        ),
        "unique_urls": len(
            set(book_urls)
        ),
        "pages_fetched": pages_fetched,
        "cache_hits": cache_hits,
        "valid_records": len(
            records
        ),
        "invalid_records": len(
            errors
        ),
        "failed_pages": len(
            errors
        )
    }

    report_file = (
        OUTPUT_DIR
        / "run-report.json"
    )

    report_file.write_text(
        json.dumps(
            report,
            indent=2
        ),
        encoding="utf-8"
    )

 
    # SUMMARY
  

    print("\n==============================")
    print("RUN COMPLETE")
    print("==============================")

    print(
        f"catalogue_pages: "
        f"{len(catalogue_pages)}"
    )

    print(
        f"discovered: "
        f"{len(book_urls)}"
    )

    print(
        f"unique_urls: "
        f"{len(set(book_urls))}"
    )

    print(
        f"pages_fetched: "
        f"{pages_fetched}"
    )

    print(
        f"cache_hits: "
        f"{cache_hits}"
    )

    print(
        f"valid_records: "
        f"{len(records)}"
    )

    print(
        f"invalid_records: "
        f"{len(errors)}"
    )

    print(
        f"failed_pages: "
        f"{len(errors)}"
    )

    print(
        f"duration: "
        f"{duration:.2f}s"
    )

    print(
        f"\nOutput: {books_file}"
    )

    print(
        f"Report: {report_file}"
    )



# ENTRY POINT


if __name__ == "__main__":
    main()
from decimal import Decimal
from typing import TypedDict
from urllib.parse import urljoin
from playwright.sync_api import Page, Locator

URL: str = "https://books.toscrape.com/"

RATING_MAP: dict[str, int] = {
    "One": 1,
    "Two": 2,
    "Three": 3,
    "Four": 4,
    "Five": 5,
}


class BookData(TypedDict):
    url: str
    name: str
    rating: int
    price: Decimal
    in_stock: bool

def find_category_url(page: Page, category: str) -> str | None:
    """Find the absolute URL of a sidebar category matching `category`.

    Matching is case-insensitive. Returns `None` if no category matches.
    """
    category_links = page.locator("div.side_categories ul.nav-list ul li a")

    for link in category_links.all():
        link_text = link.inner_text().strip()
        if link_text.lower() == category.lower():
            href = link.get_attribute("href")
            return urljoin(page.url, href)

    return None

def parse_rating(rating_class: str) -> int:
    """Convert a star-rating class attribute (e.g. "star-rating Three") to an integer."""
    rating_word = rating_class.replace("star-rating", "").strip()
    return RATING_MAP.get(rating_word, 0)


def parse_price(price_text: str) -> Decimal:
    """Convert a displayed price (e.g. "£51.77") to a Decimal, stripping the currency symbol."""
    digits_and_dot = "".join(char for char in price_text if char.isdigit() or char == ".")
    return Decimal(digits_and_dot)

def extract_book_data(book: Locator, page: Page) -> BookData:
    """Extract all book data fields from a single book element."""
    link = book.locator("h3 a")
    name = link.get_attribute("title") or ""
    href = link.get_attribute("href") or ""
    url = urljoin(page.url, href)

    price_text = book.locator("p.price_color").inner_text()
    price = parse_price(price_text)

    availability_text = book.locator("p.instock.availability").inner_text()
    in_stock = "In stock" in availability_text

    rating_class = book.locator("p.star-rating").get_attribute("class") or ""
    rating = parse_rating(rating_class)

    return BookData(
        url=url,
        name=name,
        rating=rating,
        price=price,
        in_stock=in_stock,
    )

def scrape_books_from_page(page: Page) -> list[BookData]:
    """Extract data for every book visible on the current page."""
    books = page.locator("article.product_pod").all()
    return [extract_book_data(book, page) for book in books]


def scrape_books(page: Page, *, category: str | None, max_books: int) -> list[BookData]:
    """Scrape book data from https://books.toscrape.com/.

    After navigating to the site homepage, scrapes book data following this
    contract:

    - `category` is `None`: scrape all books, following the pagination from
      the homepage without navigating into any category.
    - `category` matches a sidebar category (case-insensitive): scrape only
      that category's books, following its pagination.
    - `category` does not match any sidebar category (or is empty /
      whitespace-only): return an empty list.

    Stops as soon as `max_books` books have been collected and never request
    pages beyond the limit. If `max_books` is less than or equal to zero, an
    empty list is returned.

    Args:
        page: A Playwright page, already created and navigable.
        category: The category to scrape, or `None` to scrape all books.
        max_books: Maximum number of books to scrape.

    Returns:
        A list of the scraped books.
    """
    if max_books <= 0:
        return []

    page.goto(URL)

    if category is not None:
        category_url = find_category_url(page, category)
        if category_url is None:
            return []
        page.goto(category_url)

    books: list[BookData] = []

    while len(books) < max_books:
        books.extend(scrape_books_from_page(page))

        if len(books) >= max_books:
            break

        next_button = page.locator("li.next a")
        if next_button.count() == 0:
            break

        next_button.click()
        page.wait_for_load_state("networkidle")

    return books[:max_books]


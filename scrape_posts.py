"""
scrape_posts.py
----------------
Collect LinkedIn posts and save them
for downstream embedding and retrieval.

"""

import json
import logging
from typing import Any

from playwright.sync_api import sync_playwright, Page, TimeoutError as PWTimeoutError

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

LOGIN_URL = "https://www.linkedin.com/login"
SCROLL_PAUSE_SECONDS = 2.0
MAX_SCROLLS = 25  


def login(page: Page, email: str, password: str) -> None:
    """Log into LinkedIn with the given credentials.

    Args:
        page: An active Playwright page.
        email: LinkedIn account email.
        password: LinkedIn account password.

    Raises:
        RuntimeError: If login does not appear to succeed within the timeout.
    """
    page.goto(LOGIN_URL, timeout=30000)
    page.fill("input#username", email)
    page.fill("input#password", password)
    page.click("button[type='submit']")

    try:
        # A successful login redirects to the feed; we wait for a known
        # feed element rather than guessing at timing.
        page.wait_for_selector("div.feed-identity-module", timeout=20000)
        logger.info("Login successful.")
    except PWTimeoutError as exc:
        raise RuntimeError(
            "Login did not complete as expected. This usually means LinkedIn "
            "showed a security checkpoint (CAPTCHA / verification code), which "
            "this script cannot solve automatically. Log in manually in a "
            "regular browser once, then retry."
        ) from exc


def scrape_profile_posts(page: Page, profile_url: str, max_posts: int = 30) -> list[dict[str, Any]]:
    """Navigate to a profile's activity feed and collect post text.

    Args:
        page: An active, already-logged-in Playwright page.
        profile_url: Full LinkedIn profile URL, e.g. https://www.linkedin.com/in/handle/
        max_posts: Stop once this many unique posts have been collected.

    Returns:
        A list of dicts shaped like {"id": str, "text": str, "topic": "", "likes": 0}.
        likes/topic are left as placeholders here; LinkedIn's DOM for engagement
        counts changes often, so we keep this script focused on the text, which
        is the only thing the style-RAG pipeline actually needs.
    """
    activity_url = profile_url.rstrip("/") + "/recent-activity/all/"
    page.goto(activity_url, timeout=30000)
    page.wait_for_timeout(3000)

    collected: dict[str, str] = {}  
    scrolls = 0

    while len(collected) < max_posts and scrolls < MAX_SCROLLS:
        # LinkedIn renders each post inside a <div> with this data attribute.
        # NOTE: LinkedIn changes class/data names periodically. If this
        # selector returns nothing, open the page in a normal browser,
        # inspect a post, and update the selector below.
        post_nodes = page.query_selector_all("div.feed-shared-update-v2__description")

        for node in post_nodes:
            text = (node.inner_text() or "").strip()
            if text and text not in collected:
                collected[text] = f"scraped_{len(collected) + 1:03d}"
            if len(collected) >= max_posts:
                break

        page.mouse.wheel(0, 2000)
        page.wait_for_timeout(int(SCROLL_PAUSE_SECONDS * 1000))
        scrolls += 1
        logger.info("Scroll %d/%d — %d unique posts collected so far.", scrolls, MAX_SCROLLS, len(collected))

    return [{"id": post_id, "text": text, "topic": "", "likes": 0} for text, post_id in collected.items()]


def save_posts(posts: list[dict[str, Any]], path: str = config.RAW_POSTS_PATH) -> None:
    """Persist scraped posts to disk as JSON.

    Args:
        posts: List of post dicts as produced by scrape_profile_posts.
        path: Destination file path.
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(posts, f, indent=2, ensure_ascii=False)
    logger.info("Saved %d posts to %s", len(posts), path)


def main() -> None:
    """CLI entry point: log in, scrape the configured profile, save results."""
    config.require_keys("LINKEDIN_EMAIL", "LINKEDIN_PASSWORD", "LINKEDIN_PROFILE_URL")

    with sync_playwright() as pw:
        # headless=False is intentional during scraping: headless browsers are
        # far more likely to be flagged by LinkedIn's bot-detection.
        browser = pw.chromium.launch(headless=False, slow_mo=150)
        context = browser.new_context()
        page = context.new_page()

        try:
            login(page, config.LINKEDIN_EMAIL, config.LINKEDIN_PASSWORD)
            posts = scrape_profile_posts(page, config.LINKEDIN_PROFILE_URL)

            if not posts:
                logger.warning(
                    "No posts were collected. LinkedIn's markup may have "
                    "changed, or the checkpoint/captcha blocked navigation. "
                    "Falling back to data/sample_posts.json is recommended "
                    "so the rest of the pipeline can still be demoed."
                )
            else:
                save_posts(posts)
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    main()

# scraper.py
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
import os, requests, time

# --- LinkedIn credentials ---
LINKEDIN_EMAIL = "sirshendu.kundu22-24@bibs.co.in"
LINKEDIN_PASSWORD = "Skundu97@1996"

# --- Output directory ---
output_dir = r"D:\static\Image"
os.makedirs(output_dir, exist_ok=True)

def scrape_linkedin_for_term(search_term="Cognizant Walk-in Kolkata", max_posts=5):
    posts_data = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)  # fully headless
        context = browser.new_context()
        page = context.new_page()

        # --- Login ---
        page.goto("https://www.linkedin.com/login")
        page.fill("input#username", LINKEDIN_EMAIL)
        page.fill("input#password", LINKEDIN_PASSWORD)
        page.click("button[type='submit']")

        page.wait_for_load_state("networkidle")
        time.sleep(5)  # extra wait for feed to load

        # --- Navigate to LinkedIn feed ---
        page.goto("https://www.linkedin.com/feed/")
        time.sleep(5)

        # --- Search posts ---
        search_box_selector = "input.search-global-typeahead__input"
        try:
            page.wait_for_selector(search_box_selector, timeout=30000)
        except PlaywrightTimeoutError:
            print("⚠️ Search box not found. LinkedIn may have updated their UI or login failed.")
            browser.close()
            return posts_data

        search_box = page.query_selector(search_box_selector)
        search_box.fill(search_term)
        search_box.press("Enter")
        time.sleep(5)

        # --- Click on "Posts" filter ---
        try:
            page.locator("//button[contains(., 'Posts')]").first.click()
            time.sleep(5)
        except PlaywrightTimeoutError:
            print("⚠️ Posts filter not found.")
            browser.close()
            return posts_data

        # --- Scroll to load posts ---
        for _ in range(3):
            page.evaluate("window.scrollBy(0, 1000)")
            time.sleep(2)

        # --- Parse page with BeautifulSoup ---
        soup = BeautifulSoup(page.content(), "html.parser")
        posts = soup.find_all("div", class_="fie-impression-container")
        print(f"📰 Found {len(posts)} posts on page.")

        # --- Loop through posts ---
        for idx, post in enumerate(posts[:max_posts], 1):
            post_dict = {}
            caption_block = post.find("div", class_="update-components-text")
            post_dict["raw_text"] = caption_block.get_text(separator=" ", strip=True) if caption_block else "No caption"

            # --- Extract post images ---
            image_urls = []
            for img_tag in post.find_all("img"):
                src = img_tag.get("src", "")
                classes = img_tag.get("class", [])
                if any("update-components-actor__avatar-image" in c for c in classes):
                    continue
                if "feedshare" in src or "media.licdn" in src:
                    image_urls.append(src)

            post_dict["images"] = []

            # --- Save images ---
            for i, img_url in enumerate(image_urls, 1):
                try:
                    img_data = requests.get(img_url).content
                    img_path = os.path.join(output_dir, f"post_{idx}_image_{i}.jpg")
                    with open(img_path, "wb") as img_file:
                        img_file.write(img_data)
                    post_dict["images"].append(img_path)
                except Exception as e:
                    print(f"⚠️ Failed to download image {img_url}: {e}")

            # --- Save caption text ---
            caption_file = os.path.join(output_dir, f"post_{idx}_caption.txt")
            with open(caption_file, "w", encoding="utf-8") as f:
                f.write(post_dict["raw_text"])

            posts_data.append(post_dict)

        browser.close()

    print(f"🎉 Done! Scraped {len(posts_data)} posts. Check folder: {output_dir}")
    return posts_data


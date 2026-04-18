from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        print("Navigating to URL...")
        page.goto("https://www.threads.net/@_kwang110/post/DW52XA9mRRJ", wait_until="networkidle")
        page.wait_for_timeout(5000)
        print("Saving full HTML to threads_dump.html")
        with open("threads_dump.html", "w", encoding="utf-8") as f:
            f.write(page.content())
        browser.close()

if __name__ == "__main__":
    run()

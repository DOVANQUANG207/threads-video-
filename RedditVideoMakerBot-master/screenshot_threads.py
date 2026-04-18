from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://www.threads.net/@_kwang110/post/DW52XA9mRRJ")
        page.wait_for_timeout(5000)
        page.screenshot(path="threads_debug.png")
        print("Screenshot saved to threads_debug.png")
        browser.close()

if __name__ == "__main__":
    run()

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto('https://www.threads.net/@saigonbacc_/post/DWOee6GiEmB')
    page.wait_for_selector('div[data-pressable-container="true"]', timeout=10000)
    el = page.locator('div[data-pressable-container="true"]').first
    # Test parent hierarchies
    el.locator('xpath=..').screenshot(path='test_p1.png')
    el.locator('xpath=../..').screenshot(path='test_p2.png')
    el.locator('xpath=../../..').screenshot(path='test_p3.png')
    el.locator('xpath=ancestor::div[contains(@class, "x1a2a7pz")][1]').screenshot(path='test_x1.png')
    print('Done')

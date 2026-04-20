import re
from pathlib import Path
from typing import Dict, Final
from playwright.sync_api import ViewportSize, sync_playwright
from utils import settings
from utils.console import print_step, print_substep
from utils.voice import sanitize_text


def get_threads_post(post_url: str = None) -> Dict:
    if not post_url:
        post_url = input("Dán link bài viết Threads vào đây: ")

    print_step(f"Đang lấy dữ liệu từ Threads: {post_url}")
    
    # Extract ID from URL
    match = re.search(r'/post/([^/?]+)', post_url)
    thread_id = match.group(1) if match else "unknown_thread"

    # Đọc cấu hình resolution cho screenshot
    W: Final[int] = int(settings.config["settings"]["resolution_w"])
    H: Final[int] = int(settings.config["settings"]["resolution_h"])

    content = {
        "thread_url": post_url,
        "thread_title": "",
        "thread_id": thread_id,
        "is_nsfw": False,
        "comments": []
    }

    max_comments = int(settings.config["threads"]["max_comments"])
    min_len = int(settings.config["threads"]["min_comment_length"])
    max_len = int(settings.config["threads"]["max_comment_length"])

    # Tạo thư mục chứa ảnh chụp
    Path(f"assets/temp/{thread_id}/png").mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport=ViewportSize(width=W, height=H),
            device_scale_factor=2,
            locale="vi-VN",
            timezone_id="Asia/Ho_Chi_Minh",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            color_scheme="dark" if settings.config["settings"]["theme"] == "dark" else "light"
        )
        page = context.new_page()
        page.goto(post_url, wait_until="networkidle")
        
        # Chờ nội dung tải lên
        page.wait_for_timeout(3000)

        try:
            # === 1. Lấy tiêu đề + chụp ảnh bài viết gốc ===
            main_post_element = page.locator("div[data-pressable-container]").first
            main_post_element.wait_for(timeout=10000)
            
            # Ẩn các đoạn text có link (shopee, http, v.v) trước khi chụp ảnh
            main_post_element.evaluate("""(el) => {
                const links = el.querySelectorAll('a');
                links.forEach(a => {
                    const text = a.innerText.toLowerCase();
                    if (text.includes('shope') || text.includes('http') || text.includes('.vn') || text.includes('.com') || text.includes('link:')) {
                        a.style.display = 'none';
                    }
                });
                
                // Đôi khi link nằm dạng text thường không có thẻ a, ta đổi màu hoặc ẩn text đó (hơi khó nếu là text node chung)
                // Tạm thời ẩn các thẻ a là hiệu quả nhất vì Threads auto biến link thành thẻ a.
            }""")
            
            # Chụp ảnh bài viết gốc
            title_path = f"assets/temp/{thread_id}/png/title.png"
            main_post_element.screenshot(path=title_path)
            print_substep("Đã chụp ảnh bài đăng chính.")
            
            # Lấy tiêu đề từ text
            full_text = main_post_element.inner_text()
            lines = [line.strip() for line in full_text.split("\n") if line.strip()]
            meaningful_lines = [l for l in lines if len(l) > 10]
            if meaningful_lines:
                content["thread_title"] = max(meaningful_lines, key=len)
            else:
                texts = main_post_element.locator('span[dir="auto"]').all_text_contents()
                combined = " ".join([t for t in texts if len(t) > 3])
                content["thread_title"] = combined if combined else ""
            
            if not content["thread_title"]:
                content["thread_title"] = "Threads Story " + thread_id
                
            print_substep(f"Tiêu đề: {content['thread_title'][:80]}...", style="bold green")

            # === 2. Lấy bình luận + chụp ảnh CÙNG LÚC (đảm bảo ảnh khớp text) ===
            reply_count = 0
            processed_replies = set()
            max_scrolls = 15
            scrolls = 0

            while reply_count < max_comments and scrolls < max_scrolls:
                all_containers = page.locator("div[data-pressable-container]").all()
                
                for i in range(1, len(all_containers)):
                    if reply_count >= max_comments:
                        break
                        
                    try:
                        container = all_containers[i]
                        reply_texts = container.locator('span[dir="auto"]').all_text_contents()
                        
                        # Lấy phần nội dung bình luận thực sự:
                        # Tên người dùng thường là span ngắn đứng đầu.
                        # Nội dung bình luận là span DÀI NHẤT trong container.
                        content_texts = [t.strip() for t in reply_texts if len(t.strip()) > 10]
                        if not content_texts:
                            continue
                        # Dùng span dài nhất làm nội dung để TTS đọc
                        full_reply = max(content_texts, key=len)
                        
                        reply_hash = hash(full_reply)
                        if reply_hash not in processed_replies and len(full_reply) > 10:
                            processed_replies.add(reply_hash)
                            
                            # Kiểm tra ngay lập tức xem TOÀN BỘ bình luận có chứa từ khóa tiếp thị / link không
                            text_lower = " ".join(content_texts).lower()
                            if any(kw in text_lower for kw in ['shopee', 'shope.ee', 'http://', 'https://', 'www.', '.vn/', 'lazada', 'tiktok.com']):
                                continue
                                
                            if min_len <= len(full_reply) <= max_len:
                                sanitized = sanitize_text(full_reply)
                                if sanitized:
                                    content["comments"].append({
                                        "comment_body": full_reply,
                                        "comment_url": post_url, 
                                        "comment_id": f"reply_{reply_count}"
                                    })
                                    
                                    # Cuộn đến bình luận 
                                    container.scroll_into_view_if_needed()
                                    page.wait_for_timeout(500)
                                    
                                    # Tự động click vào các nút Spoiler/Bị ẩn nấp bên trong đoạn text
                                    try:
                                        container.evaluate("""(el) => {
                                            const spans = el.querySelectorAll('span[dir="auto"]');
                                            spans.forEach(span => {
                                                const btns = span.querySelectorAll('div[role="button"]');
                                                btns.forEach(b => b.click());
                                            });
                                        }""")
                                        page.wait_for_timeout(500)  # Chờ hiệu ứng mờ biến mất
                                    except:
                                        pass

                                    comment_path = f"assets/temp/{thread_id}/png/comment_{reply_count}.png"
                                    container.screenshot(path=comment_path)
                                    print_substep(f"Đã lấy + chụp bình luận {reply_count}: {full_reply[:40]}...")
                                    reply_count += 1
                    except Exception:
                        continue
                        
                # Cuộn trang xuống để tải thêm bình luận mới
                page.mouse.wheel(0, 1000)
                page.wait_for_timeout(2000)
                scrolls += 1

        except Exception as e:
            print_substep(f"Lỗi khi cào dữ liệu: {e}", style="bold red")
            if not content["thread_title"]:
                content["thread_title"] = "Threads Post " + thread_id

        browser.close()

    if not content["comments"]:
        print_substep("Không tìm thấy bình luận nào phù hợp.", style="bold yellow")
    else:
        print_substep(f"Tổng cộng lấy được {len(content['comments'])} bình luận.", style="bold green")
        
    return content

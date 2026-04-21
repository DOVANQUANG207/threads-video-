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
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            color_scheme="dark" if settings.config["settings"]["theme"] == "dark" else "light"
        )
        page = context.new_page()
        page.goto(post_url, wait_until="networkidle")
        
        # Chờ nội dung tải lên
        page.wait_for_timeout(5000)

        # Thêm CSS để TẮT HOÀN TOÀN hiệu ứng làm mờ và ẩn popup đăng nhập (bất chấp React)
        try:
            page.add_style_tag(content="""
                * {
                    filter: none !important;
                    backdrop-filter: none !important;
                }
                div[role="dialog"], #login-modal, [data-testid="login-modal"] {
                    display: none !important;
                    opacity: 0 !important;
                    visibility: hidden !important;
                    pointer-events: none !important;
                }
                body {
                    overflow: auto !important;
                    pointer-events: auto !important;
                }
            """)
        except:
            pass

        # --- Xóa popup đăng nhập và lớp phủ đen mờ bằng JavaScript ---
        try:
            page.evaluate('''() => {
                // Khôi phục khả năng cuộn trang và tương tác
                document.body.style.overflow = 'auto';
                document.body.style.pointerEvents = 'auto';
                
                // Xóa tất cả các dialog/modal (thường là popup đăng nhập)
                const dialogs = document.querySelectorAll('div[role="dialog"]');
                for (let d of dialogs) d.remove();
                
                // Tìm và xóa các lớp phủ, banner và hiệu ứng làm mờ
                const allElements = document.querySelectorAll('*');
                for (let el of allElements) {
                    const style = window.getComputedStyle(el);
                    
                    // Xóa các phần tử cố định đè lên màn hình (banner đăng nhập)
                    if ((style.position === 'fixed' || style.position === 'sticky') && parseInt(style.zIndex) > 10) {
                        el.remove();
                        continue;
                    }
                    
                    // Loại bỏ hiệu ứng làm mờ (blur)
                    if (style.filter.includes('blur') || style.backdropFilter.includes('blur')) {
                        el.style.filter = 'none';
                        el.style.backdropFilter = 'none';
                    }
                }
            }''')
            print_substep("Đã dọn dẹp các lớp phủ đăng nhập và làm mờ.")
            page.wait_for_timeout(1000)
        except Exception as e:
            print_substep(f"Không thể chạy JS dọn dẹp popup: {e}")

        try:
            core_el = page.locator('div[data-pressable-container="true"]').first
            main_post_element = None
            if core_el.count() > 0:
                core_el.scroll_into_view_if_needed()
                page.wait_for_timeout(1000)
                # Row container is usually the grandparent
                row_el = core_el.locator("xpath=../..")
                if row_el.count() > 0 and row_el.is_visible():
                    main_post_element = row_el
                elif core_el.is_visible():
                    main_post_element = core_el
            
            if main_post_element:
                # Chụp ảnh bài viết gốc
                title_path = f"assets/temp/{thread_id}/png/title.png"
                main_post_element.screenshot(path=title_path)
                print_substep("Đã chụp ảnh bài đăng chính.")
                
                # Lấy tiêu đề từ text
                texts = main_post_element.locator('span[dir="auto"]').all_text_contents()
                content_texts = [t.strip() for t in texts if len(t.strip()) > 8]
                if not content_texts:
                    texts = main_post_element.locator('div[dir="auto"]').all_text_contents()
                    content_texts = [t.strip() for t in texts if len(t.strip()) > 8]
                
                # Loại bỏ username nếu nó là phần tử đầu tiên
                if content_texts and " " not in content_texts[0] and len(content_texts[0]) <= 20:
                    content_texts = content_texts[1:]
                    
                content["thread_title"] = "\n".join(content_texts) if content_texts else ""
            else:
                content["thread_title"] = ""
            
            if not content["thread_title"]:
                content["thread_title"] = "Threads Story " + thread_id
                
            print_substep(f"Tiêu đề: {content['thread_title'][:80]}...", style="bold green")

            # === 2. Lấy bình luận + chụp ảnh CÙNG LÚC (đảm bảo ảnh khớp text) ===
            reply_count = 0
            processed_replies = set()
            max_scrolls = 15
            scrolls = 0

            while reply_count < max_comments and scrolls < max_scrolls:
                # Tìm tất cả các container có khả năng là bài viết hoặc bình luận
                all_containers = page.locator("article, div[data-pressable-container]").all()
                
                if len(all_containers) <= 1:
                    print_substep(f"Đang cuộn tìm thêm bình luận (Lần {scrolls+1})...")
                
                # Bắt đầu từ index 1 để bỏ qua bài viết gốc (Topic)
                for i in range(1, len(all_containers)):
                    if reply_count >= max_comments:
                        break
                        
                    try:
                        container = all_containers[i]
                        # Bỏ qua nếu container không hiển thị hoặc quá nhỏ
                        if not container.is_visible():
                            continue
                            
                        box = container.bounding_box()
                        if not box or box['height'] < 50:
                            continue

                        reply_texts = container.locator('span[dir="auto"]').all_text_contents()
                        
                        content_texts = [t.strip() for t in reply_texts if len(t.strip()) > 8]
                        if not content_texts:
                            continue
                            
                        # Loại bỏ username nếu nó bị lẫn vào (thường là từ đầu tiên không có khoảng trắng)
                        if content_texts and " " not in content_texts[0] and len(content_texts[0]) <= 20:
                            content_texts = content_texts[1:]
                            
                        if not content_texts:
                            continue

                        # Gộp TẤT CẢ các dòng văn bản lại để TTS đọc đầy đủ (không bị sót dòng)
                        full_reply = "\n".join(content_texts)
                        
                        # Bộ lọc spam: Loại bỏ bình luận shopee, quảng cáo, mua bán
                        spam_keywords = [
                            "shopee", "lazada", "tiktok shop", "giỏ hàng", 
                            "link bio", "link ở bio", "link dưới", "sản phẩm", 
                            "mua ngay", "đặt hàng", "inbox", "ib cho", "pass lại",
                            "mua ở đâu", "mua hàng", "bán hàng", "mua đi", "chốt đơn"
                        ]
                        if any(kw in full_reply.lower() for kw in spam_keywords):
                            print_substep(f"Bỏ qua bình luận quảng cáo/bán hàng: {full_reply[:30]}...", style="bold yellow")
                            continue
                        
                        reply_hash = hash(full_reply)
                        if reply_hash not in processed_replies and len(full_reply) > 10:
                            processed_replies.add(reply_hash)
                            if min_len <= len(full_reply) <= max_len:
                                sanitized = sanitize_text(full_reply)
                                if sanitized:
                                    # Cuộn đến bình luận và đợi thêm để tải nội dung/ảnh (tránh bị che/chưa load kịp)
                                    container.scroll_into_view_if_needed()
                                    page.wait_for_timeout(1500)
                                    comment_path = f"assets/temp/{thread_id}/png/comment_{reply_count}.png"
                                    container.screenshot(path=comment_path)
                                    
                                    content["comments"].append({
                                        "comment_body": full_reply,
                                        "comment_url": post_url, 
                                        "comment_id": f"reply_{reply_count}"
                                    })
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

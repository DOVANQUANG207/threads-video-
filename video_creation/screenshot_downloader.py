import json
import re
from pathlib import Path
from typing import Dict, Final

from utils import settings
from utils.console import print_step, print_substep

__all__ = ["get_screenshots_of_posts"]


def get_screenshots_of_posts(post_data: dict, screenshot_num: int):
    """Verifies screenshots exist. Screenshots are now captured during scraping
    to ensure image-audio sync. This function only checks that files are present.
    """
    thread_id = re.sub(r"[^\w\s-]", "", post_data["thread_id"])
    png_dir = Path(f"assets/temp/{thread_id}/png")
    
    print_step("Kiểm tra ảnh chụp màn hình...")
    
    # Kiểm tra title
    title_path = png_dir / "title.png"
    if title_path.exists():
        print_substep("✓ Ảnh bài đăng chính đã có sẵn.")
    else:
        print_substep("✗ Thiếu ảnh bài đăng chính!", style="bold red")
    
    # Kiểm tra các comment
    found = 0
    for i in range(screenshot_num):
        comment_path = png_dir / f"comment_{i}.png"
        if comment_path.exists():
            found += 1
        else:
            print_substep(f"✗ Thiếu ảnh comment_{i}.png", style="bold yellow")
    
    print_substep(f"✓ Đã xác nhận {found}/{screenshot_num} ảnh bình luận.", style="bold green")

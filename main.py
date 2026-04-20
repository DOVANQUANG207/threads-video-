#!/usr/bin/env python
import math
import sys
from os import name
from pathlib import Path
from subprocess import Popen
from typing import Dict, NoReturn



from threads.post_scraper import get_threads_post
from utils import settings
from utils.cleanup import cleanup
from utils.console import print_markdown, print_step, print_substep
from utils.ffmpeg_install import ffmpeg_install
from utils.id import extract_id
from utils.version import checkversion
from video_creation.background import (
    chop_background,
    download_background_audio,
    download_background_video,
    get_background_config,
)
from video_creation.final_video import make_final_video
from video_creation.screenshot_downloader import get_screenshots_of_posts
from video_creation.voices import save_text_to_mp3

__VERSION__ = "3.4.0"


print_markdown(
    "### Cảm ơn bạn đã sử dụng công cụ tạo video từ Threads!"
)
checkversion(__VERSION__)

post_id: str
post_data: Dict[str, str | list]

def main(POST_URL=None) -> None:
    global post_id, post_data
    post_data = get_threads_post(POST_URL)
    post_id = extract_id(post_data)
    print_substep(f"Thread ID is {post_id}", style="bold blue")
    length, number_of_comments = save_text_to_mp3(post_data)
    length = math.ceil(length)
    get_screenshots_of_posts(post_data, number_of_comments)
    bg_config = {
        "video": get_background_config("video"),
        "audio": get_background_config("audio"),
    }
    download_background_video(bg_config["video"])
    download_background_audio(bg_config["audio"])
    chop_background(bg_config, length, post_data)
    make_final_video(number_of_comments, length, post_data, bg_config)


def run_many(times) -> None:
    for x in range(1, times + 1):
        print_step(
            f'on the {x}{("th", "st", "nd", "rd", "th", "th", "th", "th", "th", "th")[x % 10]} iteration of {times}'
        )
        main()
        Popen("cls" if name == "nt" else "clear", shell=True).wait()


def shutdown() -> NoReturn:
    if "post_id" in globals():
        print_markdown("## Clearing temp files")
        cleanup(post_id)

    print("Exiting...")
    sys.exit()


if __name__ == "__main__":
    if sys.version_info.major != 3 or sys.version_info.minor not in [10, 11, 12, 13, 14]:
        print(
            f"Hey! Your Python version is {sys.version_info.major}.{sys.version_info.minor}. This program is optimized for 3.10-3.12, but we'll try running on your version."
        )
    ffmpeg_install()
    directory = Path().absolute()
    config = settings.check_toml(
        f"{directory}/utils/.config.template.toml", f"{directory}/config.toml"
    )
    config is False and sys.exit()

    if (
        not settings.config["settings"]["tts"]["tiktok_sessionid"]
        or settings.config["settings"]["tts"]["tiktok_sessionid"] == ""
    ) and config["settings"]["tts"]["voice_choice"] == "tiktok":
        print_substep(
            "TikTok voice requires a sessionid! Check our documentation on how to obtain one.",
            "bold red",
        )
        sys.exit()
    try:
        print_step("--- CẤU HÌNH NHANH CHO VIDEO ---")
        
        # 1. Thread URL
        default_url = config["threads"].get("post_url", "")
        post_url_input = input(f"Nhập link Threads (bỏ trống để dùng '{default_url}'): ").strip()
        if post_url_input:
            config["threads"]["post_url"] = post_url_input
            
        # 2. Background Video
        bg_opts = ["minecraft", "gta", "rocket-league", "motor-gta", "csgo-surf", "cluster-truck", "minecraft-2", "multiversus", "fall-guys", "steep"]
        default_bg = config["settings"]["background"].get("background_video", "minecraft")
        bg_video_input = input(f"Nhập video nền ({', '.join(bg_opts)})\n(bỏ trống để dùng '{default_bg}'): ").strip()
        if bg_video_input:
            config["settings"]["background"]["background_video"] = bg_video_input

        # 3. Voice Choice
        voice_opts = ["GHVoice", "EdgeTTS", "TikTok", "elevenlabs", "googletranslate"]
        default_voice = config["settings"]["tts"].get("voice_choice", "GHVoice")
        voice_input = input(f"Chọn TTS ({', '.join(voice_opts)})\n(bỏ trống để dùng '{default_voice}'): ").strip()
        if voice_input:
            config["settings"]["tts"]["voice_choice"] = voice_input

        # 4. GH Voice name if selected
        if config["settings"]["tts"]["voice_choice"].lower() == "ghvoice":
            voices_dir = Path("saved_voices")
            available_voices = [d.name for d in voices_dir.iterdir() if d.is_dir()] if voices_dir.exists() else []
            default_name = config["settings"]["tts"].get("gh_voice_name", "Ngọc Huyền 01")
            if available_voices:
                gh_voice_input = input(f"Chọn giọng GH Voice ({', '.join(available_voices)})\n(bỏ trống để dùng '{default_name}'): ").strip()
                if gh_voice_input:
                    config["settings"]["tts"]["gh_voice_name"] = gh_voice_input

        print_step("--- BẮT ĐẦU TẠO VIDEO ---")

        if config["threads"]["post_url"]:
            main(config["threads"]["post_url"])
        else:
            main()
    except KeyboardInterrupt:
        shutdown()
    except Exception as err:
        config["settings"]["tts"]["tiktok_sessionid"] = "REDACTED"
        config["settings"]["tts"]["elevenlabs_api_key"] = "REDACTED"
        config["settings"]["tts"]["openai_api_key"] = "REDACTED"
        print_step(
            f"Rất tiếc, đã có lỗi xảy ra!\n"
            f"Phiên bản: {__VERSION__} \n"
            f"Lỗi: {err} \n"
            f'Cấu hình: {config["settings"]}'
        )
        raise err

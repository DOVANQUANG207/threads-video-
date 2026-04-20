import json
import time

def check_done(
    post_id: str,
) -> bool:
    """Checks if the chosen post has already been generated
    """
    try:
        with open("./video_creation/data/videos.json", "r", encoding="utf-8-sig") as done_vids_raw:
            done_videos = json.load(done_vids_raw)
        for video in done_videos:
            if video["id"] == post_id:
                return True
    except (json.JSONDecodeError, FileNotFoundError):
        pass
    return False


def save_data(source: str, filename: str, post_title: str, post_id: str, credit: str):
    """Saves the videos that have already been generated to a JSON file in video_creation/data/videos.json"""
    try:
        with open("./video_creation/data/videos.json", "r", encoding="utf-8-sig") as raw_vids:
            done_vids = json.load(raw_vids)
    except (json.JSONDecodeError, FileNotFoundError):
        done_vids = []

    if post_id in [video["id"] for video in done_vids]:
        return  # video already done

    payload = {
        "source": source,
        "id": post_id,
        "time": str(int(time.time())),
        "background_credit": credit,
        "post_title": post_title,
        "filename": filename,
    }
    done_vids.append(payload)

    # Ghi lại file với UTF-8 không có BOM
    with open("./video_creation/data/videos.json", "w", encoding="utf-8") as raw_vids:
        json.dump(done_vids, raw_vids, ensure_ascii=False, indent=4)


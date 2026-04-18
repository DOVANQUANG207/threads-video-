import sys
import json
from pathlib import Path
from utils import settings
import traceback
import io

# Force utf-8 outputs
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def run():
    try:
        directory = Path().absolute()
        config = settings.check_toml(
            f"{directory}/utils/.config.template.toml", f"{directory}/config.toml"
        )
        settings.config = config
        from threads.post_scraper import get_threads_post
        url = "https://www.threads.net/@_kwang110/post/DW52XA9mRRJ"
        data = get_threads_post(url)
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception as e:
        traceback.print_exc()

run()

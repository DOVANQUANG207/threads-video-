import re
from typing import Optional

from utils.console import print_substep


def extract_id(post_data: dict, field: Optional[str] = "thread_id"):
    """
    This function takes a post data object and returns the post id
    """
    if field not in post_data.keys():
        raise ValueError(f"Field '{field}' not found in post data object")
    post_id = re.sub(r"[^\w\s-]", "", post_data[field])
    return post_id

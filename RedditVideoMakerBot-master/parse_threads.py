import json
import re
from bs4 import BeautifulSoup

with open("threads_dump.html", "r", encoding="utf-8") as f:
    text = f.read()

# Let's find all divs that might act as article
# Threads usually uses div[data-pressable-container="true"] for clickable posts/replies.
soup = BeautifulSoup(text, "html.parser")
containers = soup.find_all("div", attrs={"data-pressable-container": "true"})

out = {
    "articles": text.count("<article"),
    "pressable_containers": len(containers),
    "posts": []
}

for c in containers:
    # Get all text from span[dir="auto"] inside this container
    spans = c.find_all("span", dir="auto")
    texts = [s.get_text(strip=True) for s in spans]
    full_text = " ".join([t for t in texts if len(t) > 5])
    if full_text:
        out["posts"].append(full_text)

with open("threads_parsed.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

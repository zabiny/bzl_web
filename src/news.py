import re
from datetime import date
from pathlib import Path

from flask import render_template_string


class NewsItem:
    def __init__(self, content: str, filename: str) -> None:
        self.raw_content = content

        # Parse date and title from filename (e.g., "2024-11-16_sportega_partner.html")
        date_str = filename.replace(".html", "").split("_")[0]
        year, month, day = date_str.split("-")
        self.created_at = date(int(year), int(month), int(day))

        # Extract title from h2 tag in content
        h2_match = re.search(r"<h2[^>]*>(.*?)</h2>", content)
        self.title = h2_match.group(1) if h2_match else None

    def get_rendered_content(self) -> str:
        # Render the content when needed, processing any template tags
        rendered = render_template_string(self.raw_content)
        # Remove the h2 title from the rendered content
        h2_match = re.search(r"<h2[^>]*>(.*?)</h2>", rendered)
        if h2_match:
            rendered = rendered.replace(h2_match.group(0), "")
        return rendered


def load_news() -> list[NewsItem]:
    news_dir = Path("templates/news")
    news_items = []

    for file in sorted(news_dir.glob("*.html"), reverse=True):
        with open(file, "r", encoding="utf-8") as f:
            content = f.read()
            news_items.append(NewsItem(content, file.name))

    return news_items

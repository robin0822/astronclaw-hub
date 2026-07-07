from typing import Any


def paginate(items: list[dict[str, Any]], page: int = 1, page_size: int = 20) -> dict[str, Any]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)
    start = (page - 1) * page_size
    return {
        "items": items[start : start + page_size],
        "page": page,
        "pageSize": page_size,
        "total": len(items),
    }

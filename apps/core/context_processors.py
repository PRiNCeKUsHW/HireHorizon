from apps.blog.models import Post


def rail_content(request):
    """Posts for the right-hand 'Up next' list.

    One small query, and only for pages that actually render the rail — GET
    requests to HTML pages. Skipped for POSTs and admin so the toggle
    endpoints stay at the query count they had before.
    """
    if request.method != "GET" or request.path.startswith("/admin/"):
        return {}
    return {"rail_posts": Post.objects.published().for_feed()[:4]}

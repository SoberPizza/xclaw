"""Pre-defined icon classification labels for SigLIP 2 zero-shot classifier.

Optimized for Web browser + social media scenarios (~100 labels).
Each label uses descriptive 2-6 word phrases for better SigLIP text-image alignment.
"""

ICON_LABELS: list[str] = [
    # ── Window / browser controls ──
    "close button", "minimize button", "maximize button",
    # ── Navigation ──
    "back arrow", "forward arrow", "refresh button", "home button",
    "up arrow", "down arrow", "left arrow", "right arrow",
    "dropdown arrow", "expand arrow", "collapse arrow",
    # ── Menus ──
    "hamburger menu", "more options", "sidebar toggle", "tab",
    # ── Search & filter ──
    "search magnifying glass", "filter funnel", "sort",
    # ── Common actions ──
    "add plus button", "delete", "trash can", "edit pencil",
    "save", "download arrow", "upload arrow", "share button", "send arrow",
    "link chain", "attachment paperclip",
    # ── State indicators ──
    "checkbox checked", "checkbox unchecked",
    "toggle on", "toggle off",
    # ── Security / visibility ──
    "lock", "unlock", "eye visible", "eye hidden", "shield",
    # ── Settings / info ──
    "settings gear", "info circle", "help question mark", "warning triangle",
    # ── Generic content ──
    "image photo", "user avatar", "group people",

    # ── Social media actions ──
    "reply curved arrow",
    "repost retweet arrows",
    "quote tweet bubble",
    "follow plus person",
    "verified checkmark badge",
    "thumbs up",
    "thumbs down",
    "heart like button",
    "upvote arrow",
    "downvote arrow",
    "emoji reaction smiley",
    "subscribe bell",
    "live streaming",
    "stories circle",
    "direct message paper plane",
    "save to collection",
    "report flag",
    "block circle",
    "mute notifications",
    "poll chart",
    "thread",

    # ── Platform logos ──
    "X Twitter logo", "Facebook logo", "Instagram camera logo",
    "YouTube play logo", "LinkedIn logo", "Reddit alien logo",
    "TikTok logo", "WeChat logo", "Weibo logo",
    "Bilibili logo", "Xiaohongshu logo",

    # ── Browser / web-specific ──
    "new tab plus", "close tab", "bookmark star", "history clock",
    "extensions puzzle", "translate globe",
    "dark mode moon", "light mode sun",
    "zoom in", "zoom out",

    # ── Media playback (web video) ──
    "play triangle", "pause", "volume speaker", "mute",
    "fullscreen video", "closed captions",
]

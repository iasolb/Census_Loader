# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  COMPOSITES                                                             ║
# ╚═══════════════════════════════════════════════════════════════════════════╝
SERIES1 = None
SERIES2 = None
SERIES3 = None
SERIES4 = None

CATEGORY1 = {**SERIES1, **SERIES2}
CATEGORY2 = {**SERIES3, **SERIES4}

ALL_SERIES = {
    **SERIES1,
    **SERIES2,
    **SERIES3,
    **SERIES4,
}

# ── Category lookup (top-level) ───────────────────────────────────────────
CATEGORIES = {
    "CATEGORY1": CATEGORY1,
    "CATEGORY2": CATEGORY2,
}

# ── Subcategory lookup (nested, with variable references) ─────────────────
SUBCATEGORIES = {
    "CATEGORY1": {
        "SUBCATEGORY1": SERIES1,
        "SUBCATEGORY2": SERIES2,
    },
    "CATEGORY2": {
        "SUBCATEGORY3": SERIES3,
        "SUBCATEGORY4": SERIES4,
    },
}

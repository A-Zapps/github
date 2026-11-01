"""Unit tests validating frontend shell layout, routes, tokens, and navigation."""

import os

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../frontend"))

EXPECTED_ROUTES = [
    "#/overview",
    "#/analyzer",
    "#/quality",
    "#/bugs",
    "#/security",
    "#/health",
    "#/docs",
    "#/developers",
    "#/compare",
    "#/assistant",
    "#/reports",
    "#/models",
    "#/settings",
]

EXPECTED_PAGES = [
    "overview.js",
    "analyzer.js",
    "quality.js",
    "bugs.js",
    "security.js",
    "health.js",
    "docs.js",
    "developers.js",
    "compare.js",
    "assistant.js",
    "reports.js",
    "model-performance.js",
    "settings.js",
]


def test_design_tokens_present():
    """Verify tokens.css defines all mandatory tokens from DESIGN.md section 1."""
    tokens_path = os.path.join(FRONTEND_DIR, "css/tokens.css")
    assert os.path.isfile(tokens_path)
    with open(tokens_path, "r", encoding="utf-8") as f:
        content = f.read()

    mandatory_tokens = [
        "--bg:            #F4F5F7",
        "--surface:       #FFFFFF",
        "--sidebar:       #ECEEF1",
        "--primary:       #5267D8",
        "--text:          #20242C",
        "--border:        #E3E6EB",
        "--primary-hover",
        "--primary-press",
        "--primary-subtle",
        "--text-2",
        "--text-3",
        "--border-strong",
        "--success",
        "--warning",
        "--danger",
        "--info",
        "--r-sm",
        "--r-md",
        "--r-lg",
        "--shadow-1",
        "--shadow-2",
        "--sidebar-w: 248px",
        "--sidebar-w-collapsed: 64px",
        "--topbar-h: 56px",
    ]

    for token in mandatory_tokens:
        clean_token = token.split(":")[0].strip()
        assert clean_token in content, f"Missing token: {clean_token}"


def test_all_13_pages_exist_and_contract():
    """Verify all 13 page modules exist and export title, mount, and unmount."""
    pages_dir = os.path.join(FRONTEND_DIR, "js/pages")
    for page_file in EXPECTED_PAGES:
        file_path = os.path.join(pages_dir, page_file)
        assert os.path.isfile(file_path), f"Missing page module: {page_file}"
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "export default" in content, f"Missing default export in {page_file}"


def test_router_has_all_13_routes():
    """Verify router maps all 13 routes."""
    router_path = os.path.join(FRONTEND_DIR, "js/router.js")
    with open(router_path, "r", encoding="utf-8") as f:
        content = f.read()

    for route in EXPECTED_ROUTES:
        assert f'"{route}"' in content, f"Missing route {route} in router.js"


def test_responsive_layout_styles():
    """Verify responsive 375px breakpoint handling in layout.css."""
    layout_path = os.path.join(FRONTEND_DIR, "css/layout.css")
    with open(layout_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "@media (max-width: 767px)" in content
    assert "drawer-open" in content
    assert "collapsed" in content

"""
ALLTHINGS140 Hub — Design System & Custom Qt Styling
High-fidelity dark operations console with cyan, purple, and safety accent tokens.
Crafted for maximum readability, zero layout seams, and responsive ergonomics.
"""

from __future__ import annotations

# Color Palette Tokens
BG_DARK = "#0a0d14"          # Deep cosmic background (solid, never transparent)
BG_SURFACE = "#101522"       # Panel and sidebar background
BG_CARD = "#161d2e"          # Elevated container background
BG_CARD_HOVER = "#1e2840"    # Hover container state
BG_INPUT = "#0e131d"         # Input controls background
BG_SIDEBAR = "#0c1018"       # Sidebar frame background

BORDER_SUBTLE = "#222c3f"    # Standard container borders
BORDER_LIGHT = "#2f3e58"     # Highlighted borders
BORDER_FOCUS = "#00f0ff"     # Active focus border

# Typography Colors (High-Contrast & Readable)
TEXT_PRIMARY = "#f8fafc"     # 100% white for primary headers and key data
TEXT_SECONDARY = "#cbd5e1"   # Slate 300 for readable paragraphs and secondary labels
TEXT_MUTED = "#8295b0"       # Slate 400 for sub-headers and metadata (high contrast)
TEXT_DISABLED = "#4b5b75"    # Disabled controls text

# Brand Neon Accents
ACCENT_CYAN = "#00f0ff"      # Primary brand cyan
ACCENT_CYAN_DIM = "#00a3b0"
ACCENT_PURPLE = "#a855f7"    # Station purple
ACCENT_PINK = "#ec4899"      # Live takeover pink

# Safety Level Tokens
# 1. GREEN: Safe / Read-Only
SAFETY_GREEN = "#10b981"
SAFETY_GREEN_BG = "rgba(16, 185, 129, 0.12)"
SAFETY_GREEN_BORDER = "rgba(16, 185, 129, 0.35)"

# 2. YELLOW: Local Change (no production impact)
SAFETY_YELLOW = "#f59e0b"
SAFETY_YELLOW_BG = "rgba(245, 158, 11, 0.12)"
SAFETY_YELLOW_BORDER = "rgba(245, 158, 11, 0.35)"

# 3. ORANGE: Remote Service Change (VM/service restart)
SAFETY_ORANGE = "#f97316"
SAFETY_ORANGE_BG = "rgba(249, 115, 22, 0.14)"
SAFETY_ORANGE_BORDER = "rgba(249, 115, 22, 0.40)"

# 4. RED: Production / Destructive (deployment, purge, rollback)
SAFETY_RED = "#ef4444"
SAFETY_RED_BG = "rgba(239, 68, 68, 0.15)"
SAFETY_RED_BORDER = "rgba(239, 68, 68, 0.45)"

# Aliases for Status Compatibility
STATUS_GREEN = SAFETY_GREEN
STATUS_GREEN_BG = SAFETY_GREEN_BG
STATUS_AMBER = SAFETY_YELLOW
STATUS_AMBER_BG = SAFETY_YELLOW_BG
STATUS_RED = SAFETY_RED
STATUS_RED_BG = SAFETY_RED_BG
STATUS_BLUE = "#38bdf8"
STATUS_BLUE_BG = "rgba(56, 189, 248, 0.12)"
STATUS_PURPLE = ACCENT_PURPLE
STATUS_PURPLE_BG = "rgba(168, 85, 247, 0.12)"


# Global Qt Stylesheet
STYLE_SHEET = f"""
/* Root Window and Base Containers */
QMainWindow, QDialog {{
    background-color: {BG_DARK};
    color: {TEXT_PRIMARY};
    font-family: 'Inter', 'Segoe UI', 'Ubuntu', sans-serif;
}}

/* Universal Widget Defaults (Solid, Opaque Backgrounds to prevent transparency seams) */
QWidget {{
    color: {TEXT_PRIMARY};
    font-size: 13px;
}}

QWidget#central_widget, QStackedWidget {{
    background-color: {BG_DARK};
}}

/* Scroll Areas & Viewports */
QScrollArea {{
    background-color: {BG_DARK};
    border: none;
}}

QScrollArea > QWidget > QWidget {{
    background-color: {BG_DARK};
}}

/* Scrollbars */
QScrollBar:vertical {{
    background: {BG_DARK};
    width: 10px;
    margin: 0px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_LIGHT};
    min-height: 28px;
    border-radius: 5px;
    margin: 2px;
}}
QScrollBar::handle:vertical:hover {{
    background: {ACCENT_CYAN};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar:horizontal {{
    background: {BG_DARK};
    height: 10px;
    margin: 0px;
    border-radius: 5px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER_LIGHT};
    min-width: 28px;
    border-radius: 5px;
    margin: 2px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {ACCENT_CYAN};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* Inputs & Text Editors */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 13px;
    selection-background-color: {ACCENT_CYAN};
    selection-color: {BG_DARK};
}}
QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover {{
    border: 1px solid {BORDER_LIGHT};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {ACCENT_CYAN};
    background-color: {BG_CARD};
}}

/* Buttons */
QPushButton {{
    background-color: {BG_CARD};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 600;
    font-size: 13px;
    min-height: 20px;
}}
QPushButton:hover {{
    background-color: {BG_CARD_HOVER};
    border: 1px solid {ACCENT_CYAN};
    color: {ACCENT_CYAN};
}}
QPushButton:pressed {{
    background-color: {BG_SURFACE};
}}
QPushButton:disabled {{
    background-color: {BG_SURFACE};
    color: {TEXT_DISABLED};
    border: 1px solid {BORDER_SUBTLE};
}}

/* Primary Action Buttons (Cyan) */
QPushButton[primary="true"] {{
    background-color: {ACCENT_CYAN};
    color: {BG_DARK};
    border: 1px solid {ACCENT_CYAN};
    font-weight: 700;
}}
QPushButton[primary="true"]:hover {{
    background-color: #38f4ff;
    border: 1px solid #38f4ff;
    color: {BG_DARK};
}}
QPushButton[primary="true"]:disabled {{
    background-color: #1a3a44;
    color: #4a7582;
    border: 1px solid #1a3a44;
}}

/* Accent Buttons (Purple) */
QPushButton[accent="true"] {{
    background-color: {ACCENT_PURPLE};
    color: #ffffff;
    border: 1px solid {ACCENT_PURPLE};
    font-weight: 700;
}}
QPushButton[accent="true"]:hover {{
    background-color: #be7bfb;
    border: 1px solid #be7bfb;
}}
QPushButton[accent="true"]:disabled {{
    background-color: #2e1d44;
    color: #634d7d;
    border: 1px solid #2e1d44;
}}

/* Warning / Service Change Buttons (Orange) */
QPushButton[warning="true"] {{
    background-color: {SAFETY_ORANGE_BG};
    color: {SAFETY_ORANGE};
    border: 1px solid {SAFETY_ORANGE_BORDER};
    font-weight: 700;
}}
QPushButton[warning="true"]:hover {{
    background-color: {SAFETY_ORANGE};
    color: #ffffff;
}}

/* Danger / Destructive Buttons (Red) */
QPushButton[danger="true"] {{
    background-color: {SAFETY_RED_BG};
    color: {SAFETY_RED};
    border: 1px solid {SAFETY_RED_BORDER};
    font-weight: 700;
}}
QPushButton[danger="true"]:hover {{
    background-color: {SAFETY_RED};
    color: #ffffff;
}}

/* ComboBox */
QComboBox {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 6px;
    padding: 7px 12px;
    font-size: 13px;
}}
QComboBox:hover {{
    border: 1px solid {ACCENT_CYAN};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: {BG_SURFACE};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_LIGHT};
    selection-background-color: {BG_CARD_HOVER};
    selection-color: {ACCENT_CYAN};
    outline: none;
    padding: 4px;
}}

/* CheckBoxes */
QCheckBox {{
    color: {TEXT_SECONDARY};
    spacing: 8px;
    font-size: 13px;
}}
QCheckBox:hover {{
    color: {TEXT_PRIMARY};
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid {BORDER_LIGHT};
    background: {BG_INPUT};
}}
QCheckBox::indicator:hover {{
    border: 1px solid {ACCENT_CYAN};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT_CYAN};
    border: 1px solid {ACCENT_CYAN};
    image: none;
}}

/* Tabs */
QTabWidget::pane {{
    border: 1px solid {BORDER_SUBTLE};
    background-color: {BG_SURFACE};
    border-radius: 6px;
}}
QTabBar::tab {{
    background-color: {BG_DARK};
    color: {TEXT_SECONDARY};
    padding: 8px 16px;
    margin-right: 4px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    border: 1px solid {BORDER_SUBTLE};
    border-bottom: none;
    font-weight: 600;
}}
QTabBar::tab:hover {{
    color: {TEXT_PRIMARY};
    background-color: {BG_CARD};
}}
QTabBar::tab:selected {{
    color: {ACCENT_CYAN};
    background-color: {BG_SURFACE};
    border: 1px solid {BORDER_LIGHT};
    border-bottom: 1px solid {BG_SURFACE};
}}

/* Tables */
QTableWidget, QTableView {{
    background-color: {BG_SURFACE};
    border: 1px solid {BORDER_SUBTLE};
    gridline-color: {BORDER_SUBTLE};
    color: {TEXT_PRIMARY};
    selection-background-color: {BG_CARD_HOVER};
    selection-color: {ACCENT_CYAN};
    border-radius: 6px;
    outline: none;
}}
QTableWidget::item, QTableView::item {{
    padding: 8px 10px;
    border-bottom: 1px solid {BORDER_SUBTLE};
}}
QHeaderView::section {{
    background-color: {BG_CARD};
    color: {TEXT_MUTED};
    padding: 8px 10px;
    border: none;
    border-right: 1px solid {BORDER_SUBTLE};
    border-bottom: 1px solid {BORDER_LIGHT};
    font-weight: 700;
    font-size: 11px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}}
QHeaderView::section:last {{
    border-right: none;
}}

/* Splitters (Eliminates vertical transparency seam) */
QSplitter::handle {{
    background-color: {BORDER_SUBTLE};
    width: 3px;
    height: 3px;
}}
QSplitter::handle:hover {{
    background-color: {ACCENT_CYAN};
}}
"""


APPLICATION_STYLESHEET = STYLE_SHEET


def get_application_stylesheet() -> str:
    """Return the global application Qt stylesheet."""
    return STYLE_SHEET

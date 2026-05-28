"""Generate the Week 8 presentation PowerPoint with a dark tech theme."""

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE_TYPE
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
OUTPUT_PATH = os.path.join(REPORTS_DIR, "week8_presentation.pptx")

# Palette
BG       = RGBColor(0x0d, 0x11, 0x17)
PANEL    = RGBColor(0x16, 0x1b, 0x22)
ACCENT   = RGBColor(0x58, 0xa6, 0xff)   # blue
GREEN    = RGBColor(0x3f, 0xb9, 0x50)   # green
RED      = RGBColor(0xff, 0x7b, 0x72)   # red
YELLOW   = RGBColor(0xe3, 0xb3, 0x41)   # yellow
TITLE_C  = RGBColor(0xe6, 0xed, 0xf3)   # near-white
TEXT_C   = RGBColor(0xb0, 0xbe, 0xcc)   # light grey
MUTED    = RGBColor(0x7d, 0x8b, 0x97)   # muted grey


def new_prs() -> Presentation:
    prs = Presentation()
    prs.slide_width  = Inches(13.33)
    prs.slide_height = Inches(7.5)
    return prs


def add_blank_slide(prs: Presentation):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = BG
    return slide


def title_bar(slide, text: str, y=Inches(0.28)):
    tb = slide.shapes.add_textbox(Inches(0.55), y, Inches(12.2), Inches(0.7))
    tf = tb.text_frame
    p = tf.paragraphs[0]
    run = p.add_run()
    run.text = text
    run.font.size = Pt(30)
    run.font.bold = True
    run.font.color.rgb = ACCENT
    return tb


def divider(slide, y=Inches(0.98)):
    rect = slide.shapes.add_shape(1, Inches(0.55), y, Inches(12.2), Inches(0.035))
    rect.fill.solid()
    rect.fill.fore_color.rgb = ACCENT
    rect.line.fill.background()


def textbox(slide, text: str, x, y, w, h, size=14, color=None, bold=False,
            italic=False, align=PP_ALIGN.LEFT, wrap=True):
    color = color or TEXT_C
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.color.rgb = color
    run.font.bold = bold
    run.font.italic = italic
    return tb


def bullets(slide, items, x, y, w, h, size=14, bullet_color=None):
    """items: list of str. Optional (label, body) tuples."""
    bullet_color = bullet_color or ACCENT
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    first = True
    for item in items:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.space_before = Pt(5)
        if isinstance(item, tuple):
            label, body = item
            r1 = p.add_run()
            r1.text = f"• {label}: "
            r1.font.size = Pt(size)
            r1.font.bold = True
            r1.font.color.rgb = bullet_color
            r2 = p.add_run()
            r2.text = body
            r2.font.size = Pt(size)
            r2.font.color.rgb = TEXT_C
        else:
            r = p.add_run()
            r.text = f"• {item}"
            r.font.size = Pt(size)
            r.font.color.rgb = TEXT_C


def panel(slide, x, y, w, h, border_color=None):
    border_color = border_color or ACCENT
    s = slide.shapes.add_shape(1, x, y, w, h)
    s.fill.solid()
    s.fill.fore_color.rgb = PANEL
    s.line.color.rgb = border_color
    s.line.width = Pt(1.2)
    return s


# ─────────────────────────────────────────────
# SLIDE 1 — Title
# ─────────────────────────────────────────────
def slide_title(prs):
    s = add_blank_slide(prs)

    textbox(s, "Autonomous 3D Printer Supply Chain",
            Inches(0.8), Inches(1.6), Inches(11.7), Inches(1.2),
            size=42, color=TITLE_C, bold=True, align=PP_ALIGN.CENTER)

    textbox(s, "Three independent agents managing a volatile market",
            Inches(0.8), Inches(2.9), Inches(11.7), Inches(0.6),
            size=20, color=MUTED, align=PP_ALIGN.CENTER, italic=True)

    roles = [("Provider", GREEN, Inches(1.0)),
             ("Manufacturer", ACCENT, Inches(5.1)),
             ("Retailer", RED,   Inches(9.2))]
    for name, col, x in roles:
        b = panel(s, x, Inches(3.85), Inches(3.0), Inches(0.85), col)
        tf = b.text_frame
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = name
        r.font.size = Pt(20)
        r.font.bold = True
        r.font.color.rgb = col

    textbox(s, "Demo scenario: holiday-rush",
            Inches(0.8), Inches(5.2), Inches(11.7), Inches(0.5),
            size=15, color=MUTED, align=PP_ALIGN.CENTER, italic=True)

    textbox(s, "DGSI · Week 8 · Autonomous Supply Chain",
            Inches(0.8), Inches(6.6), Inches(11.7), Inches(0.45),
            size=13, color=MUTED, align=PP_ALIGN.CENTER)


# ─────────────────────────────────────────────
# SLIDE 2 — System Overview
# ─────────────────────────────────────────────
def slide_overview(prs):
    s = add_blank_slide(prs)
    title_bar(s, "System Overview")
    divider(s)

    # Node boxes
    nodes = [
        ("Customers", Inches(0.35), Inches(3.0),  MUTED),
        ("Retailer\nPrinterWorld\n:8003", Inches(2.65), Inches(2.6), RED),
        ("Manufacturer\nFactory\n:8002",  Inches(5.35), Inches(2.6), ACCENT),
        ("Provider\nChipSupply Co\n:8001", Inches(8.05), Inches(2.6), GREEN),
    ]
    for label, x, y, col in nodes:
        b = panel(s, x, y, Inches(2.15), Inches(1.3), col)
        tf = b.text_frame
        tf.margin_left = Inches(0.08)
        tf.margin_top  = Inches(0.08)
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = label
        r.font.size = Pt(13)
        r.font.bold = True
        r.font.color.rgb = col

    # Arrow labels between nodes
    arrows = [
        ("orders →",   Inches(2.1),  Inches(3.1)),
        ("POs →",      Inches(4.8),  Inches(3.1)),
        ("orders →",   Inches(7.5),  Inches(3.1)),
    ]
    for txt, x, y in arrows:
        textbox(s, txt, x, y, Inches(0.8), Inches(0.4),
                size=11, color=MUTED, align=PP_ALIGN.CENTER)

    # Return arrows (deliveries)
    ret_arrows = [
        ("← printers",  Inches(4.8),  Inches(4.1)),
        ("← parts",     Inches(7.5),  Inches(4.1)),
    ]
    for txt, x, y in ret_arrows:
        textbox(s, txt, x, y, Inches(0.9), Inches(0.35),
                size=11, color=MUTED, align=PP_ALIGN.CENTER)

    # Turn engine
    b2 = panel(s, Inches(4.3), Inches(5.2), Inches(4.5), Inches(0.85), YELLOW)
    tf = b2.text_frame
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = "Turn Engine · scripts/run_simulation.py"
    r.font.size = Pt(13)
    r.font.bold = True
    r.font.color.rgb = YELLOW

    # Scenario signals box
    b3 = panel(s, Inches(0.35), Inches(5.2), Inches(3.4), Inches(0.85), MUTED)
    tf = b3.text_frame
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = "Scenario signals\ndemand · supply · lead time"
    r.font.size = Pt(12)
    r.font.color.rgb = MUTED

    textbox(s,
            "Each app owns its own SQLite DB and exposes REST endpoints. "
            "The engine advances time, injects demand, and orchestrates all services in lock-step.",
            Inches(0.55), Inches(6.3), Inches(12.2), Inches(0.8),
            size=13, color=MUTED, italic=True)


# ─────────────────────────────────────────────
# SLIDE 3 — Turn Design
# ─────────────────────────────────────────────
def slide_turn(prs):
    s = add_blank_slide(prs)
    title_bar(s, "Turn Design — One Simulated Day")
    divider(s)

    steps = [
        "Read scenario signal for the day",
        "Inject customer demand into the retailer",
        "Provider reacts to stock pressure and supply conditions",
        "Manufacturer releases orders, buys parts, adjusts wholesale prices",
        "Retailer processes customers and buys printers",
        "All three apps advance one day",
        "Narrative log and metrics are saved",
    ]

    tb = s.shapes.add_textbox(Inches(0.55), Inches(1.15), Inches(7.5), Inches(5.8))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, step in enumerate(steps):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_before = Pt(8)
        r1 = p.add_run()
        r1.text = f"  {i + 1}.  "
        r1.font.size = Pt(16)
        r1.font.bold = True
        r1.font.color.rgb = ACCENT
        r2 = p.add_run()
        r2.text = step
        r2.font.size = Pt(16)
        r2.font.color.rgb = TEXT_C

    b = panel(s, Inches(8.4), Inches(1.15), Inches(4.4), Inches(4.2), ACCENT)
    tf = b.text_frame
    tf.word_wrap = True
    tf.margin_left  = Inches(0.18)
    tf.margin_right = Inches(0.18)
    tf.margin_top   = Inches(0.12)
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = "Why this order?"
    r.font.size = Pt(16)
    r.font.bold = True
    r.font.color.rgb = ACCENT
    p2 = tf.add_paragraph()
    p2.space_before = Pt(10)
    r2 = p2.add_run()
    r2.text = (
        "The upstream provider acts before the manufacturer places new "
        "pressure, then the manufacturer reacts to retail demand, and the "
        "retailer closes the loop with customers.\n\n"
        "This order avoids stale-read race conditions between agents."
    )
    r2.font.size = Pt(14)
    r2.font.color.rgb = TEXT_C


# ─────────────────────────────────────────────
# SLIDE 4 — Provider
# ─────────────────────────────────────────────
def _agent_slide(prs, title: str, port: str, tag_color, subtitle: str,
                 col1_label, col1_items,
                 col2_label, col2_items,
                 col3_label, col3_items, col3_color=None):
    col3_color = col3_color or YELLOW
    s = add_blank_slide(prs)
    title_bar(s, title)
    divider(s)

    textbox(s, f"{port}", Inches(0.55), Inches(1.05), Inches(4), Inches(0.35),
            size=13, color=tag_color, bold=True)
    textbox(s, subtitle, Inches(0.55), Inches(1.42), Inches(12.2), Inches(0.5),
            size=15, color=TEXT_C, italic=True)

    col_x = [Inches(0.55), Inches(4.7), Inches(8.85)]
    col_w = Inches(3.9)
    col_colors = [GREEN, ACCENT, col3_color]
    col_labels = [col1_label, col2_label, col3_label]
    col_items_all = [col1_items, col2_items, col3_items]

    for x, col, lbl, items in zip(col_x, col_colors, col_labels, col_items_all):
        textbox(s, lbl, x, Inches(2.05), col_w, Inches(0.42),
                size=15, color=col, bold=True)
        tb = s.shapes.add_textbox(x, Inches(2.5), col_w, Inches(4.6))
        tf = tb.text_frame
        tf.word_wrap = True
        for i, item in enumerate(items):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.space_before = Pt(6)
            r = p.add_run()
            r.text = f"• {item}"
            r.font.size = Pt(14)
            r.font.color.rgb = TEXT_C
    return s


def slide_provider(prs):
    _agent_slide(
        prs,
        title="Agent Design: Provider",
        port="ChipSupply Co · :8001",
        tag_color=GREEN,
        subtitle="Keep parts available while adjusting prices under supply pressure.",
        col1_label="Inputs",
        col1_items=[
            "Current stock vs starting stock",
            "Open manufacturer orders",
            "Product price tiers",
            "Market signal: supply_modifier,\nlead_time_modifier, demand_modifier",
        ],
        col2_label="Actions",
        col2_items=[
            "Restock products below threshold",
            "Raise prices during supply shortage",
            "Avoid stockouts on critical parts when possible",
        ],
        col3_label="Design choice",
        col3_items=[
            "Prompt now provides RESTOCK\nflags and ready-to-run action hints",
            "Agent skips catalog/stock analysis",
            "Faster decisions, fewer wasted\nreasoning turns",
        ],
        col3_color=YELLOW,
    )


def slide_manufacturer(prs):
    _agent_slide(
        prs,
        title="Agent Design: Manufacturer",
        port="Factory · :8002",
        tag_color=ACCENT,
        subtitle="Convert retail purchase orders into finished printers.",
        col1_label="Inputs",
        col1_items=[
            "Retail sales orders",
            "Raw-parts stock",
            "Finished-printer stock",
            "Supplier catalog",
            "Open part purchase orders",
            "BOM per printer model",
        ],
        col2_label="Actions",
        col2_items=[
            "Release pending sales orders\nto production",
            "Order missing parts from provider",
            "Raise wholesale prices when\nutilisation/backlog is high",
        ],
        col3_label="Important fix",
        col3_items=[
            "Buys against backlog + buffer,\nnot only tiny shortages",
            "Avoids counting in_progress orders\nas new demand (BOM consumed)",
        ],
        col3_color=RED,
    )


def slide_retailer(prs):
    _agent_slide(
        prs,
        title="Agent Design: Retailer",
        port="PrinterWorld · :8003",
        tag_color=RED,
        subtitle="Serve customer demand and decide how many printers to buy.",
        col1_label="Inputs",
        col1_items=[
            "Customer orders",
            "Retail stock",
            "Open purchases from manufacturer",
            "Wholesale prices",
            "Demand and price-sensitivity signals",
        ],
        col2_label="Actions",
        col2_items=[
            "Process every pending customer order",
            "Backorder when stock unavailable",
            "Purchase enough printers to cover\nbacklog + demand buffer",
            "Raise retail prices under stock pressure",
        ],
        col3_label="Implementation note",
        col3_items=[
            "Made deterministic/direct for the\nlong run",
            "LLM version hit max turns too often",
            "Keeps simulation stable and auditable",
        ],
        col3_color=YELLOW,
    )


# ─────────────────────────────────────────────
# SLIDE 7 — Scenario: Holiday Rush
# ─────────────────────────────────────────────
def slide_scenario(prs):
    s = add_blank_slide(prs)
    title_bar(s, "Scenario: Holiday Rush")
    divider(s)

    phases = [
        ("Days 1–7",   "Pre-holiday normal", "Demand ×1.0 | Supply ×1.0 | Lead time ×1.0 — build buffer stock", GREEN),
        ("Days 8–12",  "Black Friday",        "Demand ×3.0 | Supply ×1.0 | High price sensitivity",              ACCENT),
        ("Days 13–20", "Chip shortage",       "Demand ×1.5 | Supply ×0.4 | Lead time ×2.0 — constrained upstream", YELLOW),
        ("Days 18–25", "Christmas rush",      "Demand ×2.5 | Supply ×0.6 | Lead time ×1.5 — overlaps shortage",  RED),
    ]

    for i, (days, name, desc, col) in enumerate(phases):
        y = Inches(1.2 + i * 1.18)
        b = panel(s, Inches(0.55), y, Inches(12.2), Inches(1.05), col)
        tf = b.text_frame
        tf.margin_left = Inches(0.15)
        tf.margin_top  = Inches(0.12)
        p = tf.paragraphs[0]
        r1 = p.add_run()
        r1.text = f"{days}  "
        r1.font.size = Pt(14)
        r1.font.bold = True
        r1.font.color.rgb = col
        r2 = p.add_run()
        r2.text = f"{name}  —  "
        r2.font.size = Pt(15)
        r2.font.bold = True
        r2.font.color.rgb = TITLE_C
        r3 = p.add_run()
        r3.text = desc
        r3.font.size = Pt(13)
        r3.font.color.rgb = TEXT_C

    textbox(s,
            "⚠  Days 18–20: Chip shortage + Christmas rush overlap — strongest stress test. Modifiers multiply.",
            Inches(0.55), Inches(6.05), Inches(12.2), Inches(0.7),
            size=14, color=RED, bold=True)


# ─────────────────────────────────────────────
# SLIDE 8 — Observations + Dashboard chart
# ─────────────────────────────────────────────
def slide_observations(prs):
    s = add_blank_slide(prs)
    title_bar(s, "Holiday Rush — Run Observations")
    divider(s)

    obs = [
        "Retailer stock reaches zero early and stays under pressure",
        "Backorders grow rapidly during Black Friday",
        "Manufacturer backlog high but causally reasonable",
        "Manufacturer places much larger part orders once demand spikes",
        "Provider repeatedly restocks kit_piezas back to its initial level (~120 units)",
        "Prices increase across the chain:",
        "  → Provider raises kit_piezas unit price",
        "  → Provider issues price raise-all during chip shortage",
        "  → Manufacturer raises wholesale price under high utilisation",
    ]

    tb = s.shapes.add_textbox(Inches(0.55), Inches(1.15), Inches(6.5), Inches(5.8))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, line in enumerate(obs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_before = Pt(5)
        r = p.add_run()
        if line.startswith("  →"):
            r.text = line
            r.font.size = Pt(13)
            r.font.color.rgb = MUTED
        else:
            r.text = f"• {line}"
            r.font.size = Pt(14)
            r.font.color.rgb = TEXT_C

    img_path = os.path.join(REPORTS_DIR, "holiday-rush_dashboard.png")
    if os.path.exists(img_path):
        s.shapes.add_picture(img_path, Inches(7.25), Inches(1.15), Inches(5.6), Inches(5.8))
    else:
        textbox(s, "[holiday-rush_dashboard.png not found]",
                Inches(7.25), Inches(3.5), Inches(5.6), Inches(0.5),
                size=13, color=RED)


# ─────────────────────────────────────────────
# SLIDE 9 — Emergent Behaviour
# ─────────────────────────────────────────────
def slide_emergent(prs):
    s = add_blank_slide(prs)
    title_bar(s, "Emergent Behaviour — Bullwhip Effect")
    divider(s)

    chain = [
        ("Customer spike",  "creates retailer backorders",                     RED),
        ("Retailer",        "places larger printer orders",                    ACCENT),
        ("Manufacturer",    "creates even larger part orders (BOM expansion)", YELLOW),
        ("Provider",        "stock depleted and restocked repeatedly",         GREEN),
    ]

    tb = s.shapes.add_textbox(Inches(0.55), Inches(1.15), Inches(7.0), Inches(3.2))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, (actor, action, col) in enumerate(chain):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_before = Pt(10)
        r1 = p.add_run()
        r1.text = f"▶ {actor}: "
        r1.font.size = Pt(16)
        r1.font.bold = True
        r1.font.color.rgb = col
        r2 = p.add_run()
        r2.text = action
        r2.font.size = Pt(15)
        r2.font.color.rgb = TEXT_C

    textbox(s, "Unexpected behaviours",
            Inches(0.55), Inches(4.5), Inches(7.0), Inches(0.42),
            size=15, color=ACCENT, bold=True)

    unexpected = [
        "kit_piezas keeps returning to ~120 — that is the provider's restock target",
        "Part orders rejected when provider stock < requested quantity",
        "Chained CLI commands stop after one rejection — later purchases left unexecuted",
    ]
    bullets(s, unexpected, Inches(0.55), Inches(5.0), Inches(7.0), Inches(2.0), size=13)

    b = panel(s, Inches(8.1), Inches(1.15), Inches(4.7), Inches(5.8), GREEN)
    tf = b.text_frame
    tf.word_wrap = True
    tf.margin_left  = Inches(0.2)
    tf.margin_right = Inches(0.2)
    tf.margin_top   = Inches(0.15)
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = "Why it matters"
    r.font.size = Pt(16)
    r.font.bold = True
    r.font.color.rgb = GREEN
    p2 = tf.add_paragraph()
    p2.space_before = Pt(12)
    r2 = p2.add_run()
    r2.text = (
        "These are features, not bugs.\n\n"
        "Emergence is what makes this project interesting — simple local rules "
        "interact to produce behaviour that no single agent was programmed for.\n\n"
        "The bullwhip effect was named in the 1960s. We reproduced it "
        "accidentally. That is exactly the point."
    )
    r2.font.size = Pt(14)
    r2.font.color.rgb = TEXT_C


# ─────────────────────────────────────────────
# SLIDE 10 — Demo + Reflection
# ─────────────────────────────────────────────
def slide_demo_reflection(prs):
    s = add_blank_slide(prs)
    title_bar(s, "Live Demo + Reflection")
    divider(s)

    # Demo plan
    textbox(s, "Live Demo Plan", Inches(0.55), Inches(1.15), Inches(6.0), Inches(0.42),
            size=15, color=ACCENT, bold=True)

    demo_steps = [
        "Reset the system",
        "Run 2–3 days of holiday-rush",
        "Show the narrative log updating",
        "Point out one decision per agent",
        "Show one chart from the completed 25-day run",
    ]
    tb = s.shapes.add_textbox(Inches(0.55), Inches(1.62), Inches(6.0), Inches(2.8))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, step in enumerate(demo_steps):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_before = Pt(7)
        r1 = p.add_run()
        r1.text = f"  {i + 1}.  "
        r1.font.size = Pt(15)
        r1.font.bold = True
        r1.font.color.rgb = ACCENT
        r2 = p.add_run()
        r2.text = step
        r2.font.size = Pt(15)
        r2.font.color.rgb = TEXT_C

    textbox(s,
            "Backup: if agents stall, use logs/narrative_holiday-rush.md and the saved charts.",
            Inches(0.55), Inches(4.65), Inches(6.0), Inches(0.7),
            size=13, color=MUTED, italic=True)

    # Reflection
    textbox(s, "Reflection", Inches(7.1), Inches(1.15), Inches(5.7), Inches(0.42),
            size=15, color=YELLOW, bold=True)

    reflections = [
        "Clear local prompts matter more than long prompts",
        "Pre-fetching state reduced wasted reasoning turns",
        "LLMs are useful for strategy; deterministic execution is better for repetitive low-level loops",
        "Hardest part: observability — without logs, emergent behaviour is impossible to explain",
    ]
    bullets(s, reflections, Inches(7.1), Inches(1.62), Inches(5.7), Inches(3.6),
            size=14, bullet_color=YELLOW)

    textbox(s,
            '"Deterministic software handles execution. LLMs handle strategy. '
            'Well-defined interfaces keep everything auditable and under control."',
            Inches(0.55), Inches(6.4), Inches(12.2), Inches(0.7),
            size=14, color=MUTED, italic=True, align=PP_ALIGN.CENTER)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    prs = new_prs()
    slide_title(prs)
    slide_overview(prs)
    slide_turn(prs)
    slide_provider(prs)
    slide_manufacturer(prs)
    slide_retailer(prs)
    slide_scenario(prs)
    slide_observations(prs)
    slide_emergent(prs)
    slide_demo_reflection(prs)
    prs.save(OUTPUT_PATH)
    print(f"Saved: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

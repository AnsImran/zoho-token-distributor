"""Generate PNG architecture diagrams for the README.

Run:  python docs/generate_diagrams.py
Outputs: docs/architecture.png, docs/request_flow.png, docs/ci_cd_pipeline.png
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import os

DOCS_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Color palette ──────────────────────────────────────────────────────────
C_BG       = "#FFFFFF"
C_PRIMARY  = "#1A73E8"   # blue - main service
C_SECONDARY= "#34A853"   # green - success/healthy
C_ACCENT   = "#EA4335"   # red - failure
C_NEUTRAL  = "#5F6368"   # gray - borders/text
C_LIGHT_BG = "#E8F0FE"   # light blue - service bg
C_ZOHO_BG  = "#FFF3E0"   # light orange - zoho
C_CONSUMER = "#E8F5E9"   # light green - consumers
C_CACHE_BG = "#F3E5F5"   # light purple - cache
C_WARN     = "#FB8C00"   # orange - warning/degraded
C_DARK     = "#202124"   # near black - text


def _rounded_box(ax, x, y, w, h, text, facecolor, edgecolor=C_NEUTRAL,
                 fontsize=10, fontweight="normal", textcolor=C_DARK, lw=1.5,
                 subtext=None, subtextsize=8):
    """Draw a rounded rectangle with centered text."""
    box = FancyBboxPatch((x - w/2, y - h/2), w, h,
                         boxstyle="round,pad=0.12", linewidth=lw,
                         edgecolor=edgecolor, facecolor=facecolor,
                         zorder=2)
    ax.add_patch(box)
    ty = y + 0.06 if subtext else y
    ax.text(x, ty, text, ha="center", va="center",
            fontsize=fontsize, fontweight=fontweight, color=textcolor, zorder=3)
    if subtext:
        ax.text(x, y - 0.12, subtext, ha="center", va="center",
                fontsize=subtextsize, color=C_NEUTRAL, zorder=3, style="italic")
    return box


def _arrow(ax, x1, y1, x2, y2, color=C_NEUTRAL, lw=1.5, style="-|>",
           connectionstyle="arc3,rad=0", label=None, label_fontsize=8):
    """Draw an arrow between two points."""
    arrow = FancyArrowPatch((x1, y1), (x2, y2),
                            arrowstyle=style, lw=lw, color=color,
                            connectionstyle=connectionstyle,
                            mutation_scale=15, zorder=4)
    ax.add_patch(arrow)
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mx + 0.05, my, label, fontsize=label_fontsize,
                color=color, ha="left", va="center", zorder=5,
                bbox=dict(boxstyle="round,pad=0.15", facecolor=C_BG,
                          edgecolor="none", alpha=0.85))


# ══════════════════════════════════════════════════════════════════════════
# Diagram 1 — Architecture
# ══════════════════════════════════════════════════════════════════════════

def generate_architecture():
    fig, ax = plt.subplots(1, 1, figsize=(10, 8))
    ax.set_xlim(-0.5, 5.5)
    ax.set_ylim(-0.5, 7.5)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor(C_BG)

    # ── Title ──
    ax.text(2.75, 7.1, "Zoho Token Service — Architecture",
            ha="center", va="center", fontsize=16, fontweight="bold",
            color=C_DARK)

    # ── Zoho API (top) ──
    _rounded_box(ax, 2.75, 6.2, 2.8, 0.6, "Zoho OAuth API",
                 facecolor=C_ZOHO_BG, edgecolor=C_WARN, fontsize=12,
                 fontweight="bold", subtext="accounts.zoho.com/oauth/v2/token",
                 subtextsize=8)

    # ── Arrow: Zoho -> Service ──
    _arrow(ax, 2.75, 5.88, 2.75, 5.15, color=C_PRIMARY, lw=2,
           label="POST (refresh_token)")

    # ── Main service box (large container) ──
    service_box = FancyBboxPatch((0.3, 2.3), 4.9, 2.8,
                                 boxstyle="round,pad=0.15", linewidth=2.5,
                                 edgecolor=C_PRIMARY, facecolor=C_LIGHT_BG,
                                 zorder=1, linestyle="-")
    ax.add_patch(service_box)
    ax.text(2.75, 4.85, "Zoho Token Service", ha="center", va="center",
            fontsize=13, fontweight="bold", color=C_PRIMARY, zorder=3)
    ax.text(2.75, 4.6, "FastAPI  |  Single Worker  |  asyncio", ha="center",
            va="center", fontsize=8, color=C_NEUTRAL, zorder=3, style="italic")

    # ── Background Loop (inside service) ──
    _rounded_box(ax, 1.5, 3.7, 1.8, 0.8, "Background\nRefresh Loop",
                 facecolor="#FFFFFF", edgecolor=C_SECONDARY, fontsize=10,
                 fontweight="bold", lw=1.5)
    ax.text(1.5, 3.2, "Proactive refresh\n2 min before expiry\nExp. backoff on failure",
            ha="center", va="center", fontsize=7, color=C_NEUTRAL,
            zorder=3, style="italic")

    # ── Cache (inside service) ──
    _rounded_box(ax, 4.0, 3.7, 1.5, 0.8, "In-Memory\nToken Cache",
                 facecolor=C_CACHE_BG, edgecolor="#9C27B0", fontsize=10,
                 fontweight="bold", lw=1.5)
    ax.text(4.0, 3.2, "Atomic dict swap\nSingle slot",
            ha="center", va="center", fontsize=7, color=C_NEUTRAL,
            zorder=3, style="italic")

    # Arrow: loop -> cache
    _arrow(ax, 2.45, 3.7, 3.2, 3.7, color=C_SECONDARY, lw=1.5, label="replace")

    # ── Middleware bar ──
    _rounded_box(ax, 2.75, 2.6, 3.2, 0.35, "Middleware: Request Logging  |  X-Request-ID  |  Error Handler",
                 facecolor="#FFFFFF", edgecolor=C_NEUTRAL, fontsize=7.5,
                 fontweight="normal", lw=1)

    # ── Arrow: Service -> Consumers ──
    _arrow(ax, 1.5, 2.28, 1.0, 1.3, color=C_PRIMARY, lw=2)
    _arrow(ax, 2.75, 2.28, 2.75, 1.3, color=C_PRIMARY, lw=2)
    _arrow(ax, 4.0, 2.28, 4.5, 1.3, color=C_PRIMARY, lw=2)

    ax.text(2.75, 1.75, "GET /v1/token", ha="center", va="center",
            fontsize=9, color=C_PRIMARY, fontweight="bold", zorder=5,
            bbox=dict(boxstyle="round,pad=0.15", facecolor=C_BG,
                      edgecolor="none", alpha=0.85))

    # ── Consumer services (bottom) ──
    _rounded_box(ax, 1.0, 0.9, 1.3, 0.55, "Service A",
                 facecolor=C_CONSUMER, edgecolor=C_SECONDARY, fontsize=10,
                 fontweight="bold", subtext="consumer", subtextsize=7)
    _rounded_box(ax, 2.75, 0.9, 1.3, 0.55, "Service B",
                 facecolor=C_CONSUMER, edgecolor=C_SECONDARY, fontsize=10,
                 fontweight="bold", subtext="consumer", subtextsize=7)
    _rounded_box(ax, 4.5, 0.9, 1.3, 0.55, "Service C",
                 facecolor=C_CONSUMER, edgecolor=C_SECONDARY, fontsize=10,
                 fontweight="bold", subtext="consumer", subtextsize=7)

    # ── Network boundary note ──
    ax.text(2.75, 0.2, "localhost:8000  (host-only, not exposed to internet)",
            ha="center", va="center", fontsize=8, color=C_NEUTRAL,
            style="italic", zorder=3,
            bbox=dict(boxstyle="round,pad=0.2", facecolor="#FFF9C4",
                      edgecolor="#FDD835", alpha=0.9))

    fig.tight_layout(pad=0.5)
    fig.savefig(os.path.join(DOCS_DIR, "architecture.png"), dpi=180,
                bbox_inches="tight", facecolor=C_BG)
    plt.close(fig)
    print("  OK: architecture.png")


# ══════════════════════════════════════════════════════════════════════════
# Diagram 2 — Request Flow / Lifecycle
# ══════════════════════════════════════════════════════════════════════════

def generate_request_flow():
    fig, ax = plt.subplots(1, 1, figsize=(12, 6.5))
    ax.set_xlim(-0.3, 11.5)
    ax.set_ylim(-0.3, 5.5)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor(C_BG)

    ax.text(5.6, 5.1, "Token Lifecycle — Startup, Refresh & Recovery",
            ha="center", va="center", fontsize=15, fontweight="bold", color=C_DARK)

    # ── Column 1: Startup ──
    ax.text(1.5, 4.5, "STARTUP", ha="center", va="center",
            fontsize=11, fontweight="bold", color=C_PRIMARY)

    _rounded_box(ax, 1.5, 3.7, 2.0, 0.5, "Validate Config",
                 facecolor=C_LIGHT_BG, edgecolor=C_PRIMARY, fontsize=9,
                 fontweight="bold", subtext="Pydantic Settings", subtextsize=7)
    _arrow(ax, 1.5, 3.43, 1.5, 3.0, color=C_PRIMARY, lw=1.5)

    _rounded_box(ax, 1.5, 2.65, 2.0, 0.5, "Fetch Initial Token",
                 facecolor=C_LIGHT_BG, edgecolor=C_PRIMARY, fontsize=9,
                 fontweight="bold", subtext="POST to Zoho OAuth", subtextsize=7)
    _arrow(ax, 1.5, 2.38, 1.5, 1.95, color=C_PRIMARY, lw=1.5)

    _rounded_box(ax, 1.5, 1.6, 2.0, 0.5, "Launch Background Loop",
                 facecolor=C_LIGHT_BG, edgecolor=C_PRIMARY, fontsize=9,
                 fontweight="bold", subtext="asyncio.create_task()", subtextsize=7)
    _arrow(ax, 1.5, 1.33, 1.5, 0.9, color=C_PRIMARY, lw=1.5)

    _rounded_box(ax, 1.5, 0.55, 2.0, 0.5, "Ready to Serve",
                 facecolor=C_CONSUMER, edgecolor=C_SECONDARY, fontsize=9,
                 fontweight="bold")

    # Failure branch from "Fetch Initial Token"
    _arrow(ax, 2.55, 2.65, 3.4, 2.65, color=C_ACCENT, lw=1.2,
           label="fail?", label_fontsize=7)
    ax.text(3.95, 2.65, "Log & continue\n(retry in loop)",
            ha="center", va="center", fontsize=7, color=C_ACCENT,
            bbox=dict(boxstyle="round,pad=0.15", facecolor="#FFEBEE",
                      edgecolor=C_ACCENT, alpha=0.9), zorder=5)

    # ── Column 2: Steady State ──
    ax.text(5.8, 4.5, "STEADY STATE", ha="center", va="center",
            fontsize=11, fontweight="bold", color=C_SECONDARY)

    _rounded_box(ax, 5.8, 3.7, 2.2, 0.5, "Sleep Until Near-Expiry",
                 facecolor="#FFFFFF", edgecolor=C_SECONDARY, fontsize=9,
                 fontweight="bold", subtext="(lifetime - 120s)", subtextsize=7)
    _arrow(ax, 5.8, 3.43, 5.8, 3.0, color=C_SECONDARY, lw=1.5)

    _rounded_box(ax, 5.8, 2.65, 2.2, 0.5, "Fetch Fresh Token",
                 facecolor="#FFFFFF", edgecolor=C_SECONDARY, fontsize=9,
                 fontweight="bold", subtext="POST to Zoho OAuth", subtextsize=7)
    _arrow(ax, 5.8, 2.38, 5.8, 1.95, color=C_SECONDARY, lw=1.5)

    _rounded_box(ax, 5.8, 1.6, 2.2, 0.5, "Replace Cache",
                 facecolor="#FFFFFF", edgecolor=C_SECONDARY, fontsize=9,
                 fontweight="bold", subtext="atomic dict swap", subtextsize=7)

    # Loop arrow back
    _arrow(ax, 4.65, 1.6, 4.65, 3.7, color=C_SECONDARY, lw=1.2,
           style="-|>", connectionstyle="arc3,rad=-0.4", label="loop")

    # ── Column 3: Failure Recovery ──
    ax.text(9.6, 4.5, "FAILURE RECOVERY", ha="center", va="center",
            fontsize=11, fontweight="bold", color=C_ACCENT)

    _rounded_box(ax, 9.6, 3.7, 2.2, 0.5, "Refresh Fails",
                 facecolor="#FFEBEE", edgecolor=C_ACCENT, fontsize=9,
                 fontweight="bold", subtext="Zoho down / network error", subtextsize=7)
    _arrow(ax, 9.6, 3.43, 9.6, 3.0, color=C_ACCENT, lw=1.5)

    _rounded_box(ax, 9.6, 2.65, 2.2, 0.5, "Exponential Backoff",
                 facecolor="#FFEBEE", edgecolor=C_ACCENT, fontsize=9,
                 fontweight="bold", subtext="2s, 4s, 8s ... 120s + jitter", subtextsize=7)
    _arrow(ax, 9.6, 2.38, 9.6, 1.95, color=C_ACCENT, lw=1.5)

    _rounded_box(ax, 9.6, 1.6, 2.2, 0.5, "Serve Stale Token",
                 facecolor="#FFF3E0", edgecolor=C_WARN, fontsize=9,
                 fontweight="bold", subtext='is_stale: true', subtextsize=7)

    # Retry arrow back
    _arrow(ax, 8.45, 2.65, 8.45, 3.7, color=C_ACCENT, lw=1.2,
           style="-|>", connectionstyle="arc3,rad=-0.4", label="retry")

    # ── Connecting arrows between columns ──
    _arrow(ax, 6.95, 2.65, 8.45, 3.43, color=C_ACCENT, lw=1.2,
           connectionstyle="arc3,rad=0.15", label="fail", label_fontsize=7)

    fig.tight_layout(pad=0.5)
    fig.savefig(os.path.join(DOCS_DIR, "request_flow.png"), dpi=180,
                bbox_inches="tight", facecolor=C_BG)
    plt.close(fig)
    print("  OK: request_flow.png")


# ══════════════════════════════════════════════════════════════════════════
# Diagram 3 — CI/CD Pipeline
# ══════════════════════════════════════════════════════════════════════════

def generate_ci_cd():
    fig, ax = plt.subplots(1, 1, figsize=(11, 5))
    ax.set_xlim(-0.5, 10.5)
    ax.set_ylim(-0.3, 4.5)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor(C_BG)

    ax.text(5.0, 4.1, "CI/CD Pipeline — GitHub Actions",
            ha="center", va="center", fontsize=15, fontweight="bold", color=C_DARK)

    # ── Trigger ──
    _rounded_box(ax, 0.8, 3.0, 1.4, 0.7, "Push / PR",
                 facecolor="#E3F2FD", edgecolor=C_PRIMARY, fontsize=11,
                 fontweight="bold", subtext="to main or dev", subtextsize=8)

    # ── Parallel jobs (fan out) ──
    _arrow(ax, 1.55, 3.2, 3.0, 3.6, color=C_PRIMARY, lw=2)
    _arrow(ax, 1.55, 3.0, 3.0, 3.0, color=C_PRIMARY, lw=2)
    _arrow(ax, 1.55, 2.8, 3.0, 2.4, color=C_PRIMARY, lw=2)

    # Lint job
    _rounded_box(ax, 3.9, 3.6, 1.6, 0.55, "Lint & Type Check",
                 facecolor=C_LIGHT_BG, edgecolor=C_PRIMARY, fontsize=9,
                 fontweight="bold", subtext="ruff, mypy", subtextsize=7)

    # Test job
    _rounded_box(ax, 3.9, 3.0, 1.6, 0.55, "Test",
                 facecolor=C_LIGHT_BG, edgecolor=C_PRIMARY, fontsize=9,
                 fontweight="bold", subtext="pytest, 80% coverage", subtextsize=7)

    # Audit job
    _rounded_box(ax, 3.9, 2.4, 1.6, 0.55, "Dependency Audit",
                 facecolor=C_LIGHT_BG, edgecolor=C_PRIMARY, fontsize=9,
                 fontweight="bold", subtext="pip-audit", subtextsize=7)

    # ── Fan in to gate ──
    _arrow(ax, 4.75, 3.6, 5.8, 3.2, color=C_SECONDARY, lw=2)
    _arrow(ax, 4.75, 3.0, 5.8, 3.0, color=C_SECONDARY, lw=2)
    _arrow(ax, 4.75, 2.4, 5.8, 2.8, color=C_SECONDARY, lw=2)

    # Gate
    _rounded_box(ax, 6.5, 3.0, 1.2, 0.7, "All Pass?",
                 facecolor="#FFF9C4", edgecolor="#FDD835", fontsize=10,
                 fontweight="bold", lw=2)

    # ── Deploy ──
    _arrow(ax, 7.15, 3.0, 8.0, 3.0, color=C_SECONDARY, lw=2,
           label="yes", label_fontsize=8)

    _rounded_box(ax, 8.9, 3.0, 1.6, 0.7, "Deploy",
                 facecolor=C_CONSUMER, edgecolor=C_SECONDARY, fontsize=11,
                 fontweight="bold", subtext="push to main only", subtextsize=8, lw=2)

    # ── Deploy steps (below) ──
    deploy_steps = [
        ("SSH into server", 2.7, 1.2),
        ("git pull", 4.2, 1.2),
        ("docker compose\nup --build", 5.7, 1.2),
        ("Health check\n(wait 60s)", 7.2, 1.2),
        ("Live", 8.5, 1.2),
    ]

    _arrow(ax, 8.9, 2.62, 8.9, 2.1, color=C_SECONDARY, lw=1.5)
    ax.text(8.9, 2.2, "Deploy Steps", ha="center", va="center", fontsize=8,
            fontweight="bold", color=C_NEUTRAL)

    prev_x = None
    for label, x, y in deploy_steps:
        color = C_CONSUMER if label == "Live" else "#FFFFFF"
        edge = C_SECONDARY if label == "Live" else C_NEUTRAL
        fw = "bold" if label == "Live" else "normal"
        _rounded_box(ax, x, y, 1.2, 0.5, label,
                     facecolor=color, edgecolor=edge, fontsize=8,
                     fontweight=fw, lw=1)
        if prev_x is not None:
            _arrow(ax, prev_x + 0.65, y, x - 0.65, y, color=C_NEUTRAL, lw=1)
        prev_x = x

    # ── Fail branch ──
    _arrow(ax, 6.5, 2.62, 6.5, 2.1, color=C_ACCENT, lw=1.5)
    _rounded_box(ax, 6.5, 1.7, 1.0, 0.45, "Block",
                 facecolor="#FFEBEE", edgecolor=C_ACCENT, fontsize=9,
                 fontweight="bold")
    ax.text(6.5, 1.35, "no deploy", ha="center", va="center",
            fontsize=7, color=C_ACCENT, style="italic")

    fig.tight_layout(pad=0.5)
    fig.savefig(os.path.join(DOCS_DIR, "ci_cd_pipeline.png"), dpi=180,
                bbox_inches="tight", facecolor=C_BG)
    plt.close(fig)
    print("  OK: ci_cd_pipeline.png")


if __name__ == "__main__":
    print("Generating diagrams...")
    generate_architecture()
    generate_request_flow()
    generate_ci_cd()
    print("Done.")

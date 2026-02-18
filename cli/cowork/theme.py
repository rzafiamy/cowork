"""
🎨 Cowork CLI Theme & Visual Identity
All Rich markup, color tokens, and ASCII art live here.
"""

from rich.theme import Theme
from rich.style import Style

# ─── Color Palette ────────────────────────────────────────────────────────────
PALETTE = {
    "primary":    "#7C3AED",   # violet-600
    "secondary":  "#06B6D4",   # cyan-500
    "accent":     "#F59E0B",   # amber-500
    "success":    "#10B981",   # emerald-500
    "warning":    "#F97316",   # orange-500
    "error":      "#EF4444",   # red-500
    "muted":      "#6B7280",   # gray-500
    "surface":    "#1E1B4B",   # indigo-950
    "text":       "#E2E8F0",   # slate-200
    "highlight":  "#818CF8",   # indigo-400
    "tool":       "#34D399",   # emerald-400
    "memory":     "#F472B6",   # pink-400
    "router":     "#60A5FA",   # blue-400
    "compress":   "#A78BFA",   # violet-400
    "gateway":    "#FBBF24",   # amber-400
    "sentinel":   "#FB923C",   # orange-400
}

COWORK_THEME = Theme({
    "primary":    Style(color=PALETTE["primary"], bold=True),
    "secondary":  Style(color=PALETTE["secondary"]),
    "accent":     Style(color=PALETTE["accent"], bold=True),
    "success":    Style(color=PALETTE["success"], bold=True),
    "warning":    Style(color=PALETTE["warning"]),
    "error":      Style(color=PALETTE["error"], bold=True),
    "muted":      Style(color=PALETTE["muted"]),
    "surface":    Style(bgcolor=PALETTE["surface"]),
    "text":       Style(color=PALETTE["text"]),
    "highlight":  Style(color=PALETTE["highlight"], bold=True),
    "tool":       Style(color=PALETTE["tool"], bold=True),
    "memory":     Style(color=PALETTE["memory"]),
    "router":     Style(color=PALETTE["router"]),
    "compress":   Style(color=PALETTE["compress"]),
    "gateway":    Style(color=PALETTE["gateway"]),
    "sentinel":   Style(color=PALETTE["sentinel"]),
    # Semantic aliases
    "phase1":     Style(color="#22D3EE", bold=True),   # cyan
    "phase2":     Style(color="#818CF8", bold=True),   # indigo
    "phase3":     Style(color="#A78BFA", bold=True),   # violet
    "phase4":     Style(color="#F472B6", bold=True),   # pink
    "phase5":     Style(color="#34D399", bold=True),   # emerald
    "dim_text":   Style(color="#4B5563"),
    "bold_white": Style(color="white", bold=True),
    "italic_muted": Style(color="#6B7280", italic=True),
})

# ─── ASCII Art / Banner ───────────────────────────────────────────────────────
BANNER = r"""
[primary]  ██████╗ ██████╗ ██╗    ██╗ ██████╗ ██████╗ ██╗  ██╗[/primary]
[primary] ██╔════╝██╔═══██╗██║    ██║██╔═══██╗██╔══██╗██║ ██╔╝[/primary]
[secondary] ██║     ██║   ██║██║ █╗ ██║██║   ██║██████╔╝█████╔╝ [/secondary]
[secondary] ██║     ██║   ██║██║███╗██║██║   ██║██╔══██╗██╔═██╗ [/secondary]
[highlight] ╚██████╗╚██████╔╝╚███╔███╔╝╚██████╔╝██║  ██║██║  ██╗[/highlight]
[highlight]  ╚═════╝ ╚═════╝  ╚══╝╚══╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝[/highlight]
"""

TAGLINE = "[italic_muted]  🤖 Makix Enterprise Agentic Coworker · Manager-Worker Architecture[/italic_muted]"

# ─── Phase Labels ─────────────────────────────────────────────────────────────
PHASE_LABELS = {
    1: ("[phase1]🛡️  Phase 1[/phase1]", "[phase1]Ingestion & Protection[/phase1]"),
    2: ("[phase2]🧠  Phase 2[/phase2]", "[phase2]Preparation · Meta-Routing[/phase2]"),
    3: ("[phase3]🤖  Phase 3[/phase3]", "[phase3]REACT Execution Loop[/phase3]"),
    4: ("[phase4]📡  Phase 4[/phase4]", "[phase4]Rendering & Finalization[/phase4]"),
    5: ("[phase5]🚀  Phase 5[/phase5]", "[phase5]Background Persistence[/phase5]"),
}

# ─── Telemetry Step Messages ──────────────────────────────────────────────────
TELEMETRY_STEPS = [
    "🔍 Analyzing request & architecting strategy...",
    "🧭 Routing intent to relevant tool domain...",
    "⚡ Parallel initialization: context + schema pre-fetch...",
    "🖇️  Optimizing context window...",
    "🤔 Reasoning and formulating execution plan...",
    "⚙️  Executing tools (parallelized)...",
    "🥪 Sandwiching large tool outputs...",
    "📝 Synthesizing final intelligence...",
    "🚀 Background persistence: memory ingestion...",
]

# ─── Tool Category Colors ─────────────────────────────────────────────────────
CATEGORY_STYLES = {
    "SEARCH_AND_INFO":        ("[router]🌍 SEARCH_AND_INFO[/router]",       "#60A5FA"),
    "MEDIA_AND_ENTERTAINMENT":("[accent]🎬 MEDIA_AND_ENTERTAINMENT[/accent]","#F59E0B"),
    "VISION":                 ("[highlight]👁️  VISION[/highlight]",          "#818CF8"),
    "DATA_AND_UTILITY":       ("[tool]📊 DATA_AND_UTILITY[/tool]",           "#34D399"),
    "SESSION_SCRATCHPAD":     ("[memory]📝 SESSION_SCRATCHPAD[/memory]",     "#F472B6"),
    "APP_CONNECTORS":         ("[sentinel]🔌 APP_CONNECTORS[/sentinel]",     "#FB923C"),
    "CONVERSATIONAL":         ("[muted]💬 CONVERSATIONAL[/muted]",           "#6B7280"),
    "ALL_TOOLS":              ("[error]🔥 ALL_TOOLS[/error]",                "#EF4444"),
}

# ─── Error Prefixes ───────────────────────────────────────────────────────────
GATEWAY_ERROR_PREFIX = "[GATEWAY ERROR]"
TOOL_ERROR_PREFIX    = "[TOOL ERROR]"

# ─── Operational Defaults ─────────────────────────────────────────────────────
OP_DEFAULTS = {
    "user_input_limit_tokens":    2000,
    "context_limit_tokens":       6000,
    "tool_output_limit_tokens":   1500,
    "max_steps":                  15,
    "max_tool_calls_per_step":    5,
    "max_total_tool_calls":       30,
    "idle_threshold_seconds":     900,
    "max_concurrent_jobs":        10,
    "decay_rate":                 0.02,
    "top_k_memories":             5,
    "temperature_router":         0.0,
    "temperature_compress":       0.1,
    "temperature_agent":          0.4,
    "temperature_chat":           0.7,
}

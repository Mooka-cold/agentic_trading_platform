# AI Trading Terminal - UI/UX Design Specification

## 1. Design System

### 1.1 Color Palette (Modern Financial)
*   **Background**: 
    *   App BG: `#F8FAFC` (Slate-50)
    *   Card BG: `#FFFFFF` (White) with subtle border `#E2E8F0` (Slate-200)
*   **Text**:
    *   Primary: `#0F172A` (Slate-900)
    *   Secondary: `#64748B` (Slate-500)
    *   Tertiary: `#94A3B8` (Slate-400)
*   **Functional**:
    *   **Bullish/Success**: `#10B981` (Emerald-500)
    *   **Bearish/Error**: `#EF4444` (Red-500)
    *   **Primary Brand**: `#3B82F6` (Blue-500)
    *   **Agent/AI**: `#8B5CF6` (Violet-500)

### 1.2 Typography
*   **Font Family**: `Inter` (UI), `JetBrains Mono` (Numbers/Code).
*   **Scale**:
    *   H1 (Page Title): 24px, Bold.
    *   H2 (Section Title): 18px, SemiBold.
    *   Body: 14px, Regular.
    *   Caption: 12px, Medium (Secondary text).

### 1.3 Spacing & Radius
*   **Radius**: `rounded-xl` (12px) for cards, `rounded-lg` (8px) for buttons/inputs.
*   **Shadow**: `shadow-sm` (subtle depth), `shadow-md` (hover states).
*   **Padding**: Compact density. `p-4` (16px) for standard card padding.

---

## 2. Layout Structure

### 2.1 Global Layout (`Shell`)
*   **Sidebar (Left)**: Fixed width `64px` (collapsed icon only) or `240px` (expandable). 
    *   *Decision*: Use **Compact Sidebar (64px)** by default for Laptop screens to maximize content area.
*   **Main Content (Right)**: Flexible area with `max-width: 1600px`.
*   **Responsive**:
    *   Desktop (>1024px): Sidebar + Grid Content.
    *   Mobile (<1024px): Bottom Navigation Bar + Stacked Content.

---

## 3. Page Specifications

### 3.1 Dashboard (Home) - The "Bento Box" Grid
A 2x2 Grid layout optimized for 13" screens (1280x800).

*   **Grid Area 1: Market Intelligence (Top-Left)**
    *   **Component**: `MarketOverviewCard`
    *   **Content**: 
        *   Mini Chart (Sparkline) of BTC/ETH/SOL.
        *   Key Indicators: RSI (Gauge), Fear & Greed (Bar).
        *   *Visual*: Clean data rows with +/- colors.

*   **Grid Area 2: News Feed (Top-Right)**
    *   **Component**: `NewsListCard`
    *   **Style**: Compact list (not giant cards). 
    *   **Content**: Title (truncate 2 lines), Source badge, Time ago, Sentiment dot (Red/Green).
    *   *No large images* to save space.

*   **Grid Area 3: Agent Workspace (Bottom-Left)**
    *   **Component**: `AgentChatCard`
    *   **Style**: Chat interface / Log stream.
    *   **Content**: Stream of agent thoughts ("Thinking...", "Executing...").
    *   *Visual*: Typewriter effect for AI text.

*   **Grid Area 4: Live Portfolio (Bottom-Right)**
    *   **Component**: `PortfolioCard`
    *   **Content**: Total Equity (Big Number), PnL Chart (Area chart), Active Positions table.

### 3.2 Strategy Square
*   **Layout**: Masonry Grid or Uniform Grid (3 columns).
*   **Card Design**:
    *   Header: Strategy Name + Author Avatar.
    *   Body: Performance Badge (ROI +%), Risk Level (Low/Med/High).
    *   Footer: "Clone" button + Subscribers count.

### 3.3 Settings
*   **Layout**: Split View (Left: Menu, Right: Form).
*   **Forms**: Clean inputs with labels above. `Save` button floating at bottom right or fixed top.

---

## 4. Component Implementation Checklist

1.  **Fix Configuration**:
    *   [ ] Re-initialize `tailwind.config.ts` with correct paths.
    *   [ ] Verify `postcss.config.js`.
    *   [ ] Clean `globals.css` imports.
    *   [ ] **CRITICAL**: Ensure `layout.tsx` imports CSS correctly.

2.  **Base Components (shadcn-like)**:
    *   [ ] `Button` (Primary, Ghost, Outline).
    *   [ ] `Card` (Container with standard padding/border).
    *   [ ] `Badge` (Status indicators).
    *   [ ] `Avatar`.

3.  **Feature Components**:
    *   [ ] `SideNav` (Compact mode).
    *   [ ] `NewsItem` (Compact row).
    *   [ ] `AgentLog` (Terminal style or Chat style).

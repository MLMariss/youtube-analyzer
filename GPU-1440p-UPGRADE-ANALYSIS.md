# GPU Upgrade Analysis — 1440p, 120+ Hz Gaming (Narrowed)

**Baseline:** GeForce RTX 3080 10 GB (GA102, 8704 CUDA, 320-bit, 760 GB/s, 320 W, Sep 2020)
**Target:** 2560×1440 on a 120 Hz+ display
**Date:** 2026-07-27

### Scoring rules

| Rule | Applied as |
|---|---|
| 1440p only | 1080p and 4K results discarded |
| **Frame generation is worthless** | **Excluded entirely — no card gets any credit for DLSS FG, MFG, or FSR FG** |
| Raster = main focus | weight **0.5** |
| Ray tracing = next to it | weight **0.3** |
| Rendering = weak secondary signal | weight **0.2** |
| Price | still ignored at this stage |
| Cut-off | anything at or under **+10%** composite over the 3080 is dropped |

**Composite score = (0.5 × raster) + (0.3 × ray tracing) + (0.2 × rendering)**, all indexed to RTX 3080 10 GB = 100.

---

## 0. What changed by removing frame generation

Two things, and both matter:

1. **The RTX 50 series lost its structural advantage.** MFG was the only thing Blackwell had that Ada didn't. Judged purely on silicon, the **RTX 4080 Super now outranks the RTX 5070 Ti** (+59% vs +51% composite). The RTX 40 series is back in genuine contention — subject to it being used-market only.
2. **The RTX 5070 lost its entire rationale.** In the previous pass it survived on MFG access alone. On raw silicon it is a +16% raster, 12 GB card. It clears the +10% cut on composite but it is now the weakest thing in the table.

**Assumption I'm making, flag it if wrong:** I've treated *upscaling* (DLSS/FSR Quality) as still acceptable, since it renders real frames and is a different technique from frame generation. If you reject upscaling too, jump to §4 — the qualifying list shrinks to three cards.

---

## 1. Methodology and confidence

Direct fetching of review sites was blocked by this environment's network policy — TechPowerUp, Tom's Hardware, TechSpot, GamersNexus and Blender Open Data all returned proxy denials. Figures are **consolidated from search-surfaced review summaries cross-checked against established aggregate positions**, not scraped first-hand.

- **Rank order is solid.** No source disputes it.
- **Individual percentages carry ~±5 pp.**
- **UserBenchmark-style composites were excluded** — they contradict every real 1440p game suite.
- At 1440p your 3080 is less bottlenecked than at 4K, so **every uplift here is smaller than the same comparison at 4K**. That is the honest framing for your resolution.

---

## 2. Master table — composite ranking

RTX 3080 10 GB = 100 in all index columns. Sorted by composite score.

| # | GPU | VRAM | Raster (0.5) | RT (0.3) | Render (0.2) | **Composite** | Raster+RT only |
|---|---|---|---|---|---|---|---|
| 1 | **RTX 5090** | 32 GB | +127% | +145% | +305% | **+168%** | +133% |
| 2 | **RTX 4090** | 24 GB | +98% | +110% | +195% | **+121%** | +102% |
| 3 | **RTX 5080** | 16 GB | +66% | +80% | +106% | **+78%** | +71% |
| 4 | **RTX 4080 Super** | 16 GB | +48% | +55% | +90% | **+59%** | +51% |
| 5 | **RTX 4080** | 16 GB | +45% | +52% | +88% | **+56%** | +48% |
| 6 | **RTX 5070 Ti** | 16 GB | +41% | +52% | +73% | **+51%** | +45% |
| 7 | **RTX 4070 Ti Super** | 16 GB | +30% | +40% | +43% | **+36%** | +34% |
| 8 | RTX 5070 | 12 GB | +16% | +25% | +27% | +21% | +19% |
| 9 | **RX 9070 XT** | 16 GB | +38% | +32% | **−41%** ⚠ | **+20%** | **+36%** |
| 10 | RTX 4070 Super | 12 GB | +16% | +22% | +25% | +20% | +18% |
| 11 | RTX 3090 Ti | 24 GB | +18% | +18% | +22% | +19% | +18% |
| 12 | RX 7900 XTX | 24 GB | +41% | +18% | **−40%** ⚠ | +18% | +32% |

**Dropped by the +10% composite cut:**

| GPU | Composite | Why |
|---|---|---|
| RX 7900 XT | +7% | Weak RT plus rendering regression sinks it below the line |
| RX 9070 | +6% | Same — the 0.2 rendering weight is what kills it |
| RTX 3080 Ti | +9% | Same generation, no gain worth having |
| RTX 4070 / 3090 / 5060 Ti / RX 9060 XT | ≤ +5% or negative | Not in class |

---

## 3. The 0.2 rendering coefficient is decisive for AMD — read this before you act

Compare the last two columns for the Radeon cards. This is the most important thing in the table:

| GPU | Composite (with 0.2 render) | Raster+RT only | Rank swing |
|---|---|---|---|
| RX 9070 XT | +20% → **9th** | +36% → **6th** | **−3 places** |
| RX 7900 XTX | +18% → 12th | +32% → 8th | −4 places |
| RX 9070 | +6% → **cut** | +19% → survives | **cut entirely** |

**Why this happens:** the rendering coefficient is small, but AMD's rendering figure is *negative* — the RX 9070 XT is ~41% **slower than your current RTX 3080** in Blender. A small weight on a large negative still drags hard. Every NVIDIA card in the table has rendering as a *bonus*; for AMD it's a penalty.

**My read, stated plainly:** you said you don't render much. A 0.2 coefficient is a meaningful weight — it's one fifth of the total score — and it is currently the single factor removing the RX 9070 XT from your shortlist. On pure gaming merit the 9070 XT is a legitimate 6th-place card at +36%, essentially tied with the RTX 5070 Ti in raster. **If "not much rendering" really means "almost never," 0.2 is too high and you should look at the Raster+RT column instead.** I've kept both columns so the choice is yours rather than buried in a formula.

---

## 4. Hitting 120+ fps at 1440p without frame generation

With FG off the table, the bar is materially higher. These are the honest thresholds:

| Path | Requirement | Cards that qualify |
|---|---|---|
| **Native 1440p ultra, 120 fps sustained** | ≈ +60% raster | **RTX 5080, RTX 4090, RTX 5090** — and nothing else |
| **DLSS/FSR Quality upscaling, 120 fps** | ≈ +35% raster | + RTX 4080/4080 Super, RTX 5070 Ti, RX 9070 XT |
| **Path-traced titles at 120 fps** | not achievable | No card in this list does this without MFG |

Your 3080 currently averages ~70–85 fps at 1440p ultra (~60–70 in heavy titles). Going native-120 needs roughly **+60%**, which is why the qualifying list is so short.

**The 10 GB buffer is still the sharpest problem** and it's independent of the fps question. Every card in the table above carries 16 GB or more except the two 12 GB entries. Doom: The Dark Ages and Indiana Jones — both with mandatory hardware RT — already force texture-pool compromises on 10 GB at 1440p. That category only grows. Expect the frame-buffer upgrade to improve 1% lows and streaming stalls by more than the average-fps numbers suggest.

---

## 5. Which specific card to buy — manufacturer models

Board partner choice barely affects performance (5070 Ti models sit within 57 MHz / 2–3 fps of each other). **Buy on cooling, noise, and physical size.**

### RTX 5080 — the native-120 pick

| Model | Verdict |
|---|---|
| **MSI Suprim SOC** | ✅ **Best overall.** Among the strongest cooling tested, whisper-quiet |
| **ASUS TUF OC** | ✅ **Best value pick.** ~60–62 °C at 1100 rpm, low noise, cheaper than Suprim |
| **Gigabyte Aorus Master** | ✅ Top-tier cooling, on par with Suprim |
| **Zotac Solid OC** | ✅ Cheapest better-than-reference — **the full 3.5-slot version, not the Slim** |
| Founders Edition | ⚪ Compact 2-slot, fine, but harder to find |
| ASUS ROG Astral OC | ❌ **Avoid.** Single-digit gains, higher power draw, *louder* than the FE, big premium |

### RTX 5070 Ti — the balance pick

| Model | Verdict |
|---|---|
| **ASUS TUF Gaming OC** | ✅ 58 °C, ~2716 MHz sustained, marginally louder than Gigabyte |
| **MSI Gaming Trio** | ✅ Large design, best thermal tier |
| **Gigabyte Gaming OC / Windforce OC** | ✅ 65 °C — warmest of the group but still cool and quiet |
| **MSI Ventus 3X OC** | ✅ **Best if space is tight.** Compact, clean, easy install, +45 MHz |
| Gigabyte Eagle OC Ice SFF | ⚪ SFF option if the build demands it |

### RX 9070 XT — only if you drop the rendering weight (see §3)

| Model | Verdict |
|---|---|
| **Sapphire Nitro+** | ✅ Top performance tier |
| **ASRock Taichi** | ✅ Top performance tier |
| **XFX Mercury** | ✅ Top performance tier |
| **PowerColor Red Devil** | ✅ **Best thermals.** Joint-best noise-normalised; hits the noise floor out of the box |
| Sapphire Pure / Gigabyte Elite / ASUS TUF | ⚪ Solid mid-tier |
| XFX Swift, XFX Quicksilver, Sapphire Pulse | ❌ Weakest performers in the 14-card roundup |

### RTX 5090 — only if 4K or rendering is a real second use case

| Model | Verdict |
|---|---|
| **MSI Suprim Liquid SOC** | ✅ Quiet, excellent GPU + VRAM temps, dumps 600 W outside the case |
| **Gigabyte Aorus Master / Waterforce** | ✅ Very good temps, pump inaudible |
| **ASUS ROG Astral OC** | ✅ PTM7950 compound, quad-fan, holds OC records — but expensive |

### RTX 4080 Super / 4080 / 4070 Ti Super

Used market only — discontinued. Model choice is whatever arrives in good condition; prioritise a triple-fan card with verifiable history over a specific brand. Note these have **no warranty runway**, which is the real cost of their strong composite scores.

---

## 6. Timing — the SUPER refresh is ~3 months out

Leaks point to **October 2026**, with NVIDIA reportedly EOL'ing the non-Super 5080 and 5070 Ti at launch:

| Card | Change |
|---|---|
| RTX 5080 SUPER | 10752 CUDA, 32 Gbps GDDR7, 415 W, **24 GB** (+50%), +9–16% perf |
| RTX 5070 Ti SUPER | 8960 CUDA, 28 Gbps GDDR7, 350 W, **24 GB** (+50%), +7–11% perf |
| RTX 5070 SUPER | **18 GB** (+50%) |

Leak-quality, so directional only. The +7–16% performance bump fails your own cut-off rule on its own — **the 16 → 24 GB jump is the part that matters**, since the upgrade case rests as much on frame buffer as on throughput. The two cards at the top of your shortlist are the two being replaced, one quarter out.

---

## 7. European pricing — the shortlist against real money

**Why Eurozone-only is the right call:** importing from the US or UK adds import VAT (19–27% depending on member state) plus duty and broker handling on top of a price that is already quoted ex-tax. That routinely erases a 15–20% headline saving and leaves you with no EU warranty path. Every price below is **Eurozone retail, VAT included**, from German retailers (19% VAT, typically the cheapest in the bloc) that ship EU-wide with no customs event.

Prices as of late July 2026. GPU pricing is volatile — treat these as ±5%.

> ⚠ **Market caveat:** the prices in this section are **German** (Geizhals/Mindfactory/Alternate). Baltic retail runs materially higher — see §8, where the RTX 5080 floor is €1,286 locally rather than the €1,159 quoted here. The RTX 5070 Ti figure of €845 is German-sourced too and needs local verification before the step-up maths below can be trusted. Germany is intra-EU, so buying there is customs-free and remains a live option.

### 7.1 The shortlist priced

| GPU | EU street price | Composite | **€ per point** | Status |
|---|---|---|---|---|
| **RTX 5070 Ti** | **€845–897** | +51% | **€16.6** | New, full warranty |
| RTX 4080 Super | €868 used / €1,359 new | +59% | €14.7 used | Used only — new price is a remnant, ignore it |
| **RTX 5080** | **€1,219–1,249** | +78% | **€15.6** | New, full warranty |
| RTX 4090 | €2,239 used / €2,310 new | +121% | €18.5 | Used, no warranty |
| RTX 5090 | €3,450–4,387 | +168% | €23.2 | New — but see below |

Cheapest verified sources: **Mindfactory €1,219**, Alternate €1,229, Proshop €1,239 for the RTX 5080. RTX 5070 Ti bottoms out at **€844.90**, ~€897 on Amazon.de.

### 7.2 The finding that decides this

**The RTX 5080 is better value per unit of performance than the RTX 5070 Ti** — €15.6/point versus €16.6/point. That inverts the normal rule where the cheaper card wins on value.

Look at the *marginal* rate, which is what actually matters when deciding whether to stretch:

| Step-up | Extra cost | Extra performance | Marginal rate |
|---|---|---|---|
| **5070 Ti → 5080** | **+€374** | **+27 pp** | **€13.9 / pp** ✅ |
| 5080 → 4090 (used) | +€1,020 | +43 pp | €23.7 / pp ❌ |
| 5080 → 5090 | +€2,681 | +90 pp | €29.8 / pp ❌ |

The €374 step from the 5070 Ti to the 5080 buys performance at **€13.9/pp — cheaper than the average rate of either card**. That is a genuinely rare situation and it is the clearest "pay a bit more, get meaningfully more" case in the entire lineup. It also happens to be the step that takes you from *needing upscaling to hit 120 fps* to *not needing it*.

Both step-ups above the 5080 do the opposite: you pay roughly **double the marginal rate** for performance you cannot use at 1440p.

### 7.3 Cards eliminated on price

- **RTX 5090 — eliminated.** €3,450–4,387 against a €2,229 MSRP, i.e. **55–95% over MSRP**. Worst €/point in the comparison (€23.2) and it is CPU-bound at 1440p anyway. You would be paying a 3.2× premium over a 5080 for performance your monitor cannot show.
- **RTX 4090 — eliminated.** €2,239 used. Costs **84% more than an RTX 5080 for 24% more performance**, on 4-year-old silicon with no warranty. The value case died when 5080 prices normalised.
- **RTX 4080 Super — conditional.** €868 used is the best raw €/point on the board (€14.7), and it out-scores the 5070 Ti. But: no warranty, EOL platform, unknown thermal history, and it is only €23 cheaper than a brand-new RTX 5070 Ti. **Only worth it below ~€750.** At €868, buy the 5070 Ti instead.

### 7.4 Do not overpay for the board partner model

This matters more than usual, because premium RTX 5080 variants destroy the exact advantage that makes the 5080 the smart pick:

| RTX 5080 model | Price | € per point | Verdict |
|---|---|---|---|
| **Zotac Solid OC (3.5-slot)** | ~€1,219 | **€15.6** | ✅ **Budget pick.** Cheapest better-than-reference cooler |
| **ASUS TUF OC** | ~€1,249–1,299 | €16.0–16.7 | ✅ **Best buy.** 60–62 °C at 1100 rpm, quiet, minimal premium |
| Gigabyte Aorus Master | ~€1,350–1,420 | €17.3–18.2 | ⚪ Excellent cooler, premium starts to bite |
| MSI Suprim SOC | ~€1,400–1,459 | €17.9–18.7 | ⚪ Best-in-class cooling, but you're paying €200 for silence |
| ASUS ROG Astral OC | ~€1,550+ | €19.9+ | ❌ Louder than the FE, single-digit gains |
| **ASUS Noctua** | **€1,699** | **€21.8** | ❌ **€21.8/pt — as bad as a 5090.** Avoid entirely |

**A €1,699 RTX 5080 is worse value than a €1,219 RTX 5080 by 40%, for the same silicon.** Stay at the €1,219–1,299 end or the whole argument for stepping up collapses.

For the RTX 5070 Ti, model choice barely matters — all variants sit within 57 MHz / 2–3 fps. Buy the cheapest of **MSI Ventus 3X OC**, **Gigabyte Windforce/Eagle OC**, or **ASUS TUF Gaming OC** at €845–900. Do not pay above ~€920 for any 5070 Ti.

### 7.5 Footnote: the RX 9070 XT on price

Dropped from this round, but it is the cheapest entry to the tier and price changes its case: **€640** (ASRock Challenger) to €660, against a €689 MSRP.

- On your composite (0.2 rendering): **€32.0/point — by far the worst on the board.**
- On raster+RT only: **€17.8/point — competitive with the 5070 Ti's €18.8.**

So the 0.2 rendering coefficient is worth roughly **€14/point** in this decision. If that weight is honest, the 9070 XT is out. If it isn't, the 9070 XT at €640 is the budget entry — **Sapphire Pulse** or **ASRock Challenger** at the low end, **PowerColor Red Devil** or **Sapphire Nitro+** around €720–800.

### 7.6 The timing risk now has a price tag

The SUPER refresh lands ~**October 2026**, roughly one quarter out, and reportedly EOLs the non-Super 5080 and 5070 Ti immediately. Buying a €1,219 16 GB RTX 5080 weeks before a **24 GB** RTX 5080 SUPER arrives at a rumoured $999–1,199 is a real financial risk — not because of the +9–16% performance, which fails your own cut-off rule, but because **50% more VRAM is exactly the thing this upgrade is meant to fix.**

Counter-argument, and it is a serious one: RTX 50 launch pricing in Europe ran far above MSRP for months. The 5090 is *still* 55–95% over MSRP eighteen months in. A €999 rumoured MSRP could easily mean €1,400+ on European shelves in October. **A €1,219 RTX 5080 available today may well beat a nominally cheaper SUPER you cannot actually buy until 2027.**

---

## 8. RTX 5080 board partner deep-dive — corrected against real listings

### 8.0 Two errors in the previous version of this section

**Error 1 — SKU/price conflation.** The previous draft headlined "Gainward Phoenix GS — €1,159." That was wrong. €1,159 was the *cheapest Gainward RTX 5080 listing of any kind*, which is the plain **Phoenix**. The specs quoted alongside it — vapor chamber, dual BIOS, high factory OC — came from TechPowerUp's review of the **Phoenix GS**, a different SKU. Price from one card, features from another.

They are distinguishable by part number:

| SKU | Part number | Boost | Cooling / features |
|---|---|---|---|
| Gainward RTX 5080 **Phoenix** | NE75080**0**19T2-GB2031X | **2617 MHz** (reference) | Triple fan, no factory OC |
| Gainward RTX 5080 **Phoenix GS** | NE75080**S**19T2-GB2031X | **2700 MHz** (+83 MHz) | Vapor chamber, dual BIOS, ball-bearing fans, RGB |

**+83 MHz is ~3% on clock — worth 1–2 fps.** The GS premium buys the cooler and the bin, not meaningful performance.

**Error 2 — wrong market, and this one matters more.** The whole §7/§8 price table was built on German Geizhals listings. Against real Baltic retail listings the floor is **€1,286**, not €1,159 — a **€127 gap** — and the rest of the table shifts with it. The German-derived €14.86/point headline does not exist in this market.

The "GS runs €20–40 more" line was also a guess presented as guidance, not a figure taken from listings.

### 8.1 Correction: shop/price mapping was misaligned

The previous version of this table bound prices to the wrong retailers. On the comparison grid each **shop badge sits above the product it belongs to**; the badges were read as belonging to the row above, shifting every shop by one row. Confirmed against semikom.lv's own storefront, which lists the Phoenix GS at **€1,592.87** — not the €1,346.88 previously attributed to it.

The consequence: the claim that "semikom.lv sells the GS cheaper than its own plain Phoenix" was an artefact of the misalignment and is false. semikom's GS is **€184.73 more** than its Phoenix.

Prices marked *(shop unidentified)* sit in a partially cropped row whose badges are not visible — they are real listings but cannot be attributed to a retailer.

### 8.2 Gainward RTX 5080 — corrected listings

Composite = **+78%** over the RTX 3080, identical on both SKUs.

**Phoenix GS** (NE75080S19T2-GB2031X, 2700 MHz):

| Shop | Rating | Price | €/point |
|---|---|---|---|
| **proline.lv** | ★★☆☆☆ (310) | **€1,325.00** | €16.99 |
| proline.lv | ★★☆☆☆ | €1,484.00 | €19.03 |
| dt24.lv | ★★★★★ (88) | €1,556.80 | €19.96 |
| **semikom.lv** | ★★★★☆ (26) | **€1,592.87** | €20.42 |
| nopirkt.lv | ★★☆☆☆ (531) | €1,607.31 | €20.61 |
| xmarket.lv | ★★★☆☆ (54) | €1,649.00 | €21.14 |
| 707.lv | ★★★★★ (560) | €1,688.70 | €21.65 |
| eltek.lv | ★★★★☆ (1K) | €1,698.65 | €21.78 |
| euromobile.lv | ★★☆☆☆ (415) | €1,709.80 | €21.92 |
| bigbox.lv | ★★★★☆ (722) | €1,715.54 | €21.99 |
| signe.lv | ★★★★☆ (403) | €1,739.68 | €22.30 |
| **rdveikals.lv** | ★★★★☆ (6.9K) | **€1,748.22** | €22.41 |
| nopirkt.lv | ★★☆☆☆ | €1,756.45 | €22.52 |
| 220.lv | ★★★★☆ (8.7K) | €1,829.70 | €23.46 |
| ⚠ labsveikals.lv | ★★★★☆ (509) | €1,581.24 **PVN 0% → €1,913** | €24.53 |

**Phoenix** (NE75080019T2-GB2031X, 2617 MHz):

| Shop | Rating | Price | €/point |
|---|---|---|---|
| **proline.lv** | ★★☆☆☆ (310) | **€1,286.00** | €16.49 |
| balticdata.lv | ★★★☆☆ (118) | €1,354.95 | €17.37 |
| smartech.ee | ★★☆☆☆ (29) | €1,381.35 | €17.71 |
| **rdveikals.lv** | ★★★★☆ (6.9K) | **€1,387.24** | **€17.79** |
| semikom.lv | ★★★★☆ (26) | €1,408.14 | €18.05 |
| tera.lv | ★★★★☆ (667) | €1,435.92 | €18.41 |
| proline.lv | ★★☆☆☆ | €1,440.00 | €18.46 |
| 1a.lv | ★★★★☆ (4.2K) | €1,519.00 | €19.47 |
| ksenukai.lv | ★★★☆☆ (513) | €1,519.00 | €19.47 |
| nopirkt.lv | ★★☆☆☆ (531) | €1,572.02 | €20.15 |
| euromobile.lv | ★★☆☆☆ | €1,687.80 | €21.638 |
| 707.lv | ★★★★★ (560) | €1,893.10 | €24.27 |
| electrobase.lv | ★★★☆☆ (33) | €1,963.23 | €25.17 |

### 8.3 The GS premium — same shop, both SKUs

This is what the earlier "€20–40 more" guess got wrong. Comparing within a single retailer:

| Shop | Phoenix | Phoenix GS | GS premium |
|---|---|---|---|
| 707.lv | €1,893.10 | €1,688.70 | **−€204.40** |
| euromobile.lv | €1,687.80 | €1,709.80 | +€22.00 |
| nopirkt.lv | €1,572.02 | €1,607.31 | +€35.29 |
| **proline.lv** | €1,286.00 | €1,325.00 | **+€39.00** |
| proline.lv (2nd listing) | €1,440.00 | €1,484.00 | +€44.00 |
| **semikom.lv** | €1,408.14 | €1,592.87 | **+€184.73** |
| **rdveikals.lv** | €1,387.24 | €1,748.22 | **+€360.98** |

**The premium ranges from −€204 to +€361 for the same +83 MHz.** The €20–40 figure held at exactly one retailer. There is no GS surcharge to generalise about — it must be checked per shop, per day.

### 8.4 This reverses the recommendation: buy the plain Phoenix

At the two best-rated retailers the GS costs **€185–361 extra** for **+83 MHz (~1–2 fps)** plus a vapor chamber and dual BIOS. That is not worth it. At rdveikals.lv the GS reaches **€22.41/point** — as poor as a ROG Astral.

**The plain Phoenix at rdveikals.lv, €1,387.24 (★★★★, 6.9K reviews), €17.79/point** is the best combination of price and seller reliability in these listings.

Take the GS only where the gap is genuinely ≤€50 — at proline.lv (+€39) or nopirkt.lv (+€35) — and only if you accept a ★★ seller.

### 8.5 Traps

**"PVN 0%" listings.** labsveikals.lv shows the GS at €1,581.24 **excluding VAT**. With 21% Latvian VAT that is **€1,913** — the most expensive GS on the page, displayed as if mid-priced.

**Cheapest is always proline.lv at ★★☆☆☆ (310 reviews).** It holds the floor for both SKUs (€1,286 / €1,325) and the gap to the cheapest well-rated seller is ~€100. Warranty is carry-in through the seller, so the rating is not cosmetic.

**Stock timing.** semikom.lv shows the GS as arriving **17.08.2026**; RD Electronics offers the Phoenix for collection from 7 August. Listed prices are not always immediately available stock.

**The "€1,148 floor" was a phantom — lead closed.** An earlier draft flagged a salidzini.lv listing advertising an RTX 5080 "no €1,148" and suggested chasing it. RD Electronics' product page resolves it: the Phoenix is **€1,387.24** for consumers and **€1,146.48 "Juridiskām personām"** — the VAT-excluded business price. €1,146.48 × 1.21 = €1,387.24 exactly. There is no €1,148 consumer card. Comparison sites surfacing B2B prices next to consumer ones is the same trap as the labsveikals "PVN 0%" entry.

### 8.6 Effect on the upgrade case

At real Baltic pricing the RTX 5080 spans **€16.49/point at the floor to €22.41/point at a well-rated seller**, against the €14.86 originally claimed. The realistic figure for a seller worth buying from is **€17.79/point**.

The ranking in §2 is unaffected — that is a performance ranking and no price error touches it. But the step-up case in §7.5 was built on German pricing and does not survive locally: the RTX 5070 Ti figure of €845 is German-sourced and unverified here. **Until local 5070 Ti pricing is checked, the "€314 for +27pp" argument should not be relied on in this market.**

---

## 9. Conclusions

### The two cards worth buying

**🥈 Budget option — RTX 5070 Ti, €845–900**
Cheapest of MSI Ventus 3X OC / Gigabyte Windforce OC / ASUS TUF Gaming OC. +51% composite, 16 GB, full warranty. Clears 120 fps at 1440p with DLSS Quality in essentially everything. €16.6/point. **Do not pay over €920.**

**🥇 Smart step-up — RTX 5080, €1,387.24 (verified Baltic retail)**
Gainward **Phoenix**, the plain non-GS SKU (NE75080019T2), at **rdveikals.lv / RD Electronics (★★★★, 6.9K reviews)** — €17.79/point, price confirmed on their storefront. Gainward has the lowest defect rate of any GPU brand (0.4%).

**Not the GS at that retailer** — it is €1,748.22 there, a €360.98 premium for +83 MHz. The GS is only worth taking where the gap is ≤€50, which in these listings means proline.lv (★★) at €1,325.

**The 5080 is still the right card**, for reasons untouched by any pricing error:

- It is the exact step from *needing upscaling to reach 120 fps* to *not needing it*.
- 16 GB properly solves the 10 GB frame-buffer problem that is the real reason to upgrade.
- ⚠ **But the step-up maths no longer holds locally.** The "€374 for +27pp" figure came from German pricing. The RTX 5070 Ti price above is German-sourced and unverified here — check it locally before treating the step-up as good value.

**Critical caveat: the same GPU spans €1,286 to €1,913 in Baltic retail** — a 49% spread for 2–3 fps. Every argument above collapses if you overpay for the cooler, and one listing hides 21% VAT. **§8 has the corrected model-by-model table and the traps.**

### Eliminated on price

| GPU | Why |
|---|---|
| **RTX 5090** | €3,450–4,387 vs €2,229 MSRP. Worst €/point (€23.2), CPU-bound at 1440p. 3.2× a 5080 for performance your monitor can't show |
| **RTX 4090** | €2,239 used. 84% more than a 5080 for 24% more performance, no warranty, 4-year-old silicon |
| **RTX 4080 Super** | Best raw €/point (€14.7) but only €23 cheaper than a *new* 5070 Ti. Only buy below ~€750 |

### Open question for you

The **RX 9070 XT at €640** is the cheapest way into the tier. Your 0.2 rendering coefficient costs it €14/point — €17.8/pt on gaming merit alone, €32.0/pt with the rendering weight applied. **That one coefficient is the entire decision.** If you genuinely almost never render, it belongs back on the list; if 0.2 is honest, it stays out.

### Standing caveats

- At 1440p these uplifts are the smallest they will ever look, and with frame generation excluded there is no multiplier to fall back on. **The real argument for upgrading remains the 10 GB frame buffer, not the fps number.**
- The SUPER refresh is ~3 months out with 24 GB. Real risk — but European RTX 50 street prices have run far above MSRP for eighteen months, so a nominally cheaper SUPER may not be buyable until 2027.

---

## Sources

- [TechSpot — RTX 5070 Ti Roundup, 9 cards tested](https://www.techspot.com/review/3108-nvidia-geforce-rtx-5070-ti-roundup/)
- [TechSpot — RX 9070 XT Roundup, 14 cards tested](https://www.techspot.com/review/3015-amd-radeon-9070-xt-roundup/)
- [TechPowerUp — MSI RTX 5080 Suprim SOC, Temperatures & Noise](https://www.techpowerup.com/review/msi-geforce-rtx-5080-suprim-soc/39.html)
- [TechPowerUp — ASUS RTX 5080 TUF OC, Temperatures & Noise](https://www.techpowerup.com/review/asus-geforce-rtx-5080-tuf-oc/39.html)
- [TechPowerUp — RTX 5080 Founders Edition Review](https://www.techpowerup.com/review/nvidia-geforce-rtx-5080-founders-edition/)
- [TechPowerUp — DOOM: The Dark Ages, 40 GPUs](https://www.techpowerup.com/review/doom-the-dark-ages-performance-benchmark/9.html)
- [KitGuru — PowerColor RX 9070 XT Red Devil Review](https://www.kitguru.net/components/graphic-cards/dominic-moass/powercolor-rx-9070-xt-red-devil-review/all/1/)
- [PC Gamer — ASUS TUF Gaming RTX 5070 Ti OC Review](https://www.pcgamer.com/hardware/graphics-cards/asus-tuf-gaming-rtx-5070-ti-oc-edition-review/)
- [Notebookcheck — MSI RTX 5070 Ti Ventus 3X OC Review](https://www.notebookcheck.net/MSI-GeForce-RTX-5070-Ti-16G-Ventus-3X-OC-Review-Near-perfect-mainstream-Blackwell-GPU-provided-you-can-get-one-at-749-MSRP.964050.0.html)
- [Notebookcheck — ASUS ROG Astral RTX 5080 OC Review](https://www.notebookcheck.net/Asus-ROG-Astral-GeForce-RTX-5080-OC-Edition-Review-Beautiful-bulky-and-bewilderingly-expensive.1066249.0.html)
- [Notebookcheck — RX 9070 XT vs RTX 5070 Ti, 55 games](https://www.notebookcheck.net/RX-9070-XT-vs-RTX-5070-Ti-battle-in-55-games-shows-5-performance-delta-with-some-big-wins-and-losses-for-Radeon-GPU.982678.0.html)
- [GamersNexus — RTX 5080 Founders Edition Review](https://gamersnexus.net/gpus/nvidia-geforce-rtx-5080-founders-edition-review-benchmarks-vs-5090-7900-xtx-4080-more)
- [Blender Open Data](https://opendata.blender.org/devices/NVIDIA%20GeForce%20RTX%205070%20Ti/)
- [Best Value GPU — RTX 5080 EU price tracker](https://bestvaluegpu.com/en-eu/history/new-and-used-rtx-5080-price-history-and-specs/)
- [Best Value GPU — RTX 5070 Ti EU price tracker](https://bestvaluegpu.com/en-eu/history/new-and-used-rtx-5070-ti-price-history-and-specs/)
- [Best Value GPU — RTX 4080 Super EU price tracker](https://bestvaluegpu.com/en-eu/history/new-and-used-rtx-4080-super-price-history-and-specs/)
- [Best Value GPU — RTX 4090 EU price tracker](https://bestvaluegpu.com/en-eu/history/new-and-used-rtx-4090-price-history-and-specs/)
- [Best Value GPU — RTX 5090 EU price tracker](https://bestvaluegpu.com/en-eu/history/new-and-used-rtx-5090-price-history-and-specs/)
- [Best Value GPU — RX 9070 XT EU price tracker](https://bestvaluegpu.com/en-eu/history/new-and-used-rx-9070-xt-price-history-and-specs/)
- [GPUTracker EU — RTX 5080 listings](https://www.gputracker.eu/en/search/category/1/graphics-cards/facet/2/graphics-chip/nvidia-rtx-5080)
- [TechPowerUp — RX 9070/9070 XT fall below MSRP in Germany](https://www.techpowerup.com/347952/amd-radeon-rx-9070-and-rx-9070-xt-fall-below-msrp-in-germany)
- [Tom's Hardware — NVIDIA cuts RTX 50 series prices in Europe](https://www.tomshardware.com/pc-components/gpus/nvidia-has-cut-some-rtx-50-series-prices-in-europe-rtx-5090-5080-and-5070-reduced-by-almost-10-percent-likely-prompted-by-falling-u-s-dollar)
- [VideoCardz — ASUS Noctua RTX 5080 at EUR 1699](https://videocardz.com/newz/noctua-rtx-5080-graphics-card-officially-priced-at-eur1699-60-over-nvidias-current-msrp)
- [DropReference — graphics card price evolution 2026](https://dropreference.com/en/blog/news/evolution-price-graphics-card-march-2026)
- [Geizhals DE — Gainward RTX 5080 listings](https://geizhals.de/gainward-geforce-rtx-5080-v186837.html)
- [Geizhals DE — Palit RTX 5080 listings](https://geizhals.de/palit-geforce-rtx-5080-v186847.html)
- [Geizhals DE — Gigabyte RTX 5080 listings](https://geizhals.de/gigabyte-geforce-rtx-5080-v186706.html)
- [Geizhals DE — INNO3D RTX 5080 listings](https://geizhals.de/inno3d-geforce-rtx-5080-v186865.html)
- [Geizhals DE — Zotac RTX 5080 Solid CORE OC](https://geizhals.de/zotac-gaming-geforce-rtx-5080-solid-core-oc-zt-b50800j2-10p-a3417016.html)
- [Geizhals DE — ASUS TUF Gaming RTX 5080 OC](https://geizhals.de/asus-tuf-gaming-geforce-rtx-5080-oc-90yv0m30-m0na00-a3382457.html)
- [Geizhals DE — MSI RTX 5080 Ventus 3X OC](https://geizhals.de/msi-geforce-rtx-5080-16g-ventus-3x-oc-a3382121.html)
- [TechPowerUp — Gainward RTX 5080 Phoenix GS Review](https://www.techpowerup.com/review/gainward-geforce-rtx-5080-phoenix-gs/)
- [TechPowerUp — Gainward Phoenix GS, Temperatures & Fan Noise](https://www.techpowerup.com/review/gainward-geforce-rtx-5080-phoenix-gs/39.html)
- [TechPowerUp — Gigabyte RTX 5080 Gaming OC, Cooler Performance](https://www.techpowerup.com/review/gigabyte-geforce-rtx-5080-gaming-oc/40.html)
- [TweakTown — GPU failure rates and warranty claim times by brand](https://www.tweaktown.com/news/93052/heres-look-at-gpu-failure-rates-and-warranty-claim-times-for-all-major-brands/index.html)
- [ZOTAC — product warranty policy (3+2 years)](https://www.zotac.com/ro/page/product-warranty-policy)
- [Guru3D — Gainward & Palit three-year warranty](https://www.guru3d.com/story/gainward-palit-increase-warranty-three-years/)
- [Salidzini.lv — GeForce RTX 5080 price comparison](https://www.salidzini.lv/cena?q=geforce+rtx+5080)
- [KurPirkt.lv — RTX 5080 ASUS TUF price range](https://www.kurpirkt.lv/cena.php?q=rtx+5080+asus+tuf)
- [RD Electronics — RTX 5080 listings](https://www.rdveikals.lv/categories/lv/417/sort/5/filter/0_0_0_398826/page/1/Videokartes.html)
- [Dateks.lv — ASUS RTX 5080 ROG Astral OC](https://www.dateks.lv/en/cenas/videokartes/1186873-asus-geforce-rtx-5080-16gb-gddr7-rog-astral-oc-dlss-4-)
- [PCPartPicker — Gainward Phoenix GS (NE75080S19T2-GB2031X)](https://pcpartpicker.com/product/G3bypg/gainward-phoenix-gs-geforce-rtx-5080-16-gb-video-card-ne75080s19t2-gb2031x)
- [PCPartPicker — Gainward Phoenix (NE75080019T2-GB2031X)](https://pcpartpicker.com/product/Lr62FT/gainward-phoenix-geforce-rtx-5080-16-gb-video-card-ne75080019t2-gb2031x)
- [TechPowerUp GPU DB — Gainward RTX 5080 Phoenix GS V1 specs](https://www.techpowerup.com/gpu-specs/gainward-rtx-5080-phoenix-gs-v1.b12813)
- [Gainward — Phoenix series product page](https://www.gainward.com/main/vgapc.php?fanseries=PHOENIX&lang=en)
- [TweakTown — RTX 50 SUPER refresh leaks](https://www.tweaktown.com/news/107546/heres-the-full-leaked-details-on-rtx-5080-super-rtx-5070-ti-super-rtx-5070-super-in-october/index.html)

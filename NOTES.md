# NOTES.md — season log, open items, things to keep track of

Running notes for the 2026 season: what happened, what was decided, what is
pending. Newest entries at the top of each section. Referenced from
`CLAUDE.md` and `README.md`.

---

## Leagues

| League | ID | Team | Format | Waivers |
|---|---|---|---|---|
| 2MinuteDrill | 814693 | S Dot Sack | 12-team, QB/RB/RB/WR/WR/TE/FLEX/K/DEF + 5 BN + 1 IR. 6-pt pass TD, +5 at 100/150 rush & rec yds, +5 at 350/450 pass yds | FAAB, $100 |
| First Down | 174617 | MacRazy | 10-team, QB/RB/RB/WR/WR/WR/TE/FLEX/K/DEF + 6 BN + 1 IR. Standard 4-pt pass TD, PPR. $100 buy-in | Priority (rolling) |

URLs: `https://football.fantasysports.yahoo.com/f1/<id>` (home/standings),
`/matchup?week=N`, `/transactions`, `/players?status=A&pos=RB&stat1=S_PW_2&sort=PTS&sdir=1`
(available by projected pts; `stat1=S_W_1` = week-1 actuals), `/<team_id>` (roster).

Team IDs, 2MinuteDrill: TD 1 · 619ers 2 · CaliBayBoi510 3 · DuffelBagBoy$$ 4 ·
Hit Em Wit Da Flex 5 · $KBboutabag$ 6 · Sacala 7 · JAHSHAWN GIBBS 8 · phukumean 9 ·
RocGPT 10 · **S Dot Sack 11** · OnlyBags 12.

Team IDs, First Down: Call Me MAYE-be 1 (commish) · Billy Ba Ba Ba 2 · **MacRazy 3** ·
Deebo 4 · House of Tweez 5 · Hurting bad 6 · Literally the Worst 7 ·
[Placeholder name] 8 · T & T's Prenup 9 · —HA HA— 10.

**Yahoo API is 403.** `nbs/oauth2.json` refreshes fine but every Fantasy endpoint
returns "This application is not authorized to perform this action" — the
developer app lacks the Fantasy Sports read scope. Fix at developer.yahoo.com,
not in code. Until then, league data is pulled from the Yahoo site in Chrome.

---

## Week 4 punchlist (Sep 29 – Oct 5)

**HOLD — nothing executed yet.** Sean's call (Sep 28): wait until Week 3 closes after tonight's MNF, then do a final league assessment and act. Timing is fine: MNF ends tonight, waivers process **Wed Sep 30**, so claims go in **Tuesday Sep 29**. Nothing below has been placed.

**Status Mon Sep 28.** 2MD **2-1** (4th, 3rd-most PF). FD **1-2** (6th). **De'Von Achane tore his ACL — season over**, and he was the FD RB1. Breece Hall (2MD RB2) is questionable with a thigh injury, no update until Wednesday. Waivers in BOTH leagues process **Wed Sep 30**. FAAB $80 (2MD); waiver priority **#1** (FD).

| When | League | Item | Status |
|---|---|---|---|
| Now | FD | **Move Achane to IR** (slot confirmed eligible). Frees a bench spot so the claim needs no drop. | open |
| Before Wed Sep 30 | FD | **Claim #1: Ollie Gordon II (MIA).** Took 83.6% of snaps and 100% of RB touches after Achane left; 1–3% rostered. Only target whose opportunity is *certain*. | open |
| Wed Sep 30 (after wire clears) | FD | **Add Jaylen Wright (MIA)** as a free agent if unclaimed — 1–4% rostered, listed AHEAD of Gordon on Miami's depth chart, back from a stinger/foot. Owning both = own the backfield. Drop Dobbins. | open |
| Before Wed Sep 30 | 2MD | **Claim Braelon Allen (NYJ) ~$18** — the Hall contingency; Isaiah Davis has 0 offensive snaps, so if Hall sits it's Allen alone. Contested (14–22% rostered, consensus 25–40% FAAB). Drop Sutton. | open |
| Before Wed Sep 30 | 2MD | **Second claim: Ollie Gordon ~$7** (5% rostered here). Drop Murray if Allen also lands. | open |
| Thu Oct 1, before 8:15pm | FD | Thursday rule: Denzel Boston (CLE, 10.41) and Steelers DEF both play Thu @ CLE. Boston does NOT beat Golden (11.16) on merit — leave him benched. | open |
| Wed Oct 1 | 2MD | Hall's MRI/designation from Aaron Glenn's Wednesday presser. If OUT: Jones to RB2, M. Wilson to flex. | open |
| Fri Oct 2 | both | Friday designations: Hall (thigh), Aaron Jones (knee), Mark Andrews (hand), Jaylen Wright (practice), Ashton Jeanty (ankle). | open |
| Sun Oct 4 | both | Inactives. Note J. Taylor + Warren play 9:30am London; McLaurin 9:30am too (FD). | open |
| Standing | FD | Priority #1 is being spent on Gordon — the exact case it was reserved for (starter's replacement, permanent opening). | resolved |
| Standing | 2MD | Breakouts cost $20+, contingent roles $6–9. We lose all ties (12th of 12), so no round numbers. | standing |

### Week 4 lineups (proposed)
**2MinuteDrill vs CaliBayBoi510 (1-1) — Yahoo 60% us, 128.5 vs 115.3.** Note: they also rostered Achane and still have him in their RB slot at 7.90.
QB Stafford (@PHI, 20.7) · RB J. Taylor (@WAS London, 20.1) · RB Breece Hall (@CHI, 15.0, *pending Wed*) · WR Olave (vs ATL Mon, 17.3) · WR G. Wilson (@CHI, 14.6) · TE Warren (@WAS, 13.1) · **FLEX Michael Wilson (@NYG, 12.3)** · K Dicker · DEF Steelers
Bench: A. Jones 11.8, Golden 11.2, Sutton 9.9 (drop candidate), Henry 9.7, Murray (drop candidate)
If Hall is OUT: Jones to RB2, flex stays M. Wilson, Golden is the next man up.

**First Down vs —HA HA— (2-0) — Yahoo 46% us, 122.1 vs 126.5.**
QB Hurts (vs LAR, 17.3) · RB Jeremiyah Love (@NYG, 16.4) · RB Bhayshul Tuten (@CIN, 12.0) · WR Lamb (@HOU, 17.1) · WR Rice (@LV, 13.6) · WR McLaurin (vs IND London, 12.6) · **TE Kittle (vs DEN, 10.4)** · **FLEX Golden (@TB, 11.2)** · K Aubrey · DEF Steelers (Thu @CLE)
Bench: Andrews 10.1, Boston 10.4 (Thu), Sutton 9.9, Dobbins 7.2 (drop candidate), Shough (trade chip). **Achane → IR.**

### Usage findings that drove these calls (Weeks 1–3)
- **Michael Wilson (ARI)** — real role, inflated week. 85% snaps, 67 routes and 14 targets vs Marvin Harrison Jr.'s 4 targets/1 catch. But W3's 17 targets came trailing 36-30. Project ~9–11 targets, not 17.
- **Start Kittle over Andrews.** Andrews has the better target share (23.2% vs 16.1%) and no TE competition, but 1 RZ target in two games, a 3-24 dud and a hand injury. Kittle's arrow is up everywhere: team-leading snaps, 30% TPRR, all 7 inside-the-10 snaps in W2, 2 TDs in W3. Andrews is the better ROS hold.
- **Jeremiyah Love is the ARI lead back** — 43% → 64% snaps, 81.3% backfield opportunity share, 26 of 32 RB touches in W3. Conner on IR (out through at least Wk4), Benson waived. Conner's Wk5+ return is the only threat.
- **Tuten has the JAX job but is capped** at ~50% snaps in Coen's committee. 15 carries back-to-back, goal-line TDs in W2 and W3. RB2/flex floor, limited ceiling.
- **Three fades, all role-driven:** Sutton (Waddle is Denver's WR1; 82 yards in three games), Kyler Murray (168 pass yds, 2 carries — no rushing floor, can't reach the 350 bonus), Breece Hall (107 → 29 → 21 rush yards *before* the injury).
- **Three underpriced holds:** Golden (10% → 25.4% target share, 89% route rate, 2nd-most RZ targets in the NFL with zero RZ TDs, and Jayden Reed is likely done for the year), Olave (**37 targets = most in the NFL**, three near-TDs in W3), Rice (2 → 6 → 9 targets).
- **Stafford** attempts escalating 25 → 31 → 55; 55-attempt games clear the 350/450 bonuses and 6-pt TDs amplify. Chronic back is the standing risk.

### Trade board (rebuilt ROS vs league median, Sep 28)
**2MD — S Dot Sack 1577, 4th of 12. No slot more than 13 below median.** Surplus: Murray 294 (QB2), Golden 150, Sutton 147, Jones 143, Henry 142. Verdict: **stand pat**, work the wire. Murray's trade value is low precisely because the research says he's a fade.
**FD — MacRazy 1615, now LAST in lineup strength.** RB1 -39, RB2 -33, FLEX -21 after losing Achane. Surplus is **Shough (261 ROS)** behind Hurts. Targets: House of Tweez (needs QB1, has RB Jadarian Price 165), [Placeholder name] (needs QB1 — Caleb Williams is out — has Croskey-Merritt 139/Gainwell 138), Literally the Worst (needs QB1). **Primary offer: Shough → House of Tweez for Jadarian Price.**

---

## First Down game plan (from Week 4 on)

**Situation.** 1-2 after the Week 3 loss, 6th of 10. **Six of ten make the playoffs** (Weeks 15-17, reseeded), so 1-2 is not a hole — it is a bad month, not a lost season. Trade deadline **Nov 28**. Waivers are a **continual rolling priority list** (no FAAB) and we hold **#1**, processing Wednesdays. Roster limit 10 starters + 6 bench + 1 IR.

**Diagnosis.** Losing Achane made us **last in the league in rest-of-season lineup strength (1615)**. The damage is concentrated:

| Slot | Us | vs median |
|---|---|---|
| RB1 Jeremiyah Love | 210 | **-39** |
| RB2 Bhayshul Tuten | 174 | **-33** |
| FLEX Golden | 150 | **-21** |
| QB Hurts | 266 | -14 |
| WR1 Lamb / WR2 Rice / WR3 McLaurin | 262 / 213 / 178 | 0 / +13 / -1 |
| TE Kittle | 161 | -1 |

Receivers and tight end are fine. **Every point of the deficit is running back.** Meanwhile QB is a surplus: Shough (261 ROS) sits behind Hurts and three teams in this league need a starting QB.

**Strategy: convert surplus into running back volume, and spend priority #1 on the one permanent opening.**
Gordon is the only available back whose opportunity cannot evaporate — Achane's season is over. Everyone else on the wire is a handcuff whose value depends on someone else's health. Pairing Gordon with Wright (1-4% rostered) means we own the Miami backfield no matter how Hafley splits it, for one claim plus one bench spot.

### Sequenced actions

| When | Action | Why / drop |
|---|---|---|
| Tue Sep 29 | **Achane → IR slot** (confirmed eligible) | Frees a bench spot so the claim costs nothing |
| Tue Sep 29 night | **Claim #1: Ollie Gordon II (MIA)** | 83.6% of snaps and 100% of RB touches after Achane left; 1-3% rostered. No drop needed. |
| Tue Sep 29 night | **Trade offer: Shough → [Placeholder name]**, ask Jacory Croskey-Merritt (139) | Their QB Caleb Williams is OUT; they are the most desperate QB buyer in the league. Fallback ask: Kenny Gainwell. |
| Tue Sep 29 night | **Backup offer: Shough → House of Tweez**, ask Jadarian Price (165) | They need QB1 (Bryce Young) and have Price on the bench. Send only if [Placeholder] declines — never two offers of the same player at once. |
| Wed Sep 30, after wire clears | **Add Jaylen Wright (MIA)** as a free agent, drop **J.K. Dobbins** | Wright is listed ahead of Gordon on Miami's depth chart and Yahoo's FAAB column ranks him higher. Dobbins is in a 3-way Denver committee with no receiving role — PPR-dead. |
| Thu Oct 1, pre-8:15pm | Thursday rule check: Boston and Steelers DEF both play Thu @ CLE | Boston (10.4) does not beat Golden (11.2) on merit — leave benched |
| Fri Oct 2 | Designations: Andrews (hand), Wright (practice), Love | |
| Sun Oct 4 | Inactives; McLaurin plays 9:30am London | |

### Week 4 lineup vs —HA HA— (2-0)
QB Hurts · RB **Jeremiyah Love** · RB **Bhayshul Tuten** · WR Lamb · WR Rice · WR McLaurin · TE **Kittle** · FLEX **Golden** · K Aubrey · DEF Steelers
Bench: Andrews, Boston, Sutton, Dobbins→(dropped), Shough→(trade chip), Gordon if claimed. Achane on IR.

### Contingency tree
- **Priority #1 cannot lose** — it is the top of the rolling list. The only risk is spending it on the wrong man, which is why it goes to the permanent opening (Gordon), not the coin flip (Braelon Allen, whose case resolves at Wednesday's Jets practice, i.e. after waivers run).
- **After using #1 we drop to last in the order.** Every later claim is effectively a free-agent race, so speed matters more than timing from here.
- **If someone else claims Wright**, we still hold Gordon and Miami's job is a 60/40 at worst. Do not panic-add a third Miami back.
- **If James Conner returns (Week 5+)**, Love's 81% opportunity share shrinks. That is the single biggest threat to our RB1 — recheck it every Friday.
- **If the Shough trades both fail**, hold him. QB-needy teams get more desperate, not less, and Hurts has a Week 10 bye we would otherwise have to stream.

### Do not
- Do not chase Case Keenum or any streaming QB. We start one QB and have two.
- Do not drop Andrews. He is the better rest-of-season TE hold even though Kittle is the better Week 4 start.
- Do not trade Lamb or Rice. They are the only reason the receiving corps is at median.
- Do not spend the claim on a handcuff whose situation resolves after waivers process.

---

## Open items / pending

### 2MinuteDrill
- [x] **Waiver 1 (Sep 16): WON** — Devaughn Vele added for $6, Tyjae Spears dropped. FAAB now $94.
- [x] **Waiver 2 (Sep 16):** Shakir claim skipped, as designed (same drop as claim 1).
- [x] ~~**Trade proposed (Sep 15) to CaliBayBoi510:** Tee Higgins for Aaron Jones + Hunter Henry.~~ **Closed by Sep 20**: no longer pending when Sean asked to withdraw it; not in the league trade log, so Bjohn most likely rejected it (Yahoo doesn't log rejections).
      If declined → resend for Stefon Diggs, then Jameson Williams.
- [x] ~~Trade to phukumean: Aaron Jones for A.J. Brown~~ **Withdrawn Sep 23** at Sean's call (no response in 2 days, and Jones's knee made it moot). Jones stays; no open offers in either league.
- [x] **Waiver (Sep 23): LOST Tre Tucker.** OnlyBags won him at **$20**. Our $9 (and even the original $14) was never close. Henry stays; FAAB still $94.
- [x] **WON (Sat Sep 26): $14 Michael Wilson (Ari WR), dropped Devaughn Vele.** FAAB now **$80**. Original note:  Wilson ROS 161 vs Vele 97; both Wilson (83% ros) and Chris Godwin (85%) were dumped this week after the Tucker/A.Mitchell claims. Fallback if lost: Godwin or Brenton Strange (TE, FA).
- [ ] **Trade proposed (Sep 24) to Hit Em Wit Da Flex:** Kyler Murray + Hunter Henry for **Jaylen Waddle**. Their QB Jayden Daniels is OUT and their TE is Pitts 144; they are last in lineup strength. For us: Waddle (199 ROS) fills the FLEX hole (Golden 150, -26 vs median), and both pieces we send are bench-only. **Cost if accepted: Stafford has no backup QB** — stream during the LAR bye (Week 11); wire QBs are Brissett/Lock/Rodgers.
- [ ] **Flex plan (2MD):** hold Jones; do NOT start Golden Thu (he locks 8:15pm Thu). If Jones is OUT Friday → Sutton (plays SNF, so swappable Sunday afternoon); Vele is the 4:25 backup option.
- [ ] **Kyler Murray (Q):** check Wed/Fri. IR slot if designated; if out but not IR-eligible, cut for Tyler Shough (~$8 bid).
- [ ] Only if the Cali trade fails entirely: Breece Hall → phukumean for Nico Collins (optional; skip if bullish on Hall).
- [x] Lineup Wk2 (verified Sep 16): Stafford / Taylor / Hall / Olave / G. Wilson / Warren / **Sutton (flex)** / Dicker / Steelers. Bench: Henry, A. Jones, Golden, K. Murray (Q), Vele. IR empty.
- **Decision: keep Tyler Warren.** Not trading him; Henry is a throw-in only.

### First Down
- [x] Lineup Wk2 (set Sep 15, verified Sep 16): Hurts / Achane / J. Love / Lamb / Rice / McLaurin / **Kittle (TE)** / **Sutton (flex)** / Aubrey / Steelers. Bench: Andrews, Tuten, Dobbins, Golden, Shough, Boston. IR empty.
- [x] **Cancelled (Sep 15):** stray waiver claim "Add Hunter Henry, drop Spears" — origin unclear (possibly a mis-clicked Add during the 2MD Vele flow). Would have spent waiver priority #1 on a third TE. Sean cancelled it; priority #1 preserved.
- [x] **Sep 16, FA add (no priority cost):** Denzel Boston added, Tyjae Spears dropped. Waiver priority still #1.
      Decisions: **no defense streaming** (Sean: "defense isn't an optimization I want to focus on, Steelers are fine"); **Shough stays** as QB2 for now.
      Bench now: Andrews, Tuten, Dobbins, Golden, Boston, Shough.
- **Decision (Sep 21): skip Dalton Schultz (HOU TE).** His Week 2 (26.0) came with Nico Collins out; Week 3 proj 9.9 is below Kittle 11.2 and Andrews 10.8. He's on waivers until Sep 23, so a claim would burn priority #1. Revisit only as a free agent after waivers clear AND only if Collins is out long-term.
- [x] ~~**Trade proposed (Sep 15) to Billy Ba Ba Ba:** Omarion Hampton for Terry McLaurin~~ **Withdrawn Sep 20 at Sean's request.** (they have an EMPTY WR3 slot and six RBs). If declined → Sutton + Golden for TreVeyon Henderson, then RJ Harvey.
- [ ] Trade 2: McLaurin + Golden → T & T's Prenup for Bucky Irving.
- [ ] Trade 3: Sutton + Dobbins → —HA HA— for Chuba Hubbard (Spears is gone).
- Deebo and Hurting bad are chasing the same RBs → send the Hampton offer first.

---

## Log

### 2026-09-28 — Week 4 plan built; execution on hold
- Refreshed the repo's 3-week-stale data (`espn`/`news`/`injuries` builders). That is how Achane's ACL (Out, return 2027-02-15, 20 weeks) and Hall's thigh surfaced with return dates attached.
- Deep research on Weeks 1-3 usage for every starter, plus the full RB waiver market. Findings and sources are in the Week 4 section above.
- Built the Week 4 punchlist, proposed lineups, and a rebuilt ROS-vs-median trade board for both leagues.
- Added an in-season weekly runbook to `RUNBOOK.md` (Mon post-mortem → Tue claims → Wed pressers → Thursday rule → Fri designations → Sun inactives).
- **Nothing executed.** Sean wants a final assessment after tonight's MNF closes Week 3. Claims are due Tuesday night for Wednesday processing.

### 2026-09-27 — Week 3 results: 2MD W, FD almost certainly L
- **2MinuteDrill W 146.90–140.34 over RocGPT (now 2-1).** Stafford 28.90, G. Wilson 31.70, Olave 24.70, Warren 14.70, A. Jones 14.20 (knee held up), Dicker 10.00. Bench: Michael Wilson 25.90 (!), Golden 26.00, Murray 13.42, Sutton 7.60, Henry 1.50.
- **First Down 108.30–139.14 with Hurts (MNF) left; needs 30.85, Yahoo 9%.** J. Love 21.90, Lamb 20.20, McLaurin 19.70, Rice 15.80, Aubrey 11.00; Achane 1.70 (D tag, dud), Andrews 5.40, Sutton 7.60.
- **Bench points left in FD:** Kittle 26.20 (vs Andrews 5.40 = **-20.8**), Tuten 17.00 (vs Sutton 7.60 = -9.4), Golden 21.00 (vs McLaurin 19.70 = -1.3), Shough 24.80 (vs Hurts TBD).
- **My bad call:** the Andrews-for-Kittle stack (BAL@DAL with Lamb + Aubrey) was mine and cost ~21. Lamb and Aubrey hit; Andrews didn't. Even a perfect Sunday lineup (~138.5) still trailed their 139.14 before Hurts, so the week was near-unwinnable after Bijan's 35 on Thursday — but the swap turned a live game into a blowout.
- **Lessons recorded:** (1) don't bench a stable high-floor starter (Kittle) to stack a game when the stack adds ~0.5 proj; correlation is worth chasing only when the projection cost is ~0 AND the teammate share is high. (2) The Thursday rule (Golden) cost ~11 the week before — both losses this week came from over-managing the margins.
- 2MD flex note: Michael Wilson (25.90) outscored the flex (Jones 14.20) in his first week on the roster. Worth remembering for Week 4.

### 2026-09-26 — Week 3 lineups locked
- **2MD (vs RocGPT, coin flip):** Stafford / Taylor / Hall / Olave / G. Wilson / Warren / **A. Jones (flex, cleared)** / Dicker / Steelers. Kept Stafford over Murray (proj 19.7 vs 21.0) — Murray's first game back from a Week 1 concussion, and he's in the pending Waddle offer. Bench: Sutton, Henry, Murray, M. Wilson, Golden (played Thu).
- **FD (vs House of Tweez, trailing):** swapped **Andrews in at TE for Kittle** (12.2 vs 11.7) to stack the BAL@DAL game with Lamb and Aubrey — deliberate variance play while chasing. Kept Hurts (MNF leverage) over Shough, McLaurin over Boston, Sutton in the flex (SNF lever).
- Opponent math (FD): Tweez at 57.90 with Bijan 35.3 and Watson 22.6 done; their remaining 8 project ~94, so ~152 total vs our ~130.

### 2026-09-26 — Wilson claim won; Jones cleared; Golden burn
- **Won Michael Wilson at $14**, dropped Vele. FAAB $80. Bench now: Sutton, Henry, Golden, Murray, M. Wilson.
- **Aaron Jones: no game status.** Full practice Friday, off the final injury report. He stays in the 2MD flex.
- **Thursday lesson (cost ~11 pts in FD):** Matthew Golden scored 21+ on our bench vs ATL. We held him because the Jones designation came Friday. RULE GOING FORWARD: judge a Thursday-game player on his own merit before kickoff; do not treat him as a contingency for a Friday decision. If he'd start on merit, start him.
- Waddle offer to Hit Em Wit Da Flex still unanswered (they have not set a lineup in 3 weeks).

### 2026-09-24 — 2MinuteDrill: Wilson claim + Waddle offer
- Wire scan: Michael Wilson (161 ROS, 83% ros) and Chris Godwin (153, 85%) hit waivers after other teams' Tucker/Mitchell adds. Claimed Wilson at $14, dropping Vele (97). Processes Sat Sep 26.
- Trade sent: Murray + Henry → Hit Em Wit Da Flex for Jaylen Waddle. Rationale: our only sub-median slot is FLEX (-26); Hit Em's QB is out and their TE is Pitts; both pieces we give are bench-only.
- Roster map (ROS proj vs 12-team median): RB1 Taylor +25, TE Warren +17, RB2 Hall +12, WR2 G.Wilson -6, WR1 Olave -10, QB Stafford -16, FLEX Golden -26.
- FD checked, no action: we are within ±10 of median at all 8 slots; wire has only Wan'Dale Robinson (148, FA) who matches our bench. Waiver priority #1 still held.
- Budgets after Wed waivers (2MD): 619ers 71, OnlyBags 75, $KB 75, RocGPT 77, Hit Em 93, us 94, others 100.

### 2026-09-23 — Brown offer withdrawn
- phukumean never responded in ~2 days; Sean pulled it. Jones (knee, DNP Wed) stays on the roster and remains the Week 3 flex question.
- Standing: no open trade offers in either league.

### 2026-09-23 — Waivers: lost Tucker, market repriced
- Tucker went to OnlyBags for **$20**; our bid was $9. Even the original $14 loses. No regret at $9, but the league's price level moved: $25 for Shough, $20 Tucker, $14 A. Mitchell.
- Previously-passive teams (OnlyBags, Hit Em Wit Da Flex) started bidding. Four teams still sit at or near $100.
- Aaron Jones (knee) did not practice Wednesday; Vikings say he still has a chance, designations Friday. He is our 2MD flex and the piece in the pending A.J. Brown offer.
- FD unchanged: no pending transactions, waiver priority #1 intact.

### 2026-09-21 — Trade scan, both leagues (Yahoo rest-of-season projections, every rostered player)
- **2MD, SENT Sep 21:** Aaron Jones → phukumean for **A.J. Brown** (IR, high-ankle sprain, ~6 weeks, earliest return Week 6 Oct 18). We have an empty IR slot; phukumean has Brown clogging their bench, Jordan Mason on IR and Chris Rodriguez as RB3. Cost to us: Jones leaves the flex, Sutton plays it for 3–4 weeks.
- 2MD, checked and rejected: Murray has little trade value (his ROS proj 295 is below every team's QB1); Hall for a WR loses because Jones becomes our RB2; Henry is tied up in the pending Tucker claim.
- **FD:** no deal worth forcing. We're within ±12 of league median at every lineup slot. Only marginal idea: Shough → House of Tweez (QB1 is 27 below median) for Jadarian Price (Q) or Jalen Coker. Sean previously chose to keep Shough.
- RB-desperate teams to watch (FD): Hurting bad (RB1 -52, RB2 -31), —HA HA— (RB1 -51), Deebo (RB2 -36). Their surplus is WRs/QBs we don't need.

### 2026-09-21 — First Down: Schultz passed on
- Sean asked about Dalton Schultz; decided to skip. Same injury-contingent logic as the Tucker repricing, plus it would cost waiver priority #1 and we already carry two TEs who project higher.

### 2026-09-21 — Week 2 FINAL: 2-0 week, both teams now 1-1
- 2MinuteDrill: **W 158.58 – 140.06** over TD (1st). Stafford 35.98 on MNF (327 yds, 4 TD, 1 INT; LAR 28-6 over NYG). Taylor 29.2, Olave 22.6, A. Jones 15.5 at flex.
- First Down: **W 140.06 – 129.06** over T & T's Prenup. Nabers held to 1.1 (1 catch); Rams DEF 11.0 wasn't enough. Lamb 35.3, Kittle 18.0, Aubrey 16.0.
- Lineup call that paid: Jones over Sutton in the 2MD flex (15.5 vs 5.5, +10.0). Kittle (18.0) started at TE in FD over Andrews.

### 2026-09-21 — Tre Tucker bid
- Placed $14 on Tre Tucker (LV WR), dropping Hunter Henry. Processes Sep 23.
- **Revised to $9 by Sean.** Reason: Tucker's value depends on Bowers being out (Week 1 with Bowers: 2 catches, 27 yds), so it's a rental. $9 beats the $0 bidders, SHAWN's history and the $6 Vele price; it loses to a RocGPT-style $10+ bid, which is acceptable.
- Lesson for future bids: price contingent-role players (backup-dependent) off the Vele comp (~$6-9), not the Worthy/Mitchell comps ($11-12).
- Why $14: beats every breakout-WR comp this season ($6, $11, $12) and RocGPT's $12 pattern; avoids the $10/$12 anchors because we lose all ties; about 15% of the remaining $94. Sean OK losing him.
- Tucker's Week 2 spike (27.9 in this scoring) came with Brock Bowers out; Bowers is OUT again Week 3, so the role holds at least one more week. Yahoo-wide trend: 3,335 adds vs 258 drops.

### 2026-09-21 — Week 3 recon (written during MNF)
**2MinuteDrill: S Dot Sack vs RocGPT (0-1).** Yahoo 50/50, 117.7 vs 118.0.
- RocGPT: Mahomes, CMC, TreVeyon Henderson, McConkey, Egbuka, McBride (17.3), Worthy at flex. Brock Bowers is OUT.
- QB call: Kyler Murray cleared concussion protocol and starts @TB (proj 20.4). Stafford @DEN (proj 19.8). Too close on projection; decide on matchup (Denver defense) vs Murray's rushing floor.
- Flex: A. Jones 11.4 > Sutton 10.9 > Golden 10.0 > Vele 9.4. Keep Jones.
- Wire is thin at RB/WR. Upside stash: Tre Tucker (LV WR, 27.9 pts wk2 in this scoring, 29% ros, on waivers till Sep 23). Candidate drop: Hunter Henry (TE2; Warren is staying).
- Trade angle (optional): with Murray healthy, a QB is now surplus. Yahoo's top trade partners: 619ers (need QB/RB) and Hit Em Wit Da Flex (need QB/RB/TE). E.g. Murray → 619ers for Christian Watson / Alec Pierce.
**First Down: MacRazy vs House of Tweez (1st).** Yahoo 50/50, 127.2 vs 126.9.
- Tweez is banged up: Nico Collins OUT, DJ Moore Q, Jadarian Price Q (in their flex).
- Our close calls (all within 0.4 proj): WR3 McLaurin 9.9 vs Boston 10.1 vs Golden 10.0; flex Sutton 10.9 vs Tuten 10.9; TE Kittle 11.2 vs Andrews 10.8. J.K. Dobbins is Q.
- Wire: Wan'Dale Robinson (TEN WR, 9.2 proj, 57% ros) and Dalton Schultz (HOU TE, 26.0 wk2 with Collins out). Nothing clearly beats our bench. Hold waiver priority #1.

### 2026-09-20 — Week 2, Sunday night (MNF: NYG @ LAR left)
- First Down: MacRazy 140.06 final vs T & T's Prenup 116.06 with Nabers + Rams DEF left (need 24.01). Yahoo: 59% us. Lamb 35.3, Kittle 18.0, Aubrey 16.0; Sutton 5.5 at flex.
- 2MinuteDrill: S Dot Sack 122.60 with Stafford left vs TD 140.06 final (Stafford needs 17.47). Yahoo: 64% us. Taylor 29.2, Olave 22.6, A. Jones 15.5 at flex (Sean swapped him in for Sutton — good call).
- Both games ride on NYG @ LAR: a shootout helps both leagues.
- Trades: Sean asked to pull both offers. Hampton offer (FD) cancelled. Higgins offer (2MD) was already gone — not in trade log, most likely rejected.

### 2026-09-16 — Waivers processed
- 2MD: Vele claim won ($6, Spears dropped). Shakir fallback skipped. Both trade proposals (Higgins / Hampton) still open, no response from Bjohn or Billy.
- FD: no claims filed (by design). Wire cleared. Billy Ba Ba Ba used their claim on Vele, so the Hampton-for-McLaurin offer is now a smaller upgrade for them (WR3 9.5 → 13.7) rather than filling an empty slot. Still worth leaving open.
- FD: added Denzel Boston, dropped Spears (free agent, priority #1 intact). Sean declined the Bucs DEF stream (keeping Steelers) and kept Shough.
- Both Week 2 lineups verified on Yahoo. No starters play Thursday (DET@BUF), so nothing locks before Sunday 1:00.
- **Sunday checklist:** Kyler Murray status (IR slot if designated); Sunday-morning inactives → swap-ins are Vele/Golden (2MD), Boston/Golden (FD).

### 2026-09-15 — Week 1 post-mortem, Week 2 plan
**Results.** 0-2.
- 2MinuteDrill: lost 143.00–164.34 to JAHSHAWN GIBBS (proj 122.7 vs 125.7). 143 was 7th-best score of 12; opponent's Gibbs (43.6) + Juwan Johnson/Raiders streams did it. Stafford 5.1 (7-27 loss @SF). Olave 38.2 was ours. Regret: Golden 15.5 on bench behind Henry 5.6 at flex (+9.9, not enough).
- First Down: lost 115.72–153.06 to [Placeholder name] (proj 128.6 vs 133.5). 8th of 10 scores — a real dud: Achane 10.6, Rice 9.9, McLaurin 3.4, Andrews 8.9, Aubrey 2.0. Opp had Caleb Williams 37.3, K. Walker 34.1. Shough threw 410 yds on our bench.

**Landscape.**
- 2MD: TD (171), JAHSHAWN (164), phukumean (164) on top. FAAB nearly untouched (RocGPT $77, 619ers $98, everyone else $100). Winning bids so far $11–12; Kupp went for $0.
- FD: House of Tweez 180, Hurting bad 177 (lost). MacRazy holds **waiver priority #1**.

**Roster reads (Yahoo team analysis).** 2MD: strengths RB/TE/K, weakness WR. FD: weaknesses TE/flex/DEF; real hole is RB2 (J. Love 11.8 then Tuten/Dobbins/Spears < 9.5).

**Actions taken (in Yahoo, via Claude in Chrome).**
- FD: a pending "Add Hunter Henry, drop Spears" claim appeared on MacRazy during the session; origin unclear. Sean cancelled it to keep waiver priority #1.
- 2MD: moved Sutton to W/R/T, benched Henry.
- 2MD: waiver claim $6 Vele / drop Spears. (Sean added the $3 Shakir fallback himself.)
- 2MD: proposed trade to CaliBayBoi510 — Higgins for A. Jones + Henry, with note.
- FD: lineup set — Sutton to flex (Tuten benched), Kittle to TE (Andrews benched).
- FD: proposed trade to Billy Ba Ba Ba — Hampton for McLaurin, with note.
- FD: no waiver claims filed on purpose; FA adds (Bucs DEF, Vele/Boston) scheduled for Wed Sep 17 after the wire clears, to preserve waiver priority #1.

**Corrections.** First draft of the recap had the 2MD box-score columns flipped (Lawrence/Godwin/P. Washington are JAHSHAWN's; Olave/G. Wilson are ours; we carry two TEs, not three). Fixed in the analysis above.

**Working agreement.** Claude gives step-by-step instructions with rationale; executes on Yahoo only when Sean explicitly asks for that specific move, and verifies the review screen before clicking send. Projections are treated as a mean, not the answer — argue from role, target share, scoring rules and ceiling.

---

## Things to keep track of
- FAAB spent (2MD): $20 of $100 — Vele $6 (Sep 16), Michael Wilson $14 (Sep 26). **$80 left.** Lost Tucker at $9 (went for $20).

### 2MinuteDrill FAAB market (all winning bids, 2026)
**Week 3 market jumped sharply** (Sep 23): Shough $25 ($KB), Tre Tucker $20 (OnlyBags), Adonai Mitchell $14 (SHAWN), Jonah Coleman $8 (SHAWN), Kyle Pitts $7 (Hit Em), Wicks $6 (SHAWN), Chiefs DEF $5 (OnlyBags). Teams that had never bid (OnlyBags, Hit Em) are now spending. Recalibrate: Week 1-2 comps ($6-12) are stale; breakout skill players now cost $20+.
Rules: FAB, $100 budget, 2-day waivers, **continual rolling-list tiebreak** (we are 12th of 12 as of Sep 21, so every tie loses; avoid round numbers).
| Date | Player | Winner | Bid |
|---|---|---|---|
| Sep 9 | Xavier Worthy WR | RocGPT | $12 |
| Sep 9 | Keaton Mitchell RB | RocGPT | $11 |
| Sep 9 | Cooper Kupp WR | Sacala | $0 |
| Sep 9 | Jordan James RB | 619ers | $0 |
| Sep 12 | J.K. Dobbins RB | 619ers | $2 |
| Sep 16 | George Kittle TE | 619ers | $27 |
| Sep 16 | Devaughn Vele WR | S Dot Sack | $6 (tie won on tiebreak; inferred from list movement) |
| Sep 16 | 49ers DEF | SHAWN | $4 |
| Sep 16 | Shakir / Iosivas WR, Mevis K | Sacala / $KB | $0 |
Budgets Sep 21: TD 100, SHAWN 96, phukumean 100, Duffel 100, Hit Em 100, $KB 100, RocGPT 77, 619ers 71, us 94, OnlyBags 100, Cali 100, Sacala 100.
Tendencies: RocGPT = aggressive on WR/RB breakouts ($11–12); 619ers = pays for names ($27 Kittle); Sacala/$KB = $0 bidders; SHAWN = FA streamer, small bids; TD, phukumean, Duffel, OnlyBags have never bid.
No prior-season data reachable (no history link on Yahoo; API is 403).
- Waiver priority (FD): #1, intact (stray Henry claim cancelled Sep 15).
- Trades proposed: 3. Accepted: 0. Sep 15 offers closed Sep 20. All three closed with no acceptances (Higgins gone/likely rejected, Hampton and Brown withdrawn).
- Yahoo API scope fix: not done.

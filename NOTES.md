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

## Open items / pending

### 2MinuteDrill
- [x] **Waiver 1 (Sep 16): WON** — Devaughn Vele added for $6, Tyjae Spears dropped. FAAB now $94.
- [x] **Waiver 2 (Sep 16):** Shakir claim skipped, as designed (same drop as claim 1).
- [x] ~~**Trade proposed (Sep 15) to CaliBayBoi510:** Tee Higgins for Aaron Jones + Hunter Henry.~~ **Closed by Sep 20**: no longer pending when Sean asked to withdraw it; not in the league trade log, so Bjohn most likely rejected it (Yahoo doesn't log rejections).
      If declined → resend for Stefon Diggs, then Jameson Williams.
- [ ] **Waiver (Sep 23): $14 Tre Tucker, drop Hunter Henry.** See FAAB log below.
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
- [x] ~~**Trade proposed (Sep 15) to Billy Ba Ba Ba:** Omarion Hampton for Terry McLaurin~~ **Withdrawn Sep 20 at Sean's request.** (they have an EMPTY WR3 slot and six RBs). If declined → Sutton + Golden for TreVeyon Henderson, then RJ Harvey.
- [ ] Trade 2: McLaurin + Golden → T & T's Prenup for Bucky Irving.
- [ ] Trade 3: Sutton + Dobbins → —HA HA— for Chuba Hubbard (Spears is gone).
- Deebo and Hurting bad are chasing the same RBs → send the Hampton offer first.

---

## Log

### 2026-09-21 — Week 2 FINAL: 2-0 week, both teams now 1-1
- 2MinuteDrill: **W 158.58 – 140.06** over TD (1st). Stafford 35.98 on MNF (327 yds, 4 TD, 1 INT; LAR 28-6 over NYG). Taylor 29.2, Olave 22.6, A. Jones 15.5 at flex.
- First Down: **W 140.06 – 129.06** over T & T's Prenup. Nabers held to 1.1 (1 catch); Rams DEF 11.0 wasn't enough. Lamb 35.3, Kittle 18.0, Aubrey 16.0.
- Lineup call that paid: Jones over Sutton in the 2MD flex (15.5 vs 5.5, +10.0). Kittle (18.0) started at TE in FD over Andrews.

### 2026-09-21 — Tre Tucker bid
- Placed $14 on Tre Tucker (LV WR), dropping Hunter Henry. Processes Sep 23.
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
- FAAB spent (2MD): $6 of $100 (Vele, Sep 16). $94 left. Pending: $14 Tucker (Sep 23).

### 2MinuteDrill FAAB market (all winning bids, 2026)
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
- Trades proposed: 2 (Sep 15). Accepted: 0. Both closed Sep 20 (Higgins offer gone/likely rejected; Hampton offer withdrawn). No open offers.
- Yahoo API scope fix: not done.

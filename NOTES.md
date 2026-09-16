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
- [ ] **Trade proposed (Sep 15) to CaliBayBoi510:** Tee Higgins for Aaron Jones + Hunter Henry.
      If declined → resend for Stefon Diggs, then Jameson Williams.
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
- [ ] **Trade proposed (Sep 15) to Billy Ba Ba Ba:** Omarion Hampton for Terry McLaurin (they have an EMPTY WR3 slot and six RBs). If declined → Sutton + Golden for TreVeyon Henderson, then RJ Harvey.
- [ ] Trade 2: McLaurin + Golden → T & T's Prenup for Bucky Irving.
- [ ] Trade 3: Sutton + Dobbins → —HA HA— for Chuba Hubbard (Spears is gone).
- Deebo and Hurting bad are chasing the same RBs → send the Hampton offer first.

---

## Log

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
- FAAB spent (2MD): $6 of $100 (Vele, Sep 16). $94 left.
- Waiver priority (FD): #1, intact (stray Henry claim cancelled Sep 15).
- Trades proposed: 2 (2MD → CaliBayBoi510 for Higgins; FD → Billy Ba Ba Ba for Hampton; both Sep 15). Trades accepted: 0.
- Yahoo API scope fix: not done.

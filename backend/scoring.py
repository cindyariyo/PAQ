"""
Engagement Level Classification — Post-Study Analysis Script
============================================================
Computes High / Moderate / Low engagement per participant per session.

Classification rules (adjust thresholds to suit your judgment):

  HIGH      session completed
            AND avg time on task >= 15s  (shows deliberate effort)
            AND questionnaire avg >= 3.5

  MODERATE  session completed
            AND (avg time >= 10s OR questionnaire avg >= 3.0)

  LOW       session not completed
            OR avg time < 10s
            OR questionnaire avg < 3.0

Questionnaire avg = mean of: enjoyment, effort, focused, motivated, satisfied
(excludes frustration and challenge which are not direct engagement indicators)

Run from the backend folder:
    python analyse_engagement.py
"""

import sqlite3
import csv
import statistics

DB_PATH = "fyp.db"
OUT_CSV = "engagement_classifications.csv"

# ── Thresholds (adjust these) ──
HIGH_TIME     = 15    # seconds avg per question
MOD_TIME      = 10
HIGH_Q_AVG    = 3.5   # questionnaire average
MOD_Q_AVG     = 3.0

ENGAGEMENT_ITEMS = ["enjoyment", "effort", "focused", "motivated", "satisfied"]


def classify(completed, avg_time, q_avg):
    if not completed:
        return "Low"
    if avg_time >= HIGH_TIME and q_avg >= HIGH_Q_AVG:
        return "High"
    if avg_time >= MOD_TIME or q_avg >= MOD_Q_AVG:
        return "Moderate"
    return "Low"


def run():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Pull all completed sessions with user + hexad info
    cur.execute("""
        SELECT
            s.id          AS session_id,
            s.session_number,
            s.completed,
            s.questions_answered,
            s.first_attempt_correct,
            s.difficulty_level_used,
            s.starting_difficulty,
            u.display_name,
            u.id          AS user_id,
            p.hexad_type
        FROM sessions s
        JOIN users u          ON u.id = s.user_id
        JOIN user_profiles p  ON p.user_id = s.user_id
        ORDER BY u.id, s.session_number
    """)
    sessions = cur.fetchall()

    rows = []
    for s in sessions:
        sid = s["session_id"]

        # ── Avg time on task (first attempts only, no skips) ──
        cur.execute("""
            SELECT time_spent_seconds FROM attempts
            WHERE session_id = ? AND retry_count = 0 AND skipped = 0
        """, (sid,))
        times = [r[0] for r in cur.fetchall() if r[0] is not None]
        avg_time = statistics.mean(times) if times else 0

        # ── Questionnaire average ──
        cur.execute("""
            SELECT enjoyment, effort, focused, motivated, satisfied
            FROM questionnaire_responses WHERE session_id = ?
        """, (sid,))
        qr = cur.fetchone()
        if qr:
            scores = [qr[k] for k in ENGAGEMENT_ITEMS if qr[k] is not None]
            q_avg = statistics.mean(scores) if scores else 0
            enjoyment   = qr["enjoyment"]
            frustration_row = cur.execute(
                "SELECT frustration, challenge FROM questionnaire_responses WHERE session_id=?", (sid,)
            ).fetchone()
            frustration = frustration_row["frustration"] if frustration_row else None
            challenge   = frustration_row["challenge"]   if frustration_row else None
        else:
            q_avg = 0
            enjoyment = frustration = challenge = None

        level = classify(bool(s["completed"]), avg_time, q_avg)

        accuracy = (
            round(100 * s["first_attempt_correct"] / s["questions_answered"], 1)
            if s["questions_answered"] > 0 else 0
        )

        rows.append({
            "display_name":       s["display_name"],
            "user_id":            s["user_id"],
            "hexad_type":         s["hexad_type"],
            "session_number":     s["session_number"],
            "completed":          bool(s["completed"]),
            "avg_time_s":         round(avg_time, 1),
            "questionnaire_avg":  round(q_avg, 2),
            "enjoyment":          enjoyment,
            "frustration":        frustration,
            "challenge":          challenge,
            "first_try_accuracy": accuracy,
            "end_difficulty":     s["difficulty_level_used"],
            "engagement_level":   level,
        })

    conn.close()

    # ── Print to console ──
    print(f"\n{'Name':<18} {'Hexad':<14} {'S#':>2}  {'Done':>4}  {'AvgT':>5}s  "
          f"{'Q_avg':>5}  {'Acc%':>5}  {'Lvl':>3}  Engagement")
    print("-" * 90)
    for r in rows:
        print(f"{r['display_name']:<18} {r['hexad_type']:<14} {r['session_number']:>2}  "
              f"{'Y' if r['completed'] else 'N':>4}  {r['avg_time_s']:>5}  "
              f"{r['questionnaire_avg']:>5}  {r['first_try_accuracy']:>5}  "
              f"{r['end_difficulty']:>3}  {r['engagement_level']}")

    # ── Summary by Hexad type ──
    from collections import defaultdict
    by_hexad = defaultdict(list)
    for r in rows:
        by_hexad[r["hexad_type"]].append(r["engagement_level"])

    print("\n-- Engagement distribution by Hexad type --")
    for hexad, levels in sorted(by_hexad.items()):
        h = levels.count("High")
        m = levels.count("Moderate")
        l = levels.count("Low")
        print(f"  {hexad:<14}  High={h}  Moderate={m}  Low={l}  (n={len(levels)} sessions)")

    # ── Write CSV ──
    if rows:
        with open(OUT_CSV, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        print(f"\n[OK] Saved {OUT_CSV} ({len(rows)} rows)")
    else:
        print("\n[!] No session data found.")


if __name__ == "__main__":
    run()

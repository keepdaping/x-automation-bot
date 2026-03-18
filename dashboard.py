"""
X Bot Growth Dashboard - generates an HTML report from bot data.

Usage: python dashboard.py
Opens a dashboard in your browser showing bot performance stats.
"""

import sqlite3
import json
import os
import webbrowser
from datetime import datetime, timedelta, date
from pathlib import Path
from database import get_recent_conversions, get_conversion_stats, init_conversion_tracking


def get_db_stats(db_path="data/bot.db"):
    """Pull stats from main bot database."""
    if not os.path.exists(db_path):
        return {"posts": [], "follows": {}, "recent_posts": []}

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Total posts
    cur.execute("SELECT COUNT(*) FROM posts")
    total_posts = cur.fetchone()[0]

    # Posts by pillar
    try:
        cur.execute("SELECT pillar, COUNT(*) FROM posts WHERE pillar IS NOT NULL AND pillar != '' GROUP BY pillar")
        posts_by_pillar = {row[0]: row[1] for row in cur.fetchall()}
    except Exception:
        posts_by_pillar = {}

    # Posts per day (last 30 days)
    cur.execute("""
        SELECT DATE(created_at) as day, COUNT(*) 
        FROM posts 
        WHERE created_at >= DATE('now', '-30 days')
        GROUP BY day ORDER BY day
    """)
    posts_per_day = [{"date": row[0], "count": row[1]} for row in cur.fetchall()]

    # Recent posts (last 10)
    cur.execute("SELECT topic, format, score, created_at FROM posts ORDER BY created_at DESC LIMIT 10")
    recent_posts = [{"topic": r[0], "format": r[1], "score": r[2], "date": r[3]} for r in cur.fetchall()]

    # Follow stats
    try:
        cur.execute("SELECT COUNT(*) FROM follows WHERE unfollowed_at IS NULL")
        active_follows = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM follows WHERE unfollowed_at IS NOT NULL")
        unfollowed = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM follows")
        total_followed = cur.fetchone()[0]
    except Exception:
        active_follows = 0
        unfollowed = 0
        total_followed = 0

    conn.close()

    return {
        "total_posts": total_posts,
        "posts_by_pillar": posts_by_pillar,
        "posts_per_day": posts_per_day,
        "recent_posts": recent_posts,
        "active_follows": active_follows,
        "unfollowed": unfollowed,
        "total_followed": total_followed,
    }


def get_rate_limiter_stats(db_path="data/rate_limiter.db"):
    """Pull stats from rate limiter database."""
    if not os.path.exists(db_path):
        return {"daily_totals": [], "today": {}}

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Today's summary
    today = date.today().isoformat()
    try:
        cur.execute("SELECT likes, replies, follows, unfollows, posts, quotes, errors FROM daily_summary WHERE date = ?", (today,))
        row = cur.fetchone()
        if row:
            today_stats = {"likes": row[0], "replies": row[1], "follows": row[2], "unfollows": row[3], "posts": row[4], "quotes": row[5], "errors": row[6]}
        else:
            today_stats = {"likes": 0, "replies": 0, "follows": 0, "unfollows": 0, "posts": 0, "quotes": 0, "errors": 0}
    except Exception:
        today_stats = {"likes": 0, "replies": 0, "follows": 0, "unfollows": 0, "posts": 0, "quotes": 0, "errors": 0}

    # Daily totals (last 30 days)
    try:
        cur.execute("""
            SELECT date, likes, replies, follows, unfollows, posts, quotes, errors 
            FROM daily_summary 
            WHERE date >= DATE('now', '-30 days')
            ORDER BY date
        """)
        daily_totals = [
            {"date": r[0], "likes": r[1], "replies": r[2], "follows": r[3], "unfollows": r[4], "posts": r[5], "quotes": r[6], "errors": r[7]}
            for r in cur.fetchall()
        ]
    except Exception:
        daily_totals = []

    # Total actions all time
    try:
        cur.execute("SELECT COUNT(*) FROM action_history WHERE success = TRUE")
        total_actions = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM action_history WHERE success = FALSE")
        total_errors = cur.fetchone()[0]
    except Exception:
        total_actions = 0
        total_errors = 0

    conn.close()

    return {
        "today": today_stats,
        "daily_totals": daily_totals,
        "total_actions": total_actions,
        "total_errors": total_errors,
    }


def generate_html(bot_stats, rate_stats, conv_stats=None, recent_conv=None):
    """Generate the dashboard HTML."""
    today = rate_stats["today"]
    total_today = sum(v for k, v in today.items() if k != "errors")

    # Prepare chart data
    daily_dates = json.dumps([d["date"] for d in rate_stats["daily_totals"]])
    daily_likes = json.dumps([d["likes"] for d in rate_stats["daily_totals"]])
    daily_replies = json.dumps([d["replies"] for d in rate_stats["daily_totals"]])
    daily_follows = json.dumps([d["follows"] for d in rate_stats["daily_totals"]])
    daily_quotes = json.dumps([d.get("quotes", 0) for d in rate_stats["daily_totals"]])

    pillar_names = json.dumps(list(bot_stats["posts_by_pillar"].keys())) if bot_stats["posts_by_pillar"] else '[]'
    pillar_counts = json.dumps(list(bot_stats["posts_by_pillar"].values())) if bot_stats["posts_by_pillar"] else '[]'

    recent_rows = ""
    for p in bot_stats["recent_posts"]:
        recent_rows += f'<tr><td>{p["date"] or "—"}</td><td>{p["topic"] or "—"}</td><td>{p["format"] or "—"}</td><td>{p["score"] or 0:.1f}</td></tr>\n'

    success_rate = 0
    if rate_stats["total_actions"] + rate_stats["total_errors"] > 0:
        success_rate = round(rate_stats["total_actions"] / (rate_stats["total_actions"] + rate_stats["total_errors"]) * 100, 1)

    # Conversion pipeline data
    if conv_stats is None:
        conv_stats = {"total": 0, "high_intent": 0, "curiosity_replies": 0}
    if recent_conv is None:
        recent_conv = []
    conv_total = conv_stats.get("total", 0)
    conv_high = conv_stats.get("high_intent", 0)
    conv_curiosity = conv_stats.get("curiosity_replies", 0)

    conv_rows = ""
    for c in recent_conv:
        ic = "red" if c["intent_score"] == 3 else "orange"
        d = c["date"][:10] if c["date"] else "\u2014"
        tw = (c["tweet"][:80] + "...") if c["tweet"] and len(c["tweet"]) > 80 else (c["tweet"] or "\u2014")
        rp = (c["reply"][:80] + "...") if c["reply"] and len(c["reply"]) > 80 else (c["reply"] or "\u2014")
        conv_rows += f"""<tr><td>{d}</td><td class=\"{ic}\">{c["intent_label"]}</td><td>{c["reply_type"]}</td><td>{c["keyword"]}</td><td>{tw}</td><td>{rp}</td></tr>\n"""
    if not conv_rows:
        conv_rows = '<tr><td colspan="6" style="color:#666">No high-intent engagements yet</td></tr>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>X Bot Dashboard - @KeepdapingB</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0a0a; color: #e0e0e0; padding: 20px; }}
.header {{ text-align: center; margin-bottom: 30px; }}
.header h1 {{ font-size: 28px; color: #1da1f2; }}
.header p {{ color: #666; margin-top: 5px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 30px; }}
.card {{ background: #1a1a1a; border-radius: 12px; padding: 20px; border: 1px solid #2a2a2a; }}
.card .label {{ font-size: 12px; color: #888; text-transform: uppercase; letter-spacing: 1px; }}
.card .value {{ font-size: 32px; font-weight: 700; margin-top: 5px; }}
.card .sub {{ font-size: 13px; color: #666; margin-top: 3px; }}
.blue {{ color: #1da1f2; }}
.green {{ color: #17bf63; }}
.orange {{ color: #ffad1f; }}
.red {{ color: #e0245e; }}
.purple {{ color: #794bc4; }}
.chart-container {{ background: #1a1a1a; border-radius: 12px; padding: 20px; border: 1px solid #2a2a2a; margin-bottom: 20px; }}
.chart-container h3 {{ margin-bottom: 15px; color: #ccc; }}
.two-col {{ display: grid; grid-template-columns: 2fr 1fr; gap: 20px; margin-bottom: 20px; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #2a2a2a; font-size: 13px; }}
th {{ color: #888; text-transform: uppercase; font-size: 11px; letter-spacing: 1px; }}
.footer {{ text-align: center; color: #444; font-size: 12px; margin-top: 30px; }}
@media (max-width: 768px) {{ .two-col {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<div class="header">
    <h1>X Bot Dashboard</h1>
    <p>@KeepdapingB &middot; Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
</div>

<div class="grid">
    <div class="card">
        <div class="label">Today's Actions</div>
        <div class="value blue">{total_today}</div>
        <div class="sub">{today['errors']} errors</div>
    </div>
    <div class="card">
        <div class="label">Likes Today</div>
        <div class="value green">{today['likes']}</div>
        <div class="sub">of 20 daily limit</div>
    </div>
    <div class="card">
        <div class="label">Replies Today</div>
        <div class="value orange">{today['replies']}</div>
        <div class="sub">of 5 daily limit</div>
    </div>
    <div class="card">
        <div class="label">Follows Today</div>
        <div class="value purple">{today['follows']}</div>
        <div class="sub">of 10 daily limit</div>
    </div>
    <div class="card">
        <div class="label">Quotes Today</div>
        <div class="value blue">{today['quotes']}</div>
        <div class="sub">of 2 daily limit</div>
    </div>
    <div class="card">
        <div class="label">Total Posts</div>
        <div class="value green">{bot_stats['total_posts']}</div>
        <div class="sub">all time</div>
    </div>
    <div class="card">
        <div class="label">Active Follows</div>
        <div class="value purple">{bot_stats['active_follows']}</div>
        <div class="sub">{bot_stats['unfollowed']} unfollowed</div>
    </div>
    <div class="card">
        <div class="label">Success Rate</div>
        <div class="value green">{success_rate}%</div>
        <div class="sub">{rate_stats['total_actions']} total actions</div>
    </div>
</div>

<div class="two-col">
    <div class="chart-container">
        <h3>Daily Activity (Last 30 Days)</h3>
        <canvas id="activityChart"></canvas>
    </div>
    <div class="chart-container">
        <h3>Posts by Pillar</h3>
        <canvas id="pillarChart"></canvas>
    </div>
</div>

<div class="chart-container">
    <h3>Recent Posts</h3>
    <table>
        <tr><th>Date</th><th>Topic</th><th>Format</th><th>Score</th></tr>
        {recent_rows if recent_rows else '<tr><td colspan="4" style="color:#666">No posts yet</td></tr>'}
    </table>
</div>

<div class="chart-container">
    <h3>Lead Pipeline (Last 7 Days)</h3>
    <div class="grid" style="margin-bottom:15px">
        <div class="card"><div class="label">Tracked Engagements</div><div class="value blue">{conv_total}</div></div>
        <div class="card"><div class="label">High Intent</div><div class="value red">{conv_high}</div></div>
        <div class="card"><div class="label">Curiosity Replies</div><div class="value orange">{conv_curiosity}</div></div>
    </div>
    <table>
        <tr><th>Date</th><th>Intent</th><th>Type</th><th>Keyword</th><th>Their Tweet</th><th>Your Reply</th></tr>
        {conv_rows}
    </table>
</div>

<div class="footer">X Automation Bot v2 &middot; Powered by Claude AI</div>

<script>
const activityCtx = document.getElementById('activityChart').getContext('2d');
new Chart(activityCtx, {{
    type: 'bar',
    data: {{
        labels: {daily_dates},
        datasets: [
            {{ label: 'Likes', data: {daily_likes}, backgroundColor: '#17bf63' }},
            {{ label: 'Replies', data: {daily_replies}, backgroundColor: '#ffad1f' }},
            {{ label: 'Follows', data: {daily_follows}, backgroundColor: '#794bc4' }},
            {{ label: 'Quotes', data: {daily_quotes}, backgroundColor: '#1da1f2' }},
        ]
    }},
    options: {{
        responsive: true,
        scales: {{
            x: {{ stacked: true, grid: {{ color: '#2a2a2a' }}, ticks: {{ color: '#888' }} }},
            y: {{ stacked: true, grid: {{ color: '#2a2a2a' }}, ticks: {{ color: '#888' }} }}
        }},
        plugins: {{ legend: {{ labels: {{ color: '#ccc' }} }} }}
    }}
}});

const pillarCtx = document.getElementById('pillarChart').getContext('2d');
new Chart(pillarCtx, {{
    type: 'doughnut',
    data: {{
        labels: {pillar_names},
        datasets: [{{ data: {pillar_counts}, backgroundColor: ['#1da1f2', '#17bf63', '#ffad1f', '#794bc4', '#e0245e'] }}]
    }},
    options: {{
        responsive: true,
        plugins: {{ legend: {{ labels: {{ color: '#ccc' }} }} }}
    }}
}});
</script>
</body>
</html>"""
    return html


def main():
    print("Generating dashboard...")
    init_conversion_tracking()
    bot_stats = get_db_stats()
    rate_stats = get_rate_limiter_stats()
    conv_stats = get_conversion_stats()
    recent_conv = get_recent_conversions(days=7, limit=20)
    html = generate_html(bot_stats, rate_stats, conv_stats, recent_conv)

    output_path = os.path.join(os.getcwd(), "dashboard.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Dashboard saved to: {output_path}")
    webbrowser.open(f"file://{output_path}")
    print("Opened in browser!")


if __name__ == "__main__":
    main()

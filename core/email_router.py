"""
Email routing — send opening results as an HTML digest.
Uses Gmail SMTP with an app password.

Environment variables required (in .env):
    GMAIL_ADDRESS       your Gmail address
    GMAIL_APP_PASSWORD  Gmail app password (not your login password)
"""

import os
import smtplib
from email.mime.text import MIMEText


def send_results_email(to_email: str, results: list, query: str) -> bool:
    """
    Send a formatted HTML digest of opening results.
    Returns True if sent, False if skipped or failed.
    """
    if not to_email:
        return False

    gmail_address  = os.environ.get("GMAIL_ADDRESS", "")
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD", "")

    if not gmail_address or not gmail_password:
        print("Email skipped — GMAIL_ADDRESS or GMAIL_APP_PASSWORD not set in .env")
        return False

    if not results:
        print(f"No results to send for: {query}")
        return False

    rows = "".join([
        f"""
        <tr>
          <td style="padding:8px;border-bottom:1px solid #eee">{r.get('business_name') or '—'}</td>
          <td style="padding:8px;border-bottom:1px solid #eee">{r.get('business_type') or '—'}</td>
          <td style="padding:8px;border-bottom:1px solid #eee">{r.get('location_details') or '—'}</td>
          <td style="padding:8px;border-bottom:1px solid #eee">{(r.get('opening_qualifier') or '—').replace('_', ' ')}</td>
          <td style="padding:8px;border-bottom:1px solid #eee">{r.get('opening_date') or '—'}</td>
          <td style="padding:8px;border-bottom:1px solid #eee">
            {'<a href="' + r["source_url"] + '">Source</a>' if r.get('source_url') else '—'}
          </td>
        </tr>
        """
        for r in results
    ])

    html = f"""
    <html><body style="font-family:sans-serif;color:#333">
      <h2 style="margin-bottom:4px">New business openings</h2>
      <p style="color:#666;margin-top:0">Query: <em>{query}</em> — {len(results)} result(s)</p>
      <table style="border-collapse:collapse;width:100%;font-size:14px">
        <thead>
          <tr style="background:#f5f5f5">
            <th style="padding:8px;text-align:left">Business</th>
            <th style="padding:8px;text-align:left">Type</th>
            <th style="padding:8px;text-align:left">Location</th>
            <th style="padding:8px;text-align:left">Status</th>
            <th style="padding:8px;text-align:left">Opening date</th>
            <th style="padding:8px;text-align:left">Source</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
      <p style="color:#999;font-size:12px;margin-top:24px">
        Powered by CatchAll Web Search API — platform.newscatcherapi.com
      </p>
    </body></html>
    """

    msg = MIMEText(html, "html")
    msg["Subject"] = f"New openings: {query} ({len(results)} results)"
    msg["From"]    = gmail_address
    msg["To"]      = to_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(gmail_address, gmail_password)
            smtp.send_message(msg)
        print(f"Email sent to {to_email} — {len(results)} results")
        return True
    except smtplib.SMTPAuthenticationError:
        print("Email failed — check GMAIL_APP_PASSWORD in .env")
        return False
    except smtplib.SMTPException as e:
        print(f"Email failed: {e}")
        return False

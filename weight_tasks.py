import os
import sys
from datetime import datetime, timedelta

import click
import numpy as np
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from scipy.stats.qmc import LatinHypercube

CALID = "8613ae622bde6968390c679f93c71db54103a6256ce7e3969b41758ccaf0005a@group.calendar.google.com"

SCOPES = ["https://www.googleapis.com/auth/calendar"]

NUM_POINTS = 10
MAXMIN = 1000

DAY_DATA = [
    ("Sunday", 630, 2030),
    ("Monday", 500, 800, 1615, 2030),
    ("Tuesday", 500, 800, 1615, 1700, 1900, 2030),
    ("Wednesday", 500, 800, 1615, 2030),
    ("Thursday", 500, 800, 1615, 2030),
    ("Friday", 500, 2030),
    ("Saturday", 630, 2030),
]


@click.command()
@click.option(
    "--auth/--no-auth",
    default=False,
    help=(
        "If enabled, only re-loads credentials to maintain valid tokens for"
        " future execution."
    ),
)
def main(auth):

    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    if auth:
        return 0

    service = build("calendar", "v3", credentials=creds)

    events = service.events().list(calendarId=CALID).execute()
    items = events.get("items", [])

    for item in items:
        if item["summary"] == "Weight":
            service.events().delete(
                calendarId=CALID, eventId=item["id"]
            ).execute()

    gen = LatinHypercube(2)

    day_min_integers = gen.integers(
        l_bounds=(0, 0), u_bounds=(7, MAXMIN), n=NUM_POINTS
    )

    for day, min in day_min_integers:

        day_datum = DAY_DATA[day]

        now = datetime.now()
        weekday = now.weekday()
        date = now + timedelta(days=int(6 - weekday + day))

        intervals = np.array([
            date.replace(
                hour=t // 100, minute=t % 100, second=0, microsecond=0
            )
            for t in day_datum[1:]
        ])
        num_intervals = len(intervals) // 2
        intervals = intervals.reshape(
            (num_intervals, 2),
        )

        total_time = timedelta()
        for start, end in intervals:
            total_time += end - start

        time_left = min / MAXMIN * total_time
        for start, end in intervals:
            if end - start < time_left:
                time_left -= end - start
            else:
                break

        time = (start + time_left).isoformat()

        event = {
            "summary": "Weight",
            "start": {
                "dateTime": time,
                "timeZone": "America/New_York",
            },
            "end": {
                "dateTime": time,
                "timeZone": "America/New_York",
            },
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {
                        "method": "popup",
                        "minutes": 0,
                    },
                    {
                        "method": "email",
                        "minutes": 0,
                    },
                ],
            },
        }

        event = service.events().insert(calendarId=CALID, body=event).execute()
        print("Event created: %s" % (event.get("htmlLink")))


if __name__ == "__main__":
    sys.exit(main())

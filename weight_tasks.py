import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Union

import click
import numpy as np
from google.auth.transport.requests import Request  # type: ignore
from google.oauth2.credentials import Credentials  # type: ignore
from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
from googleapiclient.discovery import build  # type: ignore
from scipy.stats.qmc import LatinHypercube  # type: ignore

logging.basicConfig(level=logging.INFO)

LOG = logging.getLogger("weight_tasks")

CALID: str = (
    "8613ae622bde6968390c679f93c71db54103a6256ce7e3969b41758ccaf0005a@group.calendar.google.com"
)

SCOPES: list[str] = ["https://www.googleapis.com/auth/calendar"]

NUM_POINTS: int = 10
MAXMIN: int = 1000

DAY_DATA: list[tuple[Union[str, int], ...]] = [
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
    help="If enabled, only re-loads credentials to maintain valid tokens for future execution.",
)
@click.option(
    "--verbose/--no-verbose",
    default=False,
    help="Enables debug logging.",
)
def main(auth: bool, verbose: bool) -> int:

    if verbose:
        LOG.setLevel(logging.DEBUG)

    LOG.info("Current time: %s", datetime.now())
    LOG.debug(f"{auth=}")

    creds = None
    if os.path.exists("token.json"):
        LOG.info("Token file exists, reading creds from file")
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        LOG.warning("Creds invalid!")
        if creds and creds.expired and creds.refresh_token:
            LOG.info("Attempting to refresh creds")
            creds.refresh(Request())
        else:
            LOG.info("Asking user to re-authenticate")
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)

        LOG.info("Creds valid!")
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    if auth:
        LOG.info("Re-authentication complete!")
        return 0

    service = build("calendar", "v3", credentials=creds)

    events = service.events().list(calendarId=CALID).execute()
    items = events.get("items", [])

    for item in items:
        if item["summary"] == "Weight":
            service.events().delete(calendarId=CALID, eventId=item["id"]).execute()

    gen = LatinHypercube(2)

    day_min_integers = gen.integers(l_bounds=(0, 0), u_bounds=(7, MAXMIN), n=NUM_POINTS)
    LOG.debug(f"{day_min_integers=}")

    for day, min in day_min_integers:

        day_datum = DAY_DATA[day]
        LOG.debug(f"{day_datum=}")

        now = datetime.now()
        weekday = now.weekday()
        date = now + timedelta(days=int(6 - weekday + day))
        LOG.debug(f"{date=}")

        intervals = np.array([
            date.replace(hour=t // 100, minute=t % 100, second=0, microsecond=0)
            for t in day_datum[1:]
        ])
        num_intervals = len(intervals) // 2
        intervals = intervals.reshape(
            (num_intervals, 2),
        )
        LOG.debug(f"{intervals=}")

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
        LOG.debug(f"{time=}")

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
        LOG.info("Event created: %s", event.get("htmlLink"))

    return 0


if __name__ == "__main__":
    sys.exit(main())

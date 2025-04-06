import logging
import os
import socket
import threading
import time
from datetime import date, datetime, timedelta
from typing import Union

import numpy as np
from google.oauth2.service_account import Credentials  # type: ignore
from googleapiclient.discovery import build  # type: ignore
from scipy.stats.qmc import LatinHypercube  # type: ignore

logging.basicConfig(level=logging.INFO)

LOG = logging.getLogger("weight_tasks")

CALID: str = (
    "8613ae622bde6968390c679f93c71db54103a6256ce7e3969b41758ccaf0005a@group.calendar.google.com"
)

SCOPES: list[str] = ["https://www.googleapis.com/auth/calendar"]
TOKEN: str = "/data/service_token.json"

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

SOCKET_PATH = "/tmp/unix_socket_example.sock"

if os.path.exists(SOCKET_PATH):
    os.remove(SOCKET_PATH)


def server():
    server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server_socket.bind(SOCKET_PATH)
    server_socket.listen(1)
    LOG.info("Server listening on %s", SOCKET_PATH)

    while True:
        conn, addr = server_socket.accept()
        with conn:
            LOG.info("Connected by %s", addr)
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                LOG.info("Received: %s", data.decode())
                conn.sendall(data)  # Echo back to client


def main(verbose: bool = False) -> int:

    if verbose:
        LOG.setLevel(logging.DEBUG)

    LOG.info("Current time: %s", datetime.now())

    creds = Credentials.from_service_account_file(TOKEN, scopes=SCOPES)

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
    server_thread = threading.Thread(target=server)
    server_thread.daemon = True
    server_thread.start()
    done: bool = False
    while True:
        today: date = date.today()
        now: datetime = datetime.now()
        LOG.info(f"{today=}, {now=}, {done=}")
        if not done and today.weekday() == 5 and now.hour >= 22:
            LOG.info("Generating tasks...")
            try:
                main()
            except Exception:
                LOG.exception("Exception in main():")
            done = True
        if done and today.weekday() == 6:
            LOG.info("Resetting flag...")
            done = False
        time.sleep(3600)

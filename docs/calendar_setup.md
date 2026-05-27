# Calendar Setup

The dashboard reads calendar events through a private ICS/iCal URL.

It does not connect directly to the Samsung Calendar app. Sync Samsung Calendar with Google Calendar or Outlook Calendar first, then use that calendar's private ICS link.

## Google Calendar

1. Open Google Calendar in a browser.
2. Click the gear icon.
3. Open Settings.
4. Select your calendar under `Settings for my calendars`.
5. Scroll to `Integrate calendar`.
6. Copy the `Secret address in iCal format`.
7. Paste it into `personal_dashboard.yaml`.

Example:

```yaml
personal_dashboard:
  calendar:
    enabled: true
    ics_url: "https://calendar.google.com/calendar/ical/example/basic.ics"
    cache_minutes: 30
    days_ahead: 7
    max_events: 3
```

## Outlook Calendar

1. Open Outlook Calendar in a browser.
2. Open Settings.
3. Select `View all Outlook settings`.
4. Go to `Calendar > Shared calendars`.
5. Under `Publish a calendar`, choose your calendar.
6. Select the permissions you want.
7. Copy the ICS link, not the HTML link.
8. Paste it into `personal_dashboard.yaml`.

## Security warning

A private ICS link can expose your calendar to anyone who has the URL. Do not publish it in GitHub, screenshots, issues, or logs.

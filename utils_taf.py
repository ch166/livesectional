import datetime
import pytz


# Compare current time plus offset to TAF's time period and return difference
def comp_time(zulu_time, taf_time):
    """Compare time plus offset to TAF."""
    # global current_zulu
    date_time_format = "%Y-%m-%dT%H:%M:%SZ"
    date1 = taf_time
    date2 = zulu_time
    diff = datetime.datetime.strptime(
        date1, date_time_format
    ) - datetime.datetime.strptime(date2, date_time_format)
    diff_minutes = int(diff.seconds / 60)
    diff_hours = int(diff_minutes / 60)
    return diff.seconds, diff_minutes, diff_hours, diff.days


def future_taf_time(app_conf, hr_increment):
    """Compute time hr_increment hours in the future"""
    taf_time = datetime.datetime.now(pytz.utc) + datetime.timedelta(hours=hr_increment)
    return datetime.datetime(
        taf_time.year,
        taf_time.month,
        taf_time.day,
        taf_time.hour,
        taf_time.minute,
        taf_time.second,
    )


def current_time_taf_offset(app_conf):
    """Get time for TAF period selected (UTC)."""
    offset = app_conf.get_int("rotaryswitch", "hour_to_display")
    curr_time = datetime.datetime.now(pytz.utc) + datetime.timedelta(hours=offset)
    return pytz.UTC.localize(curr_time)

# vim: set ts=4 sw=4 expandtab sts=4 fileencoding=utf-8:
# Copyright (c) 2013-2015 Christian Geier et al.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#

from __future__ import unicode_literals

from click import echo, style

import datetime
import itertools
import logging
import sys
import textwrap

from khal import aux, calendar_display
from khal.compat import to_unicode
from khal.khalendar.exceptions import ReadOnlyCalendarError
from khal.exceptions import FatalError
from khal.khalendar.event import Event
from khal import __version__, __productname__
from khal.log import logger
from .terminal import colored, get_terminal_size, merge_columns


def construct_daynames(daylist, longdateformat):
    """returns a list of tuples of datetime objects and datenames

    :param daylist: list of dates
    :type daylist: list(datetime.date)
    :param longdateformat: format in which to print dates
    :param str
    :returns: list of names and dates
    :rtype: list((str, datetime.date))
    """
    for date in daylist:
        if date == datetime.date.today():
            yield (date, 'Today:')
        elif date == datetime.date.today() + datetime.timedelta(days=1):
            yield (date, 'Tomorrow:')
        else:
            yield (date, date.strftime(longdateformat))


def get_agenda(collection, locale, dates=None,
               days=None, events=None, width=45, show_all_days=False):
    """returns a list of events scheduled for all days in daylist

    included are header "rows"
    :param collection:
    :type collection: khalendar.CalendarCollection
    :param dates: a list of all dates for which the events should be return,
                    including what should be printed as a header
    :type collection: list(str)
    :param show_all_days: True if all days must be shown, event without event
    :type show_all_days: Boolean
    :returns: a list to be printed as the agenda for the given days
    :rtype: list(str)

    """
    assert not (days is not None and events is not None)
    event_column = list()

    if days is None:
        days = 2

    if dates is None or len(dates) == 0:
        dates = [datetime.date.today()]
    else:
        try:
            dates = [
                aux.datefstr(date, locale['dateformat'], locale['longdateformat'])
                if not isinstance(date, datetime.date) else date
                for date in dates
            ]
        except aux.InvalidDate as error:
            logging.fatal(error)
            sys.exit(1)

    if days is not None:
        daylist = [date + datetime.timedelta(days=one)
                   for one in range(days) for date in dates]
        daylist.sort()

    daylist = construct_daynames(daylist, locale['longdateformat'])

    for day, dayname in daylist:
        start = datetime.datetime.combine(day, datetime.time.min)
        end = datetime.datetime.combine(day, datetime.time.max)

        # TODO unify allday and datetime events
        all_day_events = collection.get_allday_by_time_range(day)
        events = collection.get_datetime_by_time_range(start, end)
        if len(events) == 0 and len(all_day_events) == 0 and not show_all_days:
            continue

        event_column.append(style(dayname, bold=True))
        events.sort(key=lambda e: e.start)
        for event in itertools.chain(all_day_events, events):
            desc = textwrap.wrap(event.compact(day), width)
            event_column.extend([colored(d, event.color) for d in desc])

    if event_column == []:
        event_column = [style('No events', bold=True)]
    return event_column


class Calendar(object):

    def __init__(self, collection, date=[], firstweekday=0, encoding='utf-8',
                 weeknumber=False, show_all_days=False, **kwargs):
        term_width, _ = get_terminal_size()
        lwidth = 25
        rwidth = term_width - lwidth - 4
        event_column = get_agenda(
            collection, dates=date, width=rwidth, show_all_days=show_all_days,
            **kwargs)
        calendar_column = calendar_display.vertical_month(
            firstweekday=firstweekday, weeknumber=weeknumber)

        rows = merge_columns(calendar_column, event_column)
        # XXX: Generate this as a unicode in the first place, rather than
        # casting it.
        echo('\n'.join(rows).encode(encoding))


class Agenda(object):

    def __init__(self, collection, date=None, firstweekday=0, encoding='utf-8',
                 show_all_days=False, **kwargs):
        term_width, _ = get_terminal_size()
        event_column = get_agenda(collection, dates=date, width=term_width,
                                  show_all_days=show_all_days, **kwargs)
        # XXX: Generate this as a unicode in the first place, rather than
        # casting it.
        echo(to_unicode('\n'.join(event_column), encoding))


class NewFromString(object):

    def __init__(self, collection, conf, date_list, location=None, repeat=None):
        try:
            event = aux.construct_event(
                date_list,
                location=location,
                repeat=repeat,
                **conf['locale'])
        except FatalError:
            sys.exit(1)
        event = Event(event,
                      collection.default_calendar_name,
                      locale=conf['locale'],
                      )

        try:
            collection.new(event)
        except ReadOnlyCalendarError:
            logger.fatal('ERROR: Cannot modify calendar "{}" as it is '
                         'read-only'.format(collection.default_calendar_name))
            sys.exit(1)
        if conf['default']['print_new'] == 'event':
            echo(event.long())
        elif conf['default']['print_new'] == 'path':
            path = collection._calnames[event.calendar].path + event.href
            echo(path.encode(conf['locale']['encoding']))


class Interactive(object):

    def __init__(self, collection, conf):
        from . import ui
        pane = ui.ClassicView(collection,
                              conf,
                              title='select an event',
                              description='do something')
        ui.start_pane(
            pane, pane.cleanup,
            program_info='{0} v{1}'.format(__productname__, __version__)
        )

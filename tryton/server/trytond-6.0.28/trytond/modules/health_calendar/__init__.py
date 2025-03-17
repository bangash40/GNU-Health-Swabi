# SPDX-FileCopyrightText: 2008-2023 Luis Falcón <falcon@gnuhealth.org>
# SPDX-FileCopyrightText: 2011-2023 GNU Solidario <health@gnusolidario.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#########################################################################
#   Hospital Management Information System (HMIS) component of the      #
#                       GNU Health project                              #
#                   https://www.gnuhealth.org                           #
#########################################################################
#                        HEALTH CALENDAR package                        #
#                __init__.py: Package declaration file                  #
#########################################################################

from trytond.pool import Pool
from . import health_calendar
from . import wizard


def register():
    Pool.register(
        health_calendar.User,
        health_calendar.Appointment,
        wizard.CreateAppointmentStart,
        module='health_calendar', type_='model')
    Pool.register(
        wizard.CreateAppointment,
        module='health_calendar', type_='wizard')

# SPDX-FileCopyrightText: 2008-2023 Luis Falcón <falcon@gnuhealth.org>
# SPDX-FileCopyrightText: 2011-2023 GNU Solidario <health@gnusolidario.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

try:
    from trytond.modules.health_dentistry.tests.test_health_dentistry \
        import suite
except ImportError:
    from .test_health_dentistry import suite

__all__ = ['suite']

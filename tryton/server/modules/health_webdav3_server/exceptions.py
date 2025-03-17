# SPDX-FileCopyrightText: 2017-2023 GNU Solidario <health@gnusolidario.org>
# SPDX-FileCopyrightText: 2017-2023 Luis Falcon <falcon@gnuhealth.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

from trytond.model.exceptions import ValidationError


class InvalidAttachmentName(ValidationError):
    pass

# -*- coding: utf-8 -*-
##############################################################################
#
#    GNU Health: The Free Health and Hospital Information System
#    Copyright (C) 2008-2016 Luis Falcon <lfalcon@gnu.org>
#    Copyright (C) 2013  Sebastián Marro <smarro@thymbra.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from datetime import datetime, timedelta
from trytond.model import Workflow, ModelView, ModelSingleton, ModelSQL, fields
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
import logging
from decimal import Decimal
from trytond.config import config
from datetime import datetime
from trytond.pyson import Eval, Not, Bool, And, Equal, Or
from trytond.report import Report
from sql.aggregate import Max, Count, Sum
from sql import Literal, Join
from trytond.rpc import RPC
import logging
from trytond.modules.company import CompanyReport
import pytz

__all__ = ['Employee', 'Department']

__metaclass__ = PoolMeta

class Employee(metaclass=PoolMeta):
    'Employee'
    __name__ = 'company.employee'
    department =  fields.Many2One('anth.hr.department', 'Department')

class Department(ModelSQL, ModelView):
    "Department"
    __name__ = "anth.hr.department"
    name = fields.Char('Department Name', required=True)
    hod =  fields.Many2One('company.employee', 'HoD')
    store_location = fields.Many2One('stock.location', 'Store Location')
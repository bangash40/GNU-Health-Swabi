# -*- coding: utf-8 -*-
##############################################################################
#
#    GNU Health: The Free Health and Hospital Information System
#    Copyright (C) 2008-2016 Luis Falcon <lfalcon@gnusolidario.org>
#    Copyright (C) 2011-2016 GNU Solidario <health@gnusolidario.org>
#
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
from trytond.model import ModelView, fields
from trytond.modules.health_proc.health_proc import InsurancePanelBill
from trytond.wizard import Wizard, StateTransition, StateView, Button, StateAction
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.pyson import Eval, Not, Bool, PYSONEncoder, Equal, And, Or, If
import logging
from trytond.config import config
from trytond.model.exceptions import ValidationError
from trytond.modules.health.core  import (get_institution, compute_age_from_dates,
                   estimated_date_from_years,
                   get_health_professional)
from datetime import datetime, time, tzinfo


__all__ = ['PanelBillingStart', 'PreparePanelBillWizard','ShowPatientBillsStart']

class PanelBillingStart(ModelView):
    'Panel Billing'
    __name__ = 'health.proc.insurance.panel.bill.start'
    name = fields.Many2One('health.proc.insurance.panel','Panel', required=True)
        
    datefrom = fields.Date('From Date', required=True)
    dateto = fields.Date('To Date', required=True)


    @staticmethod
    def default_datefrom():
        return datetime.now()
       
    @staticmethod
    def default_dateto():
        return datetime.now()    

class ShowPatientBillsStart(ModelView):
    'List Patient Bills'
    __name__ = 'health.proc.insurance.panel.bill.show'
    

class PreparePanelBillWizard(Wizard):
    'Prepare Panel Bill Wizard'
    __name__ = 'health.proc.insurance.panel.bill.wizard'

    start = StateView('health.proc.insurance.panel.bill.start',
        'health_proc.panel_billing_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Find Bills', 'request', 'tryton-ok', default=True),
            ])
    
    open_samples_direct_ = StateAction('health_proc.act_health_proc_lab_samples_view')    
 
    request = StateTransition()

    def transition_request(self):
        # create the lab test first 
        #datefrom = datetime.combine(self.start.datefrom, time(0,0,0))
        #dateto = datetime.combine(self.start.dateto, time(23,59,59))

        datefrom = self.start.datefrom
        dateto = self.start.dateto

        pool = Pool()
        StatementLine = pool.get("account.statement.line")
        lines = StatementLine.search([('party', '=', self.start.name.name.id), ('date', '>=', datefrom) , ('date', '<=', dateto)])
        lineIds = set()
        for line in lines:
             lineIds.add(line.id)


        PanelBill = Pool().get("health.proc.insurance.panel.bill")
        bills = PanelBill.create([{'name': self.start.name.id, 'datefrom':self.start.datefrom, 
                    'dateto':self.start.dateto, 'state': 'draft'}])      
        
        StatementLine.write(lines,{'panel_bill': bills[0].id})

        return 'end'

    
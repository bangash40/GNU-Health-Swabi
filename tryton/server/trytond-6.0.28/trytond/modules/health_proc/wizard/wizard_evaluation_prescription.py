# -*- coding: utf-8 -*-
##############################################################################
#
#    GNU Health: The Free Health and Hospital Information System
#    Copyright (C) 2008-2016 Luis Falcon <lfalcon@gnusolidario.org>
#    Copyright (C) 2011-2016 GNU Solidario <health@gnusolidario.org>
#
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
from trytond.model import ModelView
from trytond.wizard import Wizard, StateTransition, StateAction, StateView, Button
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.pyson import PYSONEncoder
import logging
from trytond.model.exceptions import ValidationError


__all__ = ['CreateEvaluationPrescription']

class CreateEvaluationPrescription(Wizard):
	'Create Evaluation Prescription'
	__name__ = 'wizard.gnuhealth.evaluation.prescription'

	start_state = 'evaluation_prescription'
	evaluation_prescription = StateAction('health_proc.act_evaluation_prescription')

	def do_evaluation_prescription(self, action):
		evaluation = Transaction().context.get('active_id')
		patient = None
		diagnosis = None
		diagnosis_free_text = None
		patient_evaluation = None

		if Transaction().context.get('active_model') == 'gnuhealth.appointment':
			try:
				app_id = Pool().get('gnuhealth.appointment').browse([evaluation])[0]
				patient_evaluation = app_id.id

				patient = app_id.patient.id
			except:
				raise ValidationError("Please select an appointment to create the prescription.")

		logging.info("============================================ patient-eva " + str(patient_evaluation))

		action['pyson_domain'] = PYSONEncoder().encode([
            ('patient', '=', patient),
	    	('appointment', '=', patient_evaluation)
        ])
		
		action['pyson_context'] = PYSONEncoder().encode({
            'patient': patient,
			'appointment': patient_evaluation
        })
            
		return action, {}
        
	@classmethod
	def __setup__(cls):
		super(CreateEvaluationPrescription, cls).__setup__()
		
#!/usr/bin/env python

# SPDX-FileCopyrightText: 2008-2023 Luis Falcón <falcon@gnuhealth.org>
# SPDX-FileCopyrightText: 2011-2023 GNU Solidario <health@gnusolidario.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

#########################################################################
#   Hospital Management Information System (HMIS) component of the      #
#                       GNU Health project                              #
#                   https://www.gnuhealth.org                           #
#########################################################################
#                      HEALTH SURGERY package                           #
#                 health_surgery.py: Main module                        #
#########################################################################
import pytz
from dateutil.relativedelta import relativedelta
from trytond.model import ModelView, ModelSQL, fields, Unique
from datetime import datetime
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.pyson import Eval, Not, Equal, And
from trytond.pool import PoolMeta
from trytond.i18n import gettext

from .exceptions import (
    EndDateBeforeStart, ORNotAvailable, OperatingRoomAndDateRequired)

from trytond.modules.health.core import get_health_professional, \
    get_institution

__all__ = ['RCRI', 'Surgery', 'Operation', 'SurgerySupply',
           'PatientData',
           'SurgeryTeam', 'SurgeryComplication', 'SurgeryDrain',
           'PreOperativeAssessment', 'SurgeryProtocol']


class RCRI(ModelSQL, ModelView):
    'Revised Cardiac Risk Index'
    __name__ = 'gnuhealth.rcri'

    patient = fields.Many2One('gnuhealth.patient', 'Patient ID', required=True)
    rcri_date = fields.DateTime('Date', required=True)
    health_professional = fields.Many2One(
        'gnuhealth.healthprofessional', 'Health Professional',
        help="Health professional /"
        "Cardiologist who signed the assesment RCRI")

    rcri_high_risk_surgery = fields.Boolean(
        'High Risk surgery',
        help='Includes andy suprainguinal vascular, intraperitoneal,'
        ' or intrathoracic procedures')

    rcri_ischemic_history = fields.Boolean(
        'History of ischemic heart disease',
        help="history of MI or a positive exercise test, current \
        complaint of chest pain considered to be secondary to myocardial \
        ischemia, use of nitrate therapy, or ECG with pathological \
        Q waves; do not count prior coronary revascularization procedure \
        unless one of the other criteria for ischemic heart disease is \
        present")

    rcri_congestive_history = fields.Boolean(
        'History of congestive heart disease')

    rcri_diabetes_history = fields.Boolean(
        'Preoperative Diabetes',
        help="Diabetes Mellitus requiring treatment with Insulin")

    rcri_cerebrovascular_history = fields.Boolean(
        'History of Cerebrovascular disease')

    rcri_kidney_history = fields.Boolean(
        'Preoperative Kidney disease',
        help="Preoperative serum creatinine >2.0 mg/dL (177 mol/L)")

    rcri_total = fields.Integer(
        'Score',
        help='Points 0: Class I Very Low (0.4% complications)\n'
        'Points 1: Class II Low (0.9% complications)\n'
        'Points 2: Class III Moderate (6.6% complications)\n'
        'Points 3 or more : Class IV High (>11% complications)')

    rcri_class = fields.Selection([
        (None, ''),
        ('I', 'I'),
        ('II', 'II'),
        ('III', 'III'),
        ('IV', 'IV'),
        ], 'RCRI Class', sort=False)

    @fields.depends(
        'rcri_high_risk_surgery', 'rcri_ischemic_history',
        'rcri_congestive_history', 'rcri_diabetes_history',
        'rcri_cerebrovascular_history', 'rcri_kidney_history')
    def on_change_with_rcri_total(self):

        total = 0
        if self.rcri_high_risk_surgery:
            total = total + 1
        if self.rcri_ischemic_history:
            total = total + 1
        if self.rcri_congestive_history:
            total = total + 1
        if self.rcri_diabetes_history:
            total = total + 1
        if self.rcri_kidney_history:
            total = total + 1
        if self.rcri_cerebrovascular_history:
            total = total + 1

        return total

    @fields.depends(
        'rcri_high_risk_surgery', 'rcri_ischemic_history',
        'rcri_congestive_history', 'rcri_diabetes_history',
        'rcri_cerebrovascular_history', 'rcri_kidney_history')
    def on_change_with_rcri_class(self):
        rcri_class = ''

        total = 0
        if self.rcri_high_risk_surgery:
            total = total + 1
        if self.rcri_ischemic_history:
            total = total + 1
        if self.rcri_congestive_history:
            total = total + 1
        if self.rcri_diabetes_history:
            total = total + 1
        if self.rcri_kidney_history:
            total = total + 1
        if self.rcri_cerebrovascular_history:
            total = total + 1

        if total == 0:
            rcri_class = 'I'
        if total == 1:
            rcri_class = 'II'
        if total == 2:
            rcri_class = 'III'
        if (total > 2):
            rcri_class = 'IV'

        return rcri_class

    @staticmethod
    def default_rcri_date():
        return datetime.now()

    @staticmethod
    def default_rcri_total():
        return 0

    @staticmethod
    def default_rcri_class():
        return 'I'

    def get_rec_name(self, name):
        res = 'Points: ' + str(self.rcri_total) + ' (Class ' + \
            str(self.rcri_class) + ')'
        return res

    @classmethod
    def __setup__(cls):
        super(RCRI, cls).__setup__()
        cls._order.insert(0, ('rcri_date', 'DESC'))

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op, ('patient',) + tuple(clause[1:]), ]


class Surgery(ModelSQL, ModelView):
    'Surgery'
    __name__ = 'gnuhealth.surgery'

    def surgery_duration(self, name):

        if (self.surgery_end_date and self.surgery_date):
            return self.surgery_end_date - self.surgery_date
        else:
            return None

    def patient_age_at_surgery(self, name):
        if (self.patient.name.dob and self.surgery_date):
            rdelta = relativedelta(self.surgery_date.date(),
                                   self.patient.name.dob)
            years_months_days = str(rdelta.years) + 'y ' \
                + str(rdelta.months) + 'm ' \
                + str(rdelta.days) + 'd'
            return years_months_days
        else:
            return None

    patient = fields.Many2One('gnuhealth.patient', 'Patient', required=True)
    admission = fields.Many2One('gnuhealth.appointment', 'Admission')
    operating_room = fields.Many2One('gnuhealth.hospital.or', 'Operating Room')
    code = fields.Char('Code', readonly=True,
                       help="Health Center code / sequence")
    protocol = fields.Many2One(
        'gnuhealth.surgery.protocol', 'Protocol')

    postoperative_guidelines = fields.Text('Postoperative guidelines')

    discharge_instructions = fields.Text('Discharge Instructions')

    procedures = fields.One2Many(
        'gnuhealth.operation', 'name', 'Procedures',
        help="Procedures / Interventions done in the surgery")

    supplies = fields.One2Many(
        'gnuhealth.surgery_supply', 'name', 'Supplies',
        help="List of the supplies required for the surgery")

    pathology = fields.Many2One(
        'gnuhealth.pathology', 'Health Condition',
        help="Base Condition / Reason")

    classification = fields.Selection([
        (None, ''),
        ('o', 'Optional'),
        ('r', 'Required'),
        ('u', 'Urgent'),
        ('e', 'Emergency'),
        ], 'Urgency', help="Urgency level for this surgery", sort=False)
    surgeon = fields.Many2One(
        'gnuhealth.healthprofessional', 'Surgeon',
        help="Surgeon who did the procedure")

    anesthetist = fields.Many2One(
        'gnuhealth.healthprofessional', 'Anesthetist',
        help="Anesthetist in charge")

    surgery_date = fields.DateTime(
        'Date', help="Start of the Surgery")

    surgery_end_date = fields.DateTime(
        'End',
        states={
            'required': Equal(Eval('state'), 'done'),
            },
        help="Automatically set when the surgery is done."
             "It is also the estimated end time when"
             " confirming the surgery.")

    surgery_length = fields.Function(
        fields.TimeDelta(
            'Length',
            states={'invisible': And(Not(Equal(Eval('state'), 'done')),
                    Not(Equal(Eval('state'), 'signed')))},
            help="Length of the surgery"),
        'surgery_duration')

    ellapsed_time = fields.Integer(
        "Ellapsed time",
        help="Time in minutes of the surgery process."
             " This value is optional and is used when the automatic"
             " computed surgery length does not reflect the actual"
             " time or it has been recorded afterwards.")

    state = fields.Selection([
        ('pre_anesthesia', 'Pre-anesthisia'),
        ('ot_unfit', 'OT Unfit'),
        ('draft', 'OT Fit'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('signed', 'Signed'),
        ], 'State', readonly=True, sort=False)

    signed_by = fields.Many2One(
        'gnuhealth.healthprofessional', 'Signed by', readonly=True,
        states={
            'invisible': Not(Equal(Eval('state'), 'signed'))
            },

        help="Health Professional that signed this surgery document")

    # age is deprecated in GNU Health 2.0
    age = fields.Char(
        'Estimative Age',
        help="Use this field for historical purposes, \
        when no date of surgery is given")

    computed_age = fields.Function(
        fields.Char(
            'Age',
            help="Computed patient age at the moment of the surgery"),
        'patient_age_at_surgery')

    gender = fields.Function(fields.Selection([
        (None, ''),
        ('m', 'Male'),
        ('f', 'Female'),
        ('f-m', 'Female -> Male'),
        ('m-f', 'Male -> Female'),
        ], 'Gender'), 'get_patient_gender', searcher='search_patient_gender')

    description = fields.Char('Description')

    preop_assessment = fields.Many2One(
        'gnuhealth.preoperative_assessment', 'Preop assessment',
        domain=[('patient', '=', Eval('patient'))],
        depends=['patient'],
        help="Preoperative assessment associated to this surgery")

    preop_oximeter = fields.Boolean(
        'Pulse Oximeter in place',
        help="Pulse oximeter is in place "
        "and functioning")

    preop_site_marking = fields.Boolean(
        'Surgical Site Marking',
        help="The surgeon has marked the surgical incision")

    preop_antibiotics = fields.Boolean(
        'Antibiotic Prophylaxis',
        help="Prophylactic antibiotic treatment within the last 60 minutes")

    preop_sterility = fields.Boolean(
        'Sterility confirmed',
        help="Nursing team has confirmed sterility of the devices and room")

    """ Mallampati, ASA, bleeding risk, RCRI are now part of the
        preoperative assessment.
        They will not be shown in the main surgery view
    """

    preop_mallampati = fields.Selection([
        (None, ''),
        ('Class 1', 'Class 1: Full visibility of tonsils, uvula and soft '
                    'palate'),
        ('Class 2', 'Class 2: Visibility of hard and soft palate, '
                    'upper portion of tonsils and uvula'),
        ('Class 3', 'Class 3: Soft and hard palate and base of the uvula are '
                    'visible'),
        ('Class 4', 'Class 4: Only Hard Palate visible'),
        ], 'Mallampati Score', sort=False)
    preop_bleeding_risk = fields.Boolean(
        'Risk of Massive bleeding',
        help="Patient has a risk of losing more than 500 "
        "ml in adults of over 7ml/kg in infants. If so, make sure that "
        "intravenous access and fluids are available")

    preop_asa = fields.Selection([
        (None, ''),
        ('ps1', 'PS 1 : Normal healthy patient'),
        ('ps2', 'PS 2 : Patients with mild systemic disease'),
        ('ps3', 'PS 3 : Patients with severe systemic disease'),
        ('ps4', 'PS 4 : Patients with severe systemic disease that is'
            ' a constant threat to life '),
        ('ps5', 'PS 5 : Moribund patients who are not expected to'
            ' survive without the operation'),
        ('ps6', 'PS 6 : A declared brain-dead patient who organs are'
            ' being removed for donor purposes'),
        ], 'ASA PS',
        help="ASA pre-operative Physical Status", sort=False)

    preop_rcri = fields.Many2One(
        'gnuhealth.rcri', 'RCRI',
        help='Patient Revised Cardiac Risk Index\n'
        'Points 0: Class I Very Low (0.4% complications)\n'
        'Points 1: Class II Low (0.9% complications)\n'
        'Points 2: Class III Moderate (6.6% complications)\n'
        'Points 3 or more : Class IV High (>11% complications)')

    surgical_wound = fields.Selection([
        (None, ''),
        ('I', 'Clean . Class I'),
        ('II', 'Clean-Contaminated . Class II'),
        ('III', 'Contaminated . Class III'),
        ('IV', 'Dirty-Infected . Class IV'),
        ], 'Surgical wound', sort=False)

    anesthesia_type = fields.Selection([
        (None, ''),
        ('local', 'Local'),
        ('regional', 'Regional'),
        ('general', 'General'),
        ('sedation', 'Sedation'),
        ('rachianesthesia', 'Rachianesthesia'),
        ('epidural', 'Epidural'),
        ('peribulbar', 'Peribulbar'),
        ('regional_block', 'Regional Block'),
        ('local_sedation', 'Local + sedation'),
        ('No anesthesia', 'No anesthesia'),
        ], 'Anesthesia', sort=False)

    clavien_dindo = fields.Selection([
        (None, ''),
        ('grade1', 'Grade I'),
        ('grade2', 'Grade II'),
        ('grade3', 'Grade III'),
        ('grade3a', 'Grade IIIa'),
        ('grade3a', 'Grade IIIa'),
        ('grade4', 'Grade IV'),
        ('grade4a', 'Grade IVa'),
        ('grade4b', 'Grade IVb'),
        ('grade5', 'Grade V'),
        ], 'Clavien-Dindo', sort=False,
        help="Grade I: Any deviation from the normal postoperative "
             "course without the need for pharmacological treatment "
             "or surgical, endoscopic and radiological interventions\n"
             "Grade II: Requiring pharmacological treatment with drugs "
             "other than such allowed for grade I complications.\n"
             "Grade III: Requiring surgical, endoscopic or radiological "
             "intervention.\n"
             "  IIIa: Intervention not under general anesthesia\n"
             "  IIIb: Intervention under general anesthesia\n"
             "Grade IV: Life-threatening complication (including CNS "
             "complications) requiring IC/ICU-management.\n"
             "  IVa: single organ dysfunction (including dialysis)\n"
             "  IVb: multiorgan dysfunction\n"
             "Grade V: Death of a patient")

    patient_positioning = fields.Selection([
        (None, ''),
        ('supine_decubitus', 'Supine Decubitus'),
        ('prone_decubitus', 'Prone Decubitus'),
        ('lithotomy', 'Lithotomy'),
        ('lateral', 'Lateral'),
        ('sims', 'Sims'),
        ('fowlers', 'Fowlers'),
        ('semi_fowlers', 'Semi-Fowler'),
        ('trendelenburg', 'Trendelenburg'),
        ('reverse_trendelenburg', 'Reverse Trendelenburg'),
        ('jacknife', 'Jacknife'),
        ('knee_chest', 'Knee-chest'),
        ('lloyd_davies', 'Lloyd-Davies'),
        ('kidney', 'Kidney positioning'),
        ('other', 'Other'),
        ], 'Patient Positioning', sort=False,)

    laterality = fields.Selection([
        (None, ''),
        ('right', 'Right'),
        ('left', 'Left'),
        ('bilateral', 'Bilateral'),
        ], 'Laterality', sort=False,)

    approach = fields.Selection([
        (None, ''),
        ('open', 'Open'),
        ('laparoscopic', 'Laparoscopic'),
        ('endoscopic', 'Endoscopic'),
        ('arthroscopic', 'Arthroscopic'),
        ('robotic', 'Robotic'),
        ('other', 'other'),
        ], 'Approach', sort=False)

    surgery_complications = fields.One2Many(
        'gnuhealth.surgery.complication', 'name', 'Complications',
        help="Complications related to the surgery")

    complications_notes = fields.Text('Complications')

    drains = fields.One2Many(
        'gnuhealth.surgery.drain', 'name', 'Drains',
        help="Drains on this surgery")

    extra_info = fields.Text('Extra Info')

    anesthesia_report = fields.Text('Anesthesia Report')

    institution = fields.Many2One('gnuhealth.institution', 'Institution')

    report_surgery_date = fields.Function(fields.Date('Surgery Date'),
                                          'get_report_surgery_date')
    report_surgery_time = fields.Function(fields.Time('Surgery Time'),
                                          'get_report_surgery_time')

    surgery_team = fields.One2Many(
        'gnuhealth.surgery_team', 'name', 'Team Members',
        help="Professionals Involved in the surgery")

    postoperative_dx = fields.Many2One(
        'gnuhealth.pathology', 'Post-op dx',
        states={'invisible': And(Not(Equal(Eval('state'), 'done')),
                                 Not(Equal(Eval('state'), 'signed')))},
        help="Post-operative diagnosis")

    # Deprecated since 4.2. Now use "Surgical intervention"
    main_procedure = fields.Many2One('gnuhealth.procedure', 'Main Procedure')

    surgical_intervention = fields.Many2One(
        'gnuhealth.procedure', 'Surgical Intervention',
        help="This code reflects the main intervention of this surgery."
             "Additional procedures can be entered on the procedures tab.")

    @staticmethod
    def default_institution():
        return get_institution()

    @staticmethod
    def default_surgery_date():
        return datetime.now()

    @staticmethod
    def default_surgeon():
        surgeon = get_health_professional()
        return surgeon

    @staticmethod
    def default_state():
        return 'pre_anesthesia'

    # Fill in the default values from the protocol
    @fields.depends('protocol')
    def on_change_protocol(self):
        if (self.protocol):
            self.description = self.protocol.description
            self.extra_info = self.protocol.general_info
            self.pathology = self.protocol.pathology
            self.surgical_intervention = self.protocol.surgical_intervention
            self.classification = self.protocol.classification
            self.anesthesia_type = self.protocol.anesthesia_type
            self.patient_positioning = self.protocol.patient_positioning
            self.laterality = self.protocol.laterality
            self.postoperative_guidelines = \
                self.protocol.postoperative_guidelines
            self.discharge_instructions = self.protocol.discharge_instructions
            self.approach = self.protocol.approach

    def get_rec_name(self, name):
        res = f'{self.code} ({self.description})'
        return res

    def get_patient_gender(self, name):
        return self.patient.gender

    @classmethod
    def search_patient_gender(cls, name, clause):
        res = []
        value = clause[2]
        res.append(('patient.name.gender', clause[1], value))
        return res

    # Show the gender and age upon entering the patient
    # These two are function fields (don't exist at DB level)
    @fields.depends('patient', '_parent_patient.name')
    def on_change_patient(self):
        self.gender = self.patient.gender
        self.computed_age = self.patient.age

    @classmethod
    def generate_code(cls, **pattern):
        Config = Pool().get('gnuhealth.sequences')
        config = Config(1)
        sequence = config.get_multivalue(
            'surgery_code_sequence', **pattern)
        if sequence:
            return sequence.get()

    @classmethod
    def create(cls, vlist):
        vlist = [x.copy() for x in vlist]
        for values in vlist:
            if not values.get('code'):
                values['code'] = cls.generate_code()
        return super(Surgery, cls).create(vlist)

    @classmethod
    def __setup__(cls):
        super(Surgery, cls).__setup__()

        cls._order.insert(0, ('surgery_date', 'DESC'))

        cls._buttons.update({
            'ot_fit': {
                'invisible': Not(Equal(Eval('state'), 'pre_anesthesia')),
                },
            'ot_unfit': {
                'invisible': Not(Equal(Eval('state'), 'pre_anesthesia')),
                },
            'confirmed': {
                'invisible': And(Not(Equal(Eval('state'), 'draft')),
                                 Not(Equal(
                                     Eval('state'), 'cancelled'))),
                },
            'cancel': {
                'invisible': Not(Equal(Eval('state'), 'confirmed')),
                },
            'start': {
                'invisible': Not(Equal(Eval('state'), 'confirmed')),
                },
            'done': {
                'invisible': Not(Equal(Eval('state'), 'in_progress')),
                },
            'signsurgery': {
                'invisible': Not(Equal(Eval('state'), 'done')),
                },

            })

    @classmethod
    def validate(cls, surgeries):
        super(Surgery, cls).validate(surgeries)
        for surgery in surgeries:
            surgery.validate_surgery_period()

    def validate_surgery_period(self):
        if (self.surgery_end_date and self.surgery_date):
            if (self.surgery_end_date < self.surgery_date):
                raise EndDateBeforeStart(
                    gettext('health_surgery.msg_end_date_before_start'))

    @classmethod
    def write(cls, surgeries, vals):
        # Don't allow to write the record if the surgery has been signed
        if surgeries[0].state == 'signed':
            raise EndDateBeforeStart(
                gettext('health_surgery.msg_surgery_is_done'))
        return super(Surgery, cls).write(surgeries, vals)

    # Method to check for availability and make the Operating Room
    # reservation for the associated surgery
    @classmethod
    @ModelView.button
    def confirmed(cls, surgeries):
        table = cls.__table__()
        cursor = Transaction().connection.cursor()

        for surgery in surgeries:
            # Operating Room and end surgery time check
            if (not surgery.operating_room or not surgery.surgery_end_date):
                raise OperatingRoomAndDateRequired(
                        gettext('health_surgery.msg_or_and_time_needed'))
            if surgery.surgery_end_date < surgery.surgery_date:
                raise EndDateBeforeStart(
                        gettext('health_surgery.msg_end_date_before_start'))
            cursor.execute(*table.select(
                    table.id,
                    where=(
                        ((table.surgery_date <= surgery.surgery_date) &
                         (table.surgery_end_date >= surgery.surgery_date)) |
                        ((table.surgery_date <= surgery.surgery_end_date)
                            & (table.surgery_end_date
                                >= surgery.surgery_end_date)) |
                        ((table.surgery_date >= surgery.surgery_date)
                            & (table.surgery_end_date
                                <= surgery.surgery_end_date)))
                    & table.state.in_(['confirmed', 'in_progress'])
                    & (table.operating_room == surgery.operating_room.id)))
            if cursor.fetchone():
                raise ORNotAvailable(
                        gettext('health_surgery.msg_or_is_not_available'))

        cls.write(surgeries, {'state': 'confirmed'})
    
    @classmethod
    @ModelView.button
    def ot_fit(cls, surgeries):
        cls.write(surgeries, {'state': 'draft'})
    
    @classmethod
    @ModelView.button
    def ot_unfit(cls, surgeries):
        cls.write(surgeries, {'state': 'ot_unfit'})

    # Cancel the surgery and set it to draft state
    # Free the related Operating Room
    @classmethod
    @ModelView.button
    def cancel(cls, surgeries):
        cls.write(surgeries, {'state': 'cancelled'})

    # Start the surgery

    @classmethod
    @ModelView.button
    def start(cls, surgeries):
        surgery_id = surgeries[0]
        Operating_room = Pool().get('gnuhealth.hospital.or')

        cls.write(surgeries,
                  {'state': 'in_progress',
                   'surgery_date': datetime.now(),
                   'surgery_end_date': datetime.now()})
        Operating_room.write([surgery_id.operating_room],
                             {'state': 'occupied'})

    # Finish the surgery
    # Free the related Operating Room

    @classmethod
    @ModelView.button
    def done(cls, surgeries):
        surgery_id = surgeries[0]
        Operating_room = Pool().get('gnuhealth.hospital.or')

        cls.write(surgeries, {'state': 'done',
                              'surgery_end_date': datetime.now()})

        Operating_room.write([surgery_id.operating_room], {'state': 'free'})

    # Sign the surgery document, and the surgical act.

    @classmethod
    @ModelView.button
    def signsurgery(cls, surgeries):

        # Sign, change the state of the Surgery to "Signed"
        # and write the name of the signing health professional

        signing_hp = get_health_professional()

        cls.write(surgeries, {
            'state': 'signed',
            'signed_by': signing_hp})

    def get_report_surgery_date(self, name):
        Company = Pool().get('company.company')

        timezone = None
        company_id = Transaction().context.get('company')
        if company_id:
            company = Company(company_id)
            if company.timezone:
                timezone = pytz.timezone(company.timezone)

        dt = self.surgery_date
        return datetime.astimezone(dt.replace(tzinfo=pytz.utc),
                                   timezone).date()

    def get_report_surgery_time(self, name):
        Company = Pool().get('company.company')

        timezone = None
        company_id = Transaction().context.get('company')
        if company_id:
            company = Company(company_id)
            if company.timezone:
                timezone = pytz.timezone(company.timezone)

        dt = self.surgery_date
        return datetime.astimezone(dt.replace(tzinfo=pytz.utc),
                                   timezone).time()

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
                ('patient',) + tuple(clause[1:]),
                ('code',) + tuple(clause[1:]),
                ]


class Operation(ModelSQL, ModelView):
    'Operation - Surgical Procedures'
    __name__ = 'gnuhealth.operation'

    name = fields.Many2One('gnuhealth.surgery', 'Surgery')
    procedure = fields.Many2One(
        'gnuhealth.procedure', 'Code', required=True, select=True,
        help="Procedure Code, for example ICD-10-PCS or ICPM")
    notes = fields.Text('Notes')

    def get_rec_name(self, name):
        return self.procedure.rec_name


class SurgeryDrain(ModelSQL, ModelView):
    'Surgical drain'
    __name__ = 'gnuhealth.surgery.drain'

    name = fields.Many2One('gnuhealth.surgery', 'Surgery')
    drain = fields.Selection([
        (None, ''),
        ('penrose', 'Penrose'),
        ('blake', 'Blake'),
        ('kehr', 'Kehr'),
        ('jackson_pratt', 'Jackson-Pratt'),
        ('redon', 'Redon'),
        ('thoracic_tube', 'Thoracic tube'),
        ('redivac', 'Redivac'),
        ('davol', 'Davol'),
        ], 'Drain', sort=False,)

    notes = fields.Text('Notes')

    def get_rec_name(self, name):
        return self.drain


class SurgerySupply(ModelSQL, ModelView):
    'Supplies related to the surgery'
    __name__ = 'gnuhealth.surgery_supply'

    name = fields.Many2One('gnuhealth.surgery', 'Surgery')
    qty = fields.Numeric('Qty', required=True,
                         help="Initial required quantity")
    supply = fields.Many2One(
        'product.product', 'Supply', required=True,
        domain=[
            'OR',
            ('is_medical_supply', '=', True),
            ('is_vaccine', '=', True),
            ('is_medicament', '=', True)],
        help="Supplies and drugs to be used in the surgery")

    notes = fields.Char('Notes')
    qty_used = fields.Numeric('Used', required=True,
                              help="Actual amount used")


class SurgeryTeam(ModelSQL, ModelView):
    'Team Involved in the surgery'
    __name__ = 'gnuhealth.surgery_team'

    name = fields.Many2One('gnuhealth.surgery', 'Surgery')
    team_member = fields.Many2One(
        'gnuhealth.healthprofessional', 'Member', required=True, select=True,
        help="Health professional that participated on this surgery")

    role = fields.Many2One(
        'gnuhealth.hp_specialty', 'Role',
        domain=[('name', '=', Eval('team_member'))],
        depends=['team_member'])

    notes = fields.Char('Notes')


# SURGERY COMPLICATIONS
class SurgeryComplication(ModelSQL, ModelView):
    'Surgery Complication'
    __name__ = 'gnuhealth.surgery.complication'

    name = fields.Many2One('gnuhealth.surgery', 'Surgery')

    complication = fields.Many2One(
            'gnuhealth.pathology', 'Complication', required=True,
            help='Complication during surgery')

    severity = fields.Selection([
        (None, ''),
        ('1_mi', 'Mild'),
        ('2_mo', 'Moderate'),
        ('3_sv', 'Severe'),
        ], 'Severity', select=True, sort=False)

    severity_str = severity.translated('severity')

    short_comment = fields.Char(
        'Remarks',
        help='Brief, one-line remark of the complication.')


class PreOperativeAssessment(ModelSQL, ModelView):
    'Preoperative Assessment'
    __name__ = 'gnuhealth.preoperative_assessment'

    """ Preoperative Assessment class contains the necessary patient
        and anesthesia information to be taken into account
        in the upcoming surgery
    """
    patient = fields.Many2One('gnuhealth.patient', 'Patient', required=True)

    health_professional = fields.Many2One(
        'gnuhealth.healthprofessional', 'Health Prof',
        help="Health professional that signs this assessment")

    surgery = fields.Many2One(
        'gnuhealth.surgery', 'Surgery',
        depends=['patient'],
        domain=[('patient', '=', Eval('patient'))],)

    specialty = fields.Many2One('gnuhealth.specialty', 'Specialty')

    evaluation = fields.Many2One(
        'gnuhealth.patient.evaluation', 'Evaluation',
        domain=[('patient', '=', Eval('patient'))],
        depends=['patient'],
        help="Related encounter")

    assessment_date = fields.Date(
        'Date', help="Date of the assessment")

    critical_info = fields.Text(
        'Critical Information',
        help='Patient important health conditions at the moment of the'
             ' assessment')

    preop_mallampati = fields.Selection([
        (None, ''),
        ('Class 1', 'Class 1: Full visibility of tonsils, uvula and soft '
                    'palate'),
        ('Class 2', 'Class 2: Visibility of hard and soft palate, '
                    'upper portion of tonsils and uvula'),
        ('Class 3', 'Class 3: Soft and hard palate and base of the uvula are '
                    'visible'),
        ('Class 4', 'Class 4: Only Hard Palate visible'),
        ], 'Mallampati Score', sort=False)

    preop_mallampati_str = preop_mallampati.translated('preop_mallampati')

    preop_bleeding_risk = fields.Boolean(
        'Risk of Massive bleeding',
        help="Patient has a risk of losing more than 500 "
        "ml in adults of over 7ml/kg in infants. If so, make sure that "
        "intravenous access and fluids are available")

    preop_asa = fields.Selection([
        (None, ''),
        ('ps1', 'PS 1 : Normal healthy patient'),
        ('ps2', 'PS 2 : Patients with mild systemic disease'),
        ('ps3', 'PS 3 : Patients with severe systemic disease'),
        ('ps4', 'PS 4 : Patients with severe systemic disease that is'
            ' a constant threat to life '),
        ('ps5', 'PS 5 : Moribund patients who are not expected to'
            ' survive without the operation'),
        ('ps6', 'PS 6 : A declared brain-dead patient who organs are'
            ' being removed for donor purposes'),
        ], 'ASA PS',
        help="ASA pre-operative Physical Status", sort=False)
    preop_asa_str = preop_asa.translated('preop_asa')

    preop_rcri = fields.Many2One(
        'gnuhealth.rcri', 'RCRI',
        help='Patient Revised Cardiac Risk Index\n'
        'Points 0: Class I Very Low (0.4% complications)\n'
        'Points 1: Class II Low (0.9% complications)\n'
        'Points 2: Class III Moderate (6.6% complications)\n'
        'Points 3 or more : Class IV High (>11% complications)')

    surgical_wound = fields.Selection([
        (None, ''),
        ('I', 'Clean . Class I'),
        ('II', 'Clean-Contaminated . Class II'),
        ('III', 'Contaminated . Class III'),
        ('IV', 'Dirty-Infected . Class IV'),
        ], 'Surgical wound', sort=False)

    no_anesthesia = fields.Boolean(
        'Do NOT use anesthesia',
        help="The patient is not eligible to be anesthetized")

    needs_blood_reserve = fields.Boolean(
        'Needs blood reservation',
        help="The surgery requires preoperative blood ordering")

    # Include link to patient ECG
    ecg = fields.Many2One(
        'gnuhealth.patient.ecg', 'ECG',
        domain=[('name', '=', Eval('patient'))],
        depends=['patient'],
        help='Link to the associated electrocardiogram')

    # Include link to patient Imaging test (eg, Xray)
    imaging_test = fields.Many2One(
        'gnuhealth.imaging.test.result', 'Imaging',
        domain=[('patient', '=', Eval('patient'))],
        depends=['patient'],
        help='Link to the associated Dx imaging test')

    # Include link to patient lab test (eg, CBC)
    lab_test = fields.Many2One(
        'gnuhealth.lab', 'Lab',
        domain=[('patient', '=', Eval('patient'))],
        depends=['patient'],
        help='Link to the associated lab test')

    surgical_decision = fields.Selection([
        (None, ''),
        ('revision', 'Schedule Revision'),
        ('watchful_waiting', 'Watchful waiting'),
        ('needs_surgery', 'Needs surgery'),
        ('urgent_surgery', 'Urgent surgery'),
        ('discharge', 'Discharge'),
        ], 'Surgical decision',
        help='Surgical decision / advice',
        sort=False)

    surgical_decision_str = surgical_decision.translated('surgical_decision')

    short_notes = fields.Char('Notes')

    @staticmethod
    def default_assessment_date():
        return datetime.now()

    # Show the gender and age upon entering the patient
    # These two are function fields (don't exist at DB level)
    @fields.depends('patient')
    def on_change_patient(self):
        self.critical_info = f'{self.patient.critical_summary} \n' \
                             f'{self.patient.critical_info}'

    def get_rec_name(self, name):
        asa = ''
        if (self.preop_asa):
            asa = self.preop_asa
        return (f'{str(self.assessment_date)} ASA: {asa}')


# SURGERY PROTOCOL TEMPLATE
class SurgeryProtocol(ModelSQL, ModelView):
    'Surgery Protocol'
    __name__ = 'gnuhealth.surgery.protocol'

    name = fields.Char(
        'Name',
        help='Protocol Name')

    description = fields.Char('Description')

    general_info = fields.Text('General Information')

    anesthesia_type = fields.Selection([
        (None, ''),
        ('local', 'Local'),
        ('regional', 'Regional'),
        ('general', 'General'),
        ('sedation', 'Sedation'),
        ('rachianesthesia', 'Rachianesthesia'),
        ('epidural', 'Epidural'),
        ('peribulbar', 'Peribulbar'),
        ('regional_block', 'Regional Block'),
        ('local_sedation', 'Local + sedation'),
        ('No anesthesia', 'No anesthesia'),
        ], 'Anesthesia', sort=False)

    patient_positioning = fields.Selection([
        (None, ''),
        ('supine_decubitus', 'Supine Decubitus'),
        ('prone_decubitus', 'Prone Decubitus'),
        ('lithotomy', 'Lithotomy'),
        ('lateral', 'Lateral'),
        ('sims', 'Sims'),
        ('fowlers', 'Fowlers'),
        ('semi_fowlers', 'Semi-Fowler'),
        ('trendelenburg', 'Trendelenburg'),
        ('reverse_trendelenburg', 'Reverse Trendelenburg'),
        ('jacknife', 'Jacknife'),
        ('knee_chest', 'Knee-chest'),
        ('lloyd_davies', 'Lloyd-Davies'),
        ('kidney', 'Kidney positioning'),
        ('other', 'Other'),
        ], 'Patient Positioning', sort=False,)

    laterality = fields.Selection([
        (None, ''),
        ('right', 'Right'),
        ('left', 'Left'),
        ('bilateral', 'Bilateral'),
        ], 'Laterality', sort=False,)

    approach = fields.Selection([
        (None, ''),
        ('open', 'Open'),
        ('laparoscopic', 'Laparoscopic'),
        ('endoscopic', 'Endoscopic'),
        ('arthroscopic', 'Arthroscopic'),
        ('robotic', 'Robotic'),
        ('other', 'other'),
        ], 'Approach', sort=False)

    surgical_intervention = fields.Many2One(
        'gnuhealth.procedure', 'Surgical Intervention',
        help="This code reflects the main intervention of this surgery.")

    pathology = fields.Many2One(
        'gnuhealth.pathology', 'Health Condition',
        help="Base Condition / Reason")

    classification = fields.Selection([
        (None, ''),
        ('o', 'Optional'),
        ('r', 'Required'),
        ('u', 'Urgent'),
        ('e', 'Emergency'),
        ], 'Urgency', help="Urgency level for this surgery", sort=False)

    postoperative_guidelines = fields.Text('Postoperative guidelines')

    discharge_instructions = fields.Text('Discharge Instructions')

    @classmethod
    def __setup__(cls):
        super(SurgeryProtocol, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints = [
            ('code_uniq', Unique(t, t.name),
             'The protocol name must be unique')
        ]


class PatientData(metaclass=PoolMeta):
    __name__ = 'gnuhealth.patient'

    surgery = fields.One2Many(
        'gnuhealth.surgery', 'patient', 'Surgeries', readonly=True)


class PatientEvaluation (metaclass=PoolMeta):
    __name__ = 'gnuhealth.patient.evaluation'

    """ Add contextual information
        findings of importance in surgical contexts """

    surgical_context = fields.Selection([
        (None, ''),
        ('thyroid', 'Thyroid'),
        ('hernia', 'Hernia'),
        ], 'Context')

    # Begin hernia specific information
    hernia_localization = fields.Selection([
        (None, ''),
        ('umbilical', 'Umbilical'),
        ('inguinal', 'Inguinal'),
        ('crural', 'Crural'),
        ('obturator', 'Obturator'),
        ('spigelian', 'Spigelian'),
        ('lumbar', 'Lumbar'),
        ('eventration', 'Eventration'),
        ], 'Localization', sort=False)

    hernia_side = fields.Selection([
        (None, ''),
        ('left', 'Left'),
        ('right', 'Right'),
        ('bilateral', 'bilateral'),
        ], 'Side', sort=False)

    hernia_type = fields.Selection([
        (None, ''),
        ('h1', 'H1 - Reduces spontaneously when patient is lying'),
        ('h2', 'H2 - Groin only, reduces completely with gentle manual '
            'pressure'),
        ('h3a', 'H3a - Inguino-scrotal reductible with manual '
            'manipulation. Component ing-scrot<10cm'),
        ('h3b', 'H3b - Inguino-scrotal reductible with manual '
            'manipulation. Component ing-scrot 10-20 cm'),
        ('h3c', 'H3c - Inguino-scrotal reductible with manual '
            'manipulation. Component ing-scrot>20cm'),
        ('h4a', 'H4a - Irreducible. Component ing-scrot<10cm'),
        ('h4b', 'H4b - Irreducible. Component ing-scrot 10-20 cm'),
        ('h4c', 'H4c - Irreducible. Component ing-scrot >20 cm'),
        ], 'Type', sort=False)

    hernia_ehs = fields.Selection([
        (None, ''),
        ('lateral', 'Lateral (indirect)'),
        ('medial', 'Medial (direct)'),
        ('sliding', 'Sliding'),
        ('femoral', 'Femoral'),
        ], 'EHS', sort=False)

    hernia_time = fields.Selection([
        (None, ''),
        ('less_1_year', '< 1 year'),
        ('1_to_5_year', '1 - 5 years'),
        ('more_5_year', '> 5 years'),
        ], 'Evolution time', sort=False)

    hernia_disfunction = fields.Selection([
        (None, ''),
        ('no_disfunction', 'No disfunction'),
        ('limited', 'Limited daily activities'),
        ('severe', 'Discapacitating'),
        ], 'Disfunctionality level', sort=False)

    # End hernia specific information

    # Begin thyroid specific information
    thyroid_exploration = fields.Selection([
        (None, ''),
        ('normal', 'Normal'),
        ('nodule', 'Nodule'),
        ('goiter', 'Goiter'),
        ], 'Exploration', sort=False)

    thyroid_side = fields.Selection([
        (None, ''),
        ('left', 'Left'),
        ('right', 'Right'),
        ('bilateral', 'Bilateral'),
        ], 'Side', sort=False)

    thyroid_clinical = fields.Selection([
        (None, ''),
        ('hoarseness', 'Hoarseness'),
        ('cough', 'Cough'),
        ('other', 'Other'),
        ], 'Clinical', sort=False)

    thyroid_goiter = fields.Selection([
        (None, ''),
        ('solitary_nodule', 'Solitary nodule'),
        ('multinodular', 'Multinodular'),
        ('difuse', 'Difuse'),
        ('intrathoracic', 'Intrathoracic'),
        ], 'Goiter', sort=False)

    thyroid_tirads = fields.Selection([
        (None, ''),
        ('tr1', 'TR1'),
        ('tr2', 'TR2'),
        ('tr3', 'TR3'),
        ('tr4a', 'TR4a'),
        ('tr4b', 'TR4b'),
        ('tr5', 'TR5'),
        ('tr6', 'TR6'),
        ], 'TI-RADS', sort=False)

    thyroid_tvol = fields.Integer(
        "TVol (mL)",
        help="Volume in mL")

    thyroid_goiter_class = fields.Selection([
        (None, ''),
        ('gr1', '0'),
        ('gr2', '1'),
        ('gr3', '2'),
        ('gr4a', '3'),
        ('gr5', '4'),
        ('gr5', '5'),
        ], 'Goiter classification', sort=False)

    @classmethod
    def view_attributes(cls):
        # Hide the specific group unless selected in surgical_context
        return super(PatientEvaluation, cls).view_attributes() + [
                ('//group[@id="group_evl_surgery_hernia_info"]',
                    'states', {
                        'invisible': ~Equal(
                            Eval('surgical_context'), 'hernia'),
                    }),
                ('//group[@id="group_evl_surgery_thyroid_info"]',
                    'states', {
                        'invisible': ~Equal(
                            Eval('surgical_context'), 'thyroid'),
                    }),
                    ]

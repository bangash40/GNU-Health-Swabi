# -*- coding: utf-8 -*-
##############################################################################
#
#    GNU Health: The Free Health and Hospital Information System
#    Copyright (C) 2008-2016 Luis Falcon <lfalcon@gnusolidario.org>
#    Copyright (C) 2011-2016 GNU Solidario <health@gnusolidario.org>
#
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

from trytond.pool import Pool
from .health_proc import *
from .sale_reports import *
from .health_lab_updates import *
from .health_imaging_updates import *
from .health_inpatient_updates import *
from .account_rule_updates import *
from .health_hr import *
from .wizard import *
from . import sequences

def register():
    Pool.register(
        SystemConfig,
        SaleLine,
        DiscountRequest,
        DiscountRequestLine,
        ResUser, 
        HMISUtility,
        Sale,		   
        RequestLabTestFastStart, 
        GnuHealthPatientLabTest,
        HealthprofType,
        HealthProfessionalServices,
        HealthProfessional,
        Reagent,
        TestType,
        Lab,
        SampleType,
        AnalysisSpec,
        GnuHealthLabTestCategories,
        LimsAnalyteResults,
        AnalysisCategory,
        ResultOption,
        AnalysisService,
        TestTypeAnalysisService, 
        AnalysisServiceResult,
        AnalysisServiceResultRange,
        DiscountType,
        TestResultsEntryStart, 
        LimsTestResultsEntryStart,   
        ImagingTestRequest,
        Lot,     
        ImagingTestResult,
        PatientData,
        PartyData,
        Appointment,
        AccountStatementLine,
        ServicesSummaryReportCategoryWiseStart,
        StockMove,
        InvoiceLine,
        ImagingTest,
        InpatientRegistration,
        RequestPatientLabTestStart,
        InpatientAdvanceInvoices,
        GetPatientAdvanceStart,
        CreatePatientSaleStart,
        HealthSaleLine,
        RequestPatientImagingTestStart,
        GeneralSaleLine,
        #AccountRuleInsuranceCompany,
        ProductGroup,
        ProductGroupLine,
        InsurancePanel,
        InsurancePanelProductGroup,
        IpdPackageChargeLine,
        ChargePackageStart,
        PackageChargeLine,
        IpdDoctorShare,
        CalculateDoctorShareStart,
        DoctorShare,
        DeletePatientSaleLineStart,
        PrescriptionLabTest,
        PrescriptionImagingTest,
        PrescriptionOrder,
        DoctorShareDetailsReportStart,
        SampleBatch,
        sequences.GnuHealthSequences,
        sequences.LabBatchSequence,
        SampleContainer,
        Sample,
        sequences.LabSampleSequence,
        TakeNewSampleStart,
        PhelbotomySample,
        BirthCertificate,
        DeathCertificate,
        SampleBatchSample,
        HealthInstitution,
        PrintNewSampleStart,
        Pathology,
        PrescriptionDisease,
        DoctorShareSummaryReportStart,
        InsurancePanelBill,
        PanelBillingStart,
        ShowPatientBillsStart,
        OpdStatsReportStart,
        ConfirmPosPaymentStart,
        Purchase,
        Shipment,
        PurchaseRequest,
        TestTypeTestComponent,
        InternalShipment,
        PurchaseRequisition,
        StockInventoryReportStart,
        DoctorServicesDetailsReportStart,  
        Employee,
        Department,
        StockNearExpiryReportStart,
        StockExpiredReportStart,  
        ProductProduct,   
        ShipmentIn,   
        VisitOpdPatient,
        SurgeryRecommendedOpdPatient,
        ProcedureComplexity,
        Directions,
        Surgery,
        StockInternalShipmentReportStart,
        CriticalAnalytesReportStart,
        PurchaseReportStart,
        PurchaseLine,
        OPDTurnoverReportStart,
        module='health_proc', type_='model')
    Pool.register(
        RequestLabTestFastWizard,
        WizardCreateLabTestOrder,
        TestResultsEntryWizard,
        LimsTestResultsEntryWizard,  
        ReturnSale,
        WizardServicesSummaryReportCategoryWise,
        GetPatientAdvance,
        CreatePatientSale,
        WizardSalePayment,
        ChargePackageWizard,
        CalculateDoctorShareWizard,
        DeletePatientSaleLine,
        CreateEvaluationPrescription,
        WizardDoctorShareDetails,
        TakeNewSampleWizard,
        WizardDoctorShareSummary,
        PreparePanelBillWizard,
        WizardOpdStats,
        CustomSalePaymentWizard,
        WizardStockInventoryReport,
        WizardDoctorServicesDetails, 
        WizardStockNearExpiryReport, 
        WizardStockExpiredReport,            
        WizardOpdStatsDetailed,
        WizardPatientVisitOpdReport,
        WizardSurgeryRecommendedOpdReport,
        CreateShipmentWizard,
        WizardStockInternalShipmentReport,
        WizardCriticalAnalytesReport,
        WizardPurchaseReport,
        WizardOPDTurnoverReport,
        module='health_proc', type_='wizard')
    Pool.register(
	    IDHRegistrationReceiptReport,
        TestPdfReport,
        LimsLabReportReport,
        LabRequestLabelsCode39,
        RadiologyTestReportFinal,
        ServicesSummaryReportCategoryWise,
        PatientAdmissionOrderReport,
        PatientSummaryBillReport,
        PatientDischargeCertificateReport,
        PrescriptionSlipReport,
        DoctorShareDetailsReport,
        DoctorShareSummaryReport,
        PanelBillReport,
        OpdStatsReport,
        PhlebotomyAccessionSheetReport,
        StockInventoryDetailsReport,
        DoctorServicesDetailsReport,
        StockNearExpiryReport, 
        StockExpiredReport,   
        OpdStatsDetailedFinalReport, 
        VisitOpdPatientDetailsReport,  
        SurgeryRecommendedOpdDetailsReport,
        StockInternalShipmentReport,
        CriticalAnalytesReport,
        PurchaseReport,
        OPDTurnoverReport,
        module='health_proc', type_='report')

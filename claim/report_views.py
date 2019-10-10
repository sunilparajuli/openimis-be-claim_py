from report.services import ReportService
from .services import ClaimsReportService
from .reports import claims


def print(request):
    report_service = ReportService(request.user)
    report_data_service = ClaimsReportService(request.user)
    data = report_data_service.fetch(request.GET['uuid'])
    return report_service.process('claim_claims', data, claims.template)

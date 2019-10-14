from django.core.exceptions import PermissionDenied
from report.services import ReportService
from .services import ClaimsReportService
from .reports import claims
from .apps import ClaimConfig
from django.utils.translation import gettext as _


def print(request):
    if not request.user.has_perms(ClaimConfig.claim_print_perms):
        raise PermissionDenied(_("unauthorized"))
    report_service = ReportService(request.user)
    report_data_service = ClaimsReportService(request.user)
    data = report_data_service.fetch(request.GET['uuid'])
    return report_service.process('claim_claims', data, claims.template)

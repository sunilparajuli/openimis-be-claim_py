from report.services import ReportService
from .services import ReportClaimsService
from .reports import claims


def _report(prms):
    show_claims = prms.get("showClaims", "false") == 'true'
    group = prms.get("group", "H")
    if show_claims:
        report = "claim_batch_pbc_"+group
        default = pbc_H.template if group == 'H' else pbc_P.template
    elif group == 'H':
        report = "claim_batch_pbh"
        default = pbh.template
    else:
        report = "claim_batch_pbp"
        default = pbp.template
    return report, default


def print(request):
    report_service = ReportService(request.user)
    report_data_service = ReportClaimsService(request.user)
    data = report_data_service.fetch(request.GET)
    return report_service.process('claim_claims', {'data': "CLAIM"}, claims.template)


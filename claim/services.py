import logging
from gettext import gettext as _

from claim.models import Claim, ClaimDedRem, ClaimDetail
from claim.validations import validate_claim, validate_assign_prod_to_claimitems_and_services, process_dedrem, \
    approved_amount, get_claim_category
from product.models import ProductItemOrService

logger = logging.getLogger(__name__)


def submit_claim(claim, audit_user_id):
    c_errors = validate_claim(claim, True)
    logger.debug("submit_claim: claim %s validated, nb of errors: %s", claim.uuid, len(c_errors))
    if len(c_errors) == 0:
        c_errors = validate_assign_prod_to_claimitems_and_services(claim)
        logger.debug("submit_claim: claim %s assigned, nb of errors: %s", claim.uuid, len(c_errors))
        c_errors += process_dedrem(claim, audit_user_id, False)
        logger.debug("submit_claim: claim %s processed for dedrem, nb of errors: %s", claim.uuid,
                     len(c_errors))
    c_errors += set_claim_submitted(claim, c_errors, audit_user_id)
    logger.debug("submit_claim: claim %s set submitted", claim.uuid)
    return c_errors


def set_claims_status(uuids, field, status):
    errors = []
    for claim_uuid in uuids:
        claim = Claim.objects \
            .filter(uuid=claim_uuid,
                    validity_to__isnull=True) \
            .first()
        if claim is None:
            errors += [{'message': _(
                "claim.validation.id_does_not_exist") % {'id': claim_uuid}}]
            continue
        try:
            claim.save_history()
            setattr(claim, field, status)
            claim.save()
        except Exception as exc:
            errors += [
                {'message': _("claim.mutation.failed_to_change_status_of_claim") %
                            {'code': claim.code}}]

    return errors


def update_claims_dedrems(uuids, user):
    # We could do it in one query with filter(claim__uuid__in=uuids) but we'd loose the logging
    errors = []
    for uuid in uuids:
        logger.debug(f"delivering review on {uuid}, reprocessing dedrem ({user})")
        claim = Claim.objects.get(uuid=uuid)
        errors += validate_and_process_dedrem_claim(claim, user, False)
    return errors


def with_relative_prices(claim):
    return details_with_relative_prices(claim.items) or details_with_relative_prices(claim.services)


def set_claim_processed_or_valuated(claim, errors, user):
    try:
        if errors:
            claim.status = Claim.STATUS_REJECTED
        else:
            claim.status = Claim.STATUS_PROCESSED if with_relative_prices(claim) else Claim.STATUS_VALUATED
            claim.audit_user_id_process = user.id_for_audit
            from core.utils import TimeUtils
            claim.process_stamp = TimeUtils.now()
        claim.save()
        return []
    except Exception as ex:
        return {
            'title': claim.code,
            'list': [{'message': _("claim.mutation.failed_to_change_status_of_claim") % {'code': claim.code},
                      'detail': claim.uuid}]
        }


def validate_and_process_dedrem_claim(claim, user, is_process):
    errors = validate_claim(claim, False)
    logger.debug("ProcessClaimsMutation: claim %s validated, nb of errors: %s", claim.uuid, len(errors))
    if len(errors) == 0:
        errors = validate_assign_prod_to_claimitems_and_services(claim)
        logger.debug("ProcessClaimsMutation: claim %s assigned, nb of errors: %s", claim.uuid, len(errors))
        errors += process_dedrem(claim, user.id_for_audit, is_process)
        logger.debug("ProcessClaimsMutation: claim %s processed for dedrem, nb of errors: %s", claim.uuid,
                     len(errors))
    else:
        # OMT-208 the claim is invalid. If there is a dedrem, we need to clear it (caused by a review)
        deleted_dedrems = ClaimDedRem.objects.filter(claim=claim).delete()
        if deleted_dedrems:
            logger.debug(f"Claim {claim.uuid} is invalid, we deleted its dedrem ({deleted_dedrems})")
    if is_process:
        errors += set_claim_processed_or_valuated(claim, errors, user)
    return errors


def set_claim_submitted(claim, errors, audit_user_id):
    try:
        if errors:
            claim.status = Claim.STATUS_REJECTED
        else:
            claim.approved = approved_amount(claim)
            claim.status = Claim.STATUS_CHECKED
            claim.audit_user_id_submit = audit_user_id
            from core.utils import TimeUtils
            claim.submit_stamp = TimeUtils.now()
            claim.category = get_claim_category(claim)
        claim.save()
        return []
    except Exception as exc:
        return {
            'title': claim.code,
            'list': [{
                'message': _("claim.mutation.failed_to_change_status_of_claim") % {'code': claim.code},
                'detail': claim.uuid}]
        }


def set_claim_deleted(claim):
    try:
        claim.delete_history()
        return []
    except Exception as exc:
        return {
            'title': claim.code,
            'list': [{
                'message': _("claim.mutation.failed_to_change_status_of_claim") % {'code': claim.code},
                'detail': claim.uuid}]
        }


def details_with_relative_prices(details):
    return details.filter(status=ClaimDetail.STATUS_PASSED) \
        .filter(price_origin=ProductItemOrService.ORIGIN_RELATIVE) \
        .exists()


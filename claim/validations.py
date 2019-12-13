from collections import OrderedDict
from typing import List

from claim.models import ClaimItem, Claim, ClaimService
from core import utils
from core.datetimes.shared import datetimedelta
from django.db import connection
from django.db.models import Sum, Q
from django.db.models.functions import Coalesce
from django.utils.translation import gettext as _
from medical.models import Service
from medical_pricelist.models import ItemsPricelistDetail, ServicesPricelistDetail
from policy.models import Policy
from product.models import Product, ProductItem, ProductService
from .apps import ClaimConfig

REJECTION_REASON_INVALID_ITEM_OR_SERVICE = 1
REJECTION_REASON_NOT_IN_PRICE_LIST = 2
REJECTION_REASON_NO_PRODUCT_FOUND = 3
REJECTION_REASON_CATEGORY_LIMITATION = 4
REJECTION_REASON_FREQUENCY_FAILURE = 5
# REJECTION_REASON_DUPLICATED = 6
REJECTION_REASON_FAMILY = 7
# REJECTION_REASON_ICD_NOT_IN_LIST = 8
REJECTION_REASON_TARGET_DATE = 9
REJECTION_REASON_CARE_TYPE = 10
REJECTION_REASON_MAX_HOSPITAL_ADMISSIONS = 11
REJECTION_REASON_MAX_VISITS = 12
REJECTION_REASON_MAX_CONSULTATIONS = 13
REJECTION_REASON_MAX_SURGERIES = 14
REJECTION_REASON_MAX_DELIVERIES = 15
REJECTION_REASON_QTY_OVER_LIMIT = 16
REJECTION_REASON_WAITING_PERIOD_FAIL = 17
REJECTION_REASON_MAX_ANTENATAL = 19


def validate_claim(claim, check_max):
    """
    Based on the legacy validation, this method returns standard codes along with details
    :param claim: claim to be verified
    :return: (result_code, error_details)
    """
    if ClaimConfig.default_validations_disabled:
        return []
    errors = []
    errors += validate_target_date(claim)
    if len(errors) == 0:
        errors += validate_family(claim, claim.insuree)
    if len(errors) == 0:
        validate_claimitems(claim)
        validate_claimservices(claim)

    if check_max:
        # we went over the maximum for a category, all items and services in the claim are rejected
        over_category_errors = [
            x for x in errors if x['code'] in [REJECTION_REASON_MAX_HOSPITAL_ADMISSIONS,
                                               REJECTION_REASON_MAX_VISITS,
                                               REJECTION_REASON_MAX_CONSULTATIONS,
                                               REJECTION_REASON_MAX_SURGERIES,
                                               REJECTION_REASON_MAX_DELIVERIES,
                                               REJECTION_REASON_MAX_ANTENATAL]]
        if len(over_category_errors) > 0:
            rtn_items_rejected = claim.items.filter(validity_to__isnull=True)\
                .update(status=ClaimItem.STATUS_REJECTED,
                        qty_approved=0,
                        rejection_reason=over_category_errors[0]['code'])
            rtn_services_rejected = claim.services.filter(validity_to__isnull=True)\
                .update(status=ClaimService.STATUS_REJECTED,
                        qty_approved=0,
                        rejection_reason=over_category_errors[0]['code'])
        else:
            rtn_items_rejected = claim.items.filter(validity_to__isnull=True)\
                .exclude(rejection_reason=0).exclude(rejection_reason__isnull=True)\
                .update(status=ClaimItem.STATUS_REJECTED, qty_approved=0)
            rtn_services_rejected = claim.services.filter(validity_to__isnull=True)\
                .exclude(rejection_reason=0).exclude(rejection_reason__isnull=True)\
                .update(status=ClaimService.STATUS_REJECTED, qty_approved=0)

    rtn_items_passed = claim.items.filter(validity_to__isnull=True)\
        .exclude(status=ClaimItem.STATUS_REJECTED)\
        .update(status=ClaimItem.STATUS_PASSED)
    rtn_services_passed = claim.services.filter(validity_to__isnull=True)\
        .exclude(status=ClaimService.STATUS_REJECTED)\
        .update(status=ClaimService.STATUS_PASSED)

    if rtn_items_passed + rtn_services_passed == 0:
        errors += [{'code': REJECTION_REASON_INVALID_ITEM_OR_SERVICE,
                    'message': _("claim.validation.all_items_and_services_rejected") % {
                        'code': claim.code},
                    'detail': claim.uuid}]
    return errors


def validate_claimitems(claim):
    target_date = claim.date_from if claim.date_from else claim.date_to
    for claimitem in claim.items.filter(validity_to__isnull=True):
        claimitem.rejection_reason = None
        validate_claimitem_validity(claimitem)
        if not claimitem.rejection_reason:
            validate_claimitem_in_price_list(claim, claimitem)
        if not claimitem.rejection_reason:
            validate_claimitem_care_type(claim, claimitem)
        if not claimitem.rejection_reason:
            validate_claimitem_limitation_fail(claim, claimitem)
        if not claimitem.rejection_reason:
            validate_claimitem_frequency(claim, claimitem)
        if not claimitem.rejection_reason:
            validate_item_product_family(
                claimitem=claimitem,
                target_date=target_date,
                item=claimitem.item,
                insuree_id=claim.insuree_id,
                adult=claim.insuree.is_adult(target_date)
            )
        if claimitem.rejection_reason:
            claimitem.status = ClaimItem.STATUS_REJECTED
        else:
            claimitem.status = ClaimItem.STATUS_PASSED
        claimitem.save()


def validate_claimservices(claim):
    target_date = claim.date_from if claim.date_from else claim.date_to
    base_category = get_claim_category(claim)

    for claimservice in claim.services.all():
        claimservice.rejection_reason = None
        validate_claimservice_validity(claimservice)
        if not claimservice.rejection_reason:
            validate_claimservice_in_price_list(claim, claimservice)
        if not claimservice.rejection_reason:
            validate_claimservice_care_type(claim, claimservice)
        if not claimservice.rejection_reason:
            validate_claimservice_frequency(claim, claimservice)
        if not claimservice.rejection_reason:
            validate_claimservice_limitation_fail(claim, claimservice)
        if not claimservice.rejection_reason:
            validate_service_product_family(
                claimservice=claimservice,
                target_date=target_date,
                service=claimservice.service,
                insuree_id=claim.insuree_id,
                adult=claim.insuree.is_adult(target_date),
                base_category=base_category,
            )
        if claimservice.rejection_reason:
            claimservice.status = ClaimService.STATUS_REJECTED
        else:
            claimservice.status = ClaimService.STATUS_PASSED
        claimservice.save()


def validate_claimitem_validity(claimitem):
    # In the stored procedure, this check used a complex query to get the latest item but the latest item seems to
    # always be updated.
    # select *
    # from tblClaimItems tCI inner join tblItems tI on tCI.ItemID = tI.ItemID
    # where ti.ValidityTo is not null and tI.LegacyID is not null;
    # gives no result, so no claimitem is pointing to an old item and the complex query always fetched the last one.
    # Here, claimitem.item.legacy_id is always None
    if claimitem.validity_to is None and claimitem.item.validity_to is not None:
        claimitem.rejection_reason = REJECTION_REASON_INVALID_ITEM_OR_SERVICE


def validate_claimservice_validity(claimservice):
    # See note in validate_claimitem_validity
    if claimservice.validity_to is None and claimservice.service.validity_to is not None:
        claimservice.rejection_reason = REJECTION_REASON_INVALID_ITEM_OR_SERVICE


def validate_claimitem_in_price_list(claim, claimitem):
    pricelist_detail = ItemsPricelistDetail.objects\
        .filter(items_pricelist=claim.health_facility.items_pricelist)\
        .filter(item_id=claimitem.item_id)\
        .filter(validity_to__isnull=True)\
        .filter(items_pricelist__validity_to__isnull=True)\
        .first()
    if not pricelist_detail:
        claimitem.rejection_reason = REJECTION_REASON_NOT_IN_PRICE_LIST


def validate_claimservice_in_price_list(claim, claimservice):
    pricelist_detail = ServicesPricelistDetail.objects\
        .filter(services_pricelist=claim.health_facility.services_pricelist)\
        .filter(service_id=claimservice.service_id)\
        .filter(validity_to__isnull=True)\
        .filter(services_pricelist__validity_to__isnull=True)\
        .first()
    if not pricelist_detail:
        claimservice.rejection_reason = REJECTION_REASON_NOT_IN_PRICE_LIST


def validate_claimservice_care_type(claim, claimservice):
    care_type = claimservice.service.care_type
    hf_care_type = claim.health_facility.care_type if claim.health_facility.care_type else 'B'
    target_date = claim.date_to if claim.date_to else claim.date_from

    if (
            care_type == 'I' and (
            hf_care_type == 'O'
            or target_date == claim.date_from)
    ) or (
            care_type == 'O' and (
            hf_care_type == 'I'
            or target_date != claim.date_from)
    ):
        claimservice.rejection_reason = REJECTION_REASON_CARE_TYPE


def validate_claimitem_care_type(claim, claimitem):
    care_type = claimitem.item.care_type
    hf_care_type = claim.health_facility.care_type if claim.health_facility.care_type else 'B'
    target_date = claim.date_to if claim.date_to else claim.date_from

    if (
            care_type == 'I' and (
            hf_care_type == 'O'
            or target_date == claim.date_from)
    ) or (
            care_type == 'O' and (
            hf_care_type == 'I'
            or target_date != claim.date_from)
    ):
        claimitem.rejection_reason = REJECTION_REASON_CARE_TYPE


def validate_claimitem_limitation_fail(claim, claimitem):
    target_date = claim.date_to if claim.date_to else claim.date_from
    patient_category_mask = utils.patient_category_mask(
        claim.insuree, target_date)

    if claimitem.item.patient_category & patient_category_mask != patient_category_mask:
        claimitem.rejection_reason = REJECTION_REASON_CATEGORY_LIMITATION


def validate_claimservice_limitation_fail(claim, claimservice):
    target_date = claim.date_to if claim.date_to else claim.date_from
    patient_category_mask = utils.patient_category_mask(
        claim.insuree, target_date)
    if claimservice.service.patient_category & patient_category_mask != patient_category_mask:
        claimservice.rejection_reason = REJECTION_REASON_CATEGORY_LIMITATION


def frequency_check(qs, claim, elt):
    td = claim.date_from if not claim.date_to else claim.date_to
    delta = datetimedelta(days=elt.frequency)
    return qs.filter(claim__in=Claim.objects
                     .filter(validity_to__isnull=True, status__gt=Claim.STATUS_ENTERED, insuree_id=claim.insuree_id)
                     .annotate(target_date=Coalesce("date_to", "date_from"))
                     .filter(target_date__gte=td - delta)
                     .exclude(uuid=claim.uuid)
                     .order_by('-date_from')
                     ).exists()


def validate_claimitem_frequency(claim, claimitem):
    if claimitem.item.frequency and \
            frequency_check(ClaimItem.objects.filter(item=claimitem.item), claim, claimitem.item):
        claimitem.rejection_reason = REJECTION_REASON_FREQUENCY_FAILURE


def validate_claimservice_frequency(claim, claimservice):
    if claimservice.service.frequency and \
            frequency_check(ClaimService.objects.filter(service=claimservice.service), claim, claimservice.service):
        claimservice.rejection_reason = REJECTION_REASON_FREQUENCY_FAILURE


def validate_target_date(claim):
    errors = []
    if (claim.date_from is None and claim.date_to is None) \
            or claim.date_claimed < claim.date_from:
        claim.reject(REJECTION_REASON_TARGET_DATE)
        errors += [{'code': REJECTION_REASON_TARGET_DATE,
                    'message': _("claim.validation.target_date") % {
                        'code': claim.code
                    },
                    'detail': claim.uuid}]
    return errors


def validate_family(claim, insuree):
    errors = []
    if insuree.validity_to is not None:
        errors += [{'code': REJECTION_REASON_FAMILY,
                    'message': _("claim.validation.family.insuree_validity") % {
                        'code': claim.code,
                        'insuree': str(insuree)},
                    'detail': claim.uuid}]
    elif insuree.family is None:
        errors += [{'code': REJECTION_REASON_FAMILY,
                    'message': _("claim.validation.family.no_family") % {
                        'code': claim.code,
                        'insuree': str(insuree)},
                    'detail': claim.uuid}]
    elif insuree.family.validity_to is not None:
        errors += [{'code': REJECTION_REASON_FAMILY,
                    'message': _("claim.validation.family.family_validity") % {
                        'code': claim.code,
                        'insuree': str(insuree)},
                    'detail': claim.uuid}]
    if len(errors) > 0:
        claim.reject(REJECTION_REASON_FAMILY)
    return errors


def validate_item_product_family(claimitem, target_date, item, insuree_id, adult):
    errors = []
    found = False
    with get_products(target_date, item.id, insuree_id, adult, 'Item') as cursor:
        for (product_id, product_item_id, insuree_policy_effective_date, policy_effective_date, expiry_date,
             policy_stage) in cursor.fetchall():
            found = True
            core = __import__("core")
            insuree_policy_effective_date = core.datetime.date.from_ad_date(
                insuree_policy_effective_date)
            expiry_date = core.datetime.date.from_ad_date(expiry_date)
            prod_found = 1
            product_item = ProductItem.objects.get(pk=product_item_id)
            # START CHECK 17 --> Item/Service waiting period violation (17)
            if policy_stage == 'N' or policy_effective_date < insuree_policy_effective_date:
                if adult:
                    waiting_period = product_item.waiting_period_adult
                else:
                    waiting_period = product_item.waiting_period_adult
            if waiting_period and target_date < (insuree_policy_effective_date + datetimedelta(months=waiting_period)):
                claimitem.rejection_reason = REJECTION_REASON_WAITING_PERIOD_FAIL
                errors += [{'code': REJECTION_REASON_WAITING_PERIOD_FAIL,
                            'message': _("claim.validation.product_family.waiting_period") % {
                                'code': claimitem.claim.code,
                                'element': str(item)},
                            'detail': claimitem.claim.uuid}]

            # **** START CHECK 16 --> Item/Service Maximum provision (16)*****
            if adult:
                limit_no = product_item.limit_no_adult
            else:
                limit_no = product_item.limit_no_child
            if limit_no is not None and limit_no >= 0:
                # count qty provided
                total_qty_provided = ClaimItem.objects\
                    .filter(claim__insuree_id=insuree_id)\
                    .filter(item_id=item.id)\
                    .annotate(target_date=Coalesce("claim__date_to", "claim__date_from"))\
                    .filter(target_date__gt=insuree_policy_effective_date).filter(target_date__lte=expiry_date)\
                    .filter(claim__status__gt=Policy.STATUS_ACTIVE)\
                    .filter(claim__validity_to__isnull=True)\
                    .filter(validity_to__isnull=True)\
                    .filter(rejection_reason=0)\
                    .filter(rejection_reason__isnull=True)\
                    .aggregate(Sum("qty_provided"))
                if total_qty_provided is None or total_qty_provided >= limit_no:
                    claimitem.rejection_reason = REJECTION_REASON_QTY_OVER_LIMIT
                    errors += [{'code': REJECTION_REASON_QTY_OVER_LIMIT,
                                'message': _("claim.validation.product_family.max_nb_allowed") % {
                                    'code': claimitem.claim.code,
                                    'element': str(item),
                                    'provided': total_qty_provided,
                                    'max': limit_no},
                                'detail': claimitem.claim.uuid}]
        if not found:
            claimitem.rejection_reason = REJECTION_REASON_NO_PRODUCT_FOUND
            errors += [{'code': REJECTION_REASON_NO_PRODUCT_FOUND,
                        'message': _("claim.validation.product_family.no_product_found") % {
                            'code': claimitem.claim.code,
                            'element': str(item)},
                        'detail': claimitem.claim.uuid}]

    return errors


# noinspection DuplicatedCode
def validate_service_product_family(claimservice, target_date, service, insuree_id, adult, base_category):
    errors = []
    found = False
    with get_products(target_date, service.id, insuree_id, adult, 'Service') as cursor:
        for (product_id, product_service_id, insuree_policy_effective_date, policy_effective_date, expiry_date,
             policy_stage) in cursor.fetchall():
            found = True
            core = __import__("core")
            insuree_policy_effective_date = core.datetime.date.from_ad_date(
                insuree_policy_effective_date)
            expiry_date = core.datetime.date.from_ad_date(expiry_date)
            product_service = ProductService.objects.get(pk=product_service_id)
            # START CHECK 17 --> Item/Service waiting period violation (17)
            if policy_stage == 'N' or policy_effective_date < insuree_policy_effective_date:
                if adult:
                    waiting_period = product_service.waiting_period_adult
                else:
                    waiting_period = product_service.waiting_period_adult
            if waiting_period and target_date < (insuree_policy_effective_date + datetimedelta(months=waiting_period)):
                claimservice.rejection_reason = REJECTION_REASON_WAITING_PERIOD_FAIL
                errors += [{'code': REJECTION_REASON_WAITING_PERIOD_FAIL,
                            'message': _("claim.validation.product_family.waiting_period") % {
                                'code': claimservice.claim.code,
                                'element': str(service)},
                            'detail': claimservice.claim.uuid}]

            # **** START CHECK 16 --> Item/Service Maximum provision (16)*****
            if adult:
                limit_no = product_service.limit_no_adult
            else:
                limit_no = product_service.limit_no_child
            if limit_no is not None and limit_no >= 0:
                # count qty provided
                total_qty_provided = ClaimService.objects\
                    .filter(claim__insuree_id=insuree_id)\
                    .filter(service_id=service_id)\
                    .annotate(target_date=Coalesce("claim__date_to", "claim__date_from"))\
                    .filter(target_date__gt=insuree_policy_effective_date).filter(target_date__lte=expiry_date)\
                    .filter(claim__status__gt=Policy.STATUS_ACTIVE)\
                    .filter(claim__validity_to__isnull=True)\
                    .filter(validity_to__isnull=True)\
                    .filter(rejection_reason=0)\
                    .filter(rejection_reason__isnull=True)\
                    .aggregate(Sum("qty_provided"))
                if total_qty_provided is None or total_qty_provided >= limit_no:
                    claimservice.rejection_reason = REJECTION_REASON_QTY_OVER_LIMIT
                    errors += [{'code': REJECTION_REASON_QTY_OVER_LIMIT,
                                'message': _("claim.validation.product_family.max_nb_allowed") % {
                                    'code': claimservice.claim.code,
                                    'element': str(service),
                                    'provided': total_qty_provided,
                                    'max': limit_no},
                                'detail': claimservice.claim.uuid}]

            # The following checks (TODO: extract them from this method) use various limits from the product
            # Each violation is meant to interrupt the validation
            product = Product.objects.filter(pk=product_id).first()
            # **** START CHECK 13 --> Maximum consultations (13)*****
            if base_category == 'C':
                if product.max_no_consultations is not None and product.max_no_consultations >= 0:
                    count = get_claim_queryset_by_category(expiry_date, insuree_id, insuree_policy_effective_date, 'C')\
                        .count()
                    if count and count >= product.max_no_consultations:
                        errors += [{'message': _("claim.validation.product_family.max_nb_consultations") % {
                            'code': claimservice.claim.code,
                            'count': count,
                            'max': product.max_no_consultations},
                            'detail': claimservice.claim.uuid}]
                        break

            # **** START CHECK 14 --> Maximum Surgeries (14)*****
            if base_category == 'S':
                if product.max_no_surgery is not None and product.max_no_surgery >= 0:
                    count = get_claim_queryset_by_category(expiry_date, insuree_id, insuree_policy_effective_date, 'S')\
                        .count()
                    if count and count >= product.max_no_surgery:
                        errors += [{'message': _("claim.validation.product_family.max_nb_surgeries") % {
                            'code': claimservice.claim.code,
                            'count': count,
                            'max': product.max_no_surgery},
                            'detail': claimservice.claim.uuid}]
                        break

            # **** START CHECK 15 --> Maximum Deliveries (15)*****
            if base_category == 'D':
                if product.max_no_delivery is not None and product.max_no_delivery >= 0:
                    count = get_claim_queryset_by_category(expiry_date, insuree_id, insuree_policy_effective_date, 'D')\
                        .count()
                    if count and count >= product.max_no_delivery:
                        errors += [{'message': _("claim.validation.product_family.max_nb_deliveries") % {
                            'code': claimservice.claim.code,
                            'count': count,
                            'max': product.max_no_delivery},
                            'detail': claimservice.claim.uuid}]
                        break

            # **** START CHECK 19 --> Maximum Antenatal  (19)*****
            if base_category == 'A':
                if product.max_no_antenatal is not None and product.max_no_antenatal >= 0:
                    count = get_claim_queryset_by_category(expiry_date, insuree_id, insuree_policy_effective_date, 'A')\
                        .count()
                    if count and count >= product.max_no_antenatal:
                        errors += [{'message': _("claim.validation.product_family.max_nb_antenatal") % {
                            'code': claimservice.claim.code,
                            'count': count,
                            'max': product.max_no_antenatal},
                            'detail': claimservice.claim.uuid}]
                        break

            # **** START CHECK 11 --> Maximum Hospital admissions (11)*****
            if base_category == 'H':
                if product.max_no_hospitalization is not None and product.max_no_hospitalization >= 0:
                    count = get_claim_queryset_by_category(expiry_date, insuree_id, insuree_policy_effective_date, 'H')\
                        .count()
                    if count and count >= product.max_no_hospitalization:
                        errors += [{'message': _("claim.validation.product_family.max_nb_hospitalizations") % {
                            'code': claimservice.claim.code,
                            'count': count,
                            'max': product.max_no_hospitalization},
                            'detail': claimservice.claim.uuid}]
                        break

            # **** START CHECK 12 --> Maximum Visits (OP) (12)*****
            if base_category == 'V':
                if product.max_no_visits is not None and product.max_no_visits >= 0:
                    count = get_claim_queryset_by_category(expiry_date, insuree_id, insuree_policy_effective_date, 'V')\
                        .count()
                    if count and count >= product.max_no_visits:
                        errors += [{'message': _("claim.validation.product_family.max_nb_visits") % {
                            'code': claimservice.claim.code,
                            'count': count,
                            'max': product.max_no_visits},
                            'detail': claimservice.claim.uuid}]
                        break

        if not found:
            claimservice.rejection_reason = REJECTION_REASON_NO_PRODUCT_FOUND
            errors += [{'code': REJECTION_REASON_NO_PRODUCT_FOUND,
                        'message': _("claim.validation.product_family.no_product_found") % {
                            'code': claimservice.claim.code,
                            'element': str(service)},
                        'detail': claimservice.claim.uuid}]

    return errors


def get_claim_queryset_by_category(expiry_date, insuree_id, insuree_policy_effective_date, category):
    queryset = Claim.objects \
        .filter(insuree_id=insuree_id) \
        .annotate(target_date=Coalesce("date_to", "date_from")) \
        .filter(target_date__gt=insuree_policy_effective_date) \
        .filter(target_date__lte=expiry_date) \
        .filter(status__gt=2) \
        .filter(validity_to__isnull=True)
    if category == 'V':
        queryset = queryset.filter(
            Q(category=category) | Q(category__isnull=True))
    else:
        queryset = queryset.filter(category=category)
    return queryset


def get_products(target_date, elt_id, insuree_id, adult, item_or_service):
    cursor = connection.cursor()
    waiting_period = "WaitingPeriodAdult" if adult else "WaitingPeriodChild"
    # about deductions and ceilings...
    # tblProduct.DedInsuree, tblProduct.DedOPInsuree, tblProduct.DedIPInsuree,
    # tblProduct.MaxInsuree, tblProduct.MaxOPInsuree, tblProduct.MaxIPInsuree,
    # tblProduct.DedTreatment, tblProduct.DedOPTreatment, tblProduct.DedIPTreatment,
    # tblProduct.MaxTreatment, tblProduct.MaxOPTreatment, tblProduct.MaxIPTreatment,
    # tblProduct.DedPolicy, tblProduct.DedOPPolicy, tblProduct.DedIPPolicy,
    # tblProduct.MaxPolicy, tblProduct.MaxOPPolicy, tblProduct.MaxIPPolicy
    sql = f"""
        SELECT 
            tblProduct.ProdID, tblProduct{item_or_service}s.Prod{item_or_service}ID,            
            tblInsureePolicy.EffectiveDate,
            tblPolicy.EffectiveDate,
            tblInsureePolicy.ExpiryDate,
            tblPolicy.PolicyStage
        FROM tblInsuree 
            INNER JOIN tblInsureePolicy ON tblInsureePolicy.InsureeID = tblInsuree.InsureeID
            LEFT OUTER JOIN tblPolicy
            LEFT OUTER JOIN  tblProduct ON tblPolicy.ProdID = tblProduct.ProdID
            INNER JOIN tblProduct{item_or_service}s ON tblProduct.ProdID = tblProduct{item_or_service}s.ProdID            
            RIGHT OUTER JOIN tblFamilies ON tblPolicy.FamilyID = tblFamilies.FamilyID
            ON tblInsuree.FamilyID = tblFamilies.FamilyID
        WHERE (tblInsuree.ValidityTo IS NULL) AND (tblInsuree.InsureeId = %s)
            AND (tblInsureePolicy.PolicyId = tblPolicy.PolicyID)
            AND (tblPolicy.ValidityTo IS NULL) AND (tblPolicy.EffectiveDate <= %s) AND (tblPolicy.ExpiryDate >= %s)
            AND (tblPolicy.PolicyStatus in ({Policy.STATUS_ACTIVE}, {Policy.STATUS_EXPIRED}))
            AND (tblProduct{item_or_service}s.ValidityTo IS NULL) AND (tblProduct{item_or_service}s.{item_or_service}ID = %s)
        ORDER BY DATEADD(m,ISNULL(tblProduct{item_or_service}s.{waiting_period}, 0),
            tblPolicy.EffectiveDate)            
    """
    cursor.execute(sql,
                   [insuree_id, target_date, target_date, elt_id])
    return cursor


def get_claim_category(claim):
    """
    Determine the claim category based on its services:
    S = Surgery
    D = Delivery
    A = Antenatal care
    H = Hospitalization
    C = Consultation
    O = Other
    V = Visit
    :param claim: claim for which category should be determined
    :return: category if a service is defined, None if not service at all
    """

    service_categories = OrderedDict([
        (Service.CATEGORY_SURGERY, "Surgery"),
        (Service.CATEGORY_DELIVERY, "Delivery"),
        (Service.CATEGORY_ANTENATAL, "Antenatal care"),
        (Service.CATEGORY_HOSPITALIZATION, "Hospitalization"),
        (Service.CATEGORY_CONSULTATION, "Consultation"),
        (Service.CATEGORY_OTHER, "Other"),
        (Service.CATEGORY_VISIT, "Visit"),
    ])
    claim_service_categories = [
        item["service__category"]
        for item in claim.services
        .filter(validity_to__isnull=True)
        .filter(service__validity_to__isnull=True)
        .values("service__category").distinct()
    ]
    for category in service_categories:
        if category in claim_service_categories:
            claim_category = category
            break
    else:
        # One might expect "O" here but the legacy code uses "V"
        claim_category = Service.CATEGORY_VISIT

    return claim_category


def validate_assign_prod_elt(claim, elt, elt_ref, elt_qs):
    """
    This method checks the limits for the family and the insuree, child or adult for their limits
    between the copay percentage and fixed limit.
    :return: List of errors, only if no product could be found for now
    """
    visit_type_field = {
        "O": ("limitation_type",  "limit_adult",  "limit_child"),
        "E": ("limitation_type_e", "limit_adult_e", "limit_child_e"),
        "R": ("limitation_type_r", "limit_adult_r", "limit_child_r"),
    }
    target_date = claim.date_to if claim.date_to else claim.date_from
    visit_type = claim.visit_type if claim.visit_type else "O"
    adult = claim.insuree.is_adult(target_date)
    (limitation_type_field, limit_adult, limit_child) = visit_type_field
    if elt.price_asked \
            and elt.price_approved \
            and elt.price_asked > elt.price_approved:
        claim_price = elt.price_asked
    else:
        claim_price = elt.price_approved

    product_elt_c = _query_product_item_service_limit(
        target_date, claim.insuree.family_id, elt_qs, limitation_type_field, "C",
        limit_adult if adult else limit_child
    )
    product_elt_f = _query_product_item_service_limit(
        target_date, claim.insuree.family_id, elt_qs, limitation_type_field, "F",
        limit_adult if adult else limit_child
    )
    if not product_elt_c and not product_elt_f:
        elt.rejection_reason = REJECTION_REASON_NO_PRODUCT_FOUND
        elt.save()
        return[{'code': REJECTION_REASON_NO_PRODUCT_FOUND,
                'message': _("claim.validation.assign_prod.elt.no_product_code") % {
                    'code': claim.code,
                    'elt': str(elt_ref)},
                'detail': claim.uuid}]

    if product_elt_f:
        fixed_limit = getattr(
            product_elt_f, limit_adult if adult else limit_child)
    else:
        fixed_limit = None

    if product_elt_c:
        co_sharing_percent = getattr(
            product_elt_c, limit_adult if adult else limit_child)
    else:
        co_sharing_percent = None

    # if both products exist, find the best one to use
    if product_elt_c and product_elt_f:
        if fixed_limit == 0 or fixed_limit > claim_price:
            product_elt = product_elt_f
            product_elt_c = None  # used in condition below
        else:
            if 100 - co_sharing_percent > 0:
                product_amount_own_f = claim_price - fixed_limit
                product_amount_own_c = (
                    1 - co_sharing_percent/100) * claim_price
                if product_amount_own_c > product_amount_own_f:
                    product_elt = product_elt_f
                    product_elt_c = None  # used in condition below
                else:
                    product_elt = product_elt_c
            else:
                product_elt = product_elt_c
    else:
        if product_elt_c:
            product_elt = product_elt_c
        else:
            product_elt = product_elt_f
            product_elt_c = None

    elt.product_id = product_elt.product_id
    elt.policy = product_elt\
        .product\
        .policies\
        .filter(effective_date__lte=target_date)\
        .filter(expiry_date__gte=target_date)\
        .filter(validity_to__isnull=True)\
        .filter(status__in=[Policy.STATUS_ACTIVE, Policy.STATUS_EXPIRED])\
        .filter(family_id=claim.insuree.family_id)\
        .first()
    elt.price_origin = product_elt.price_origin
    # The original code also sets claimservice.price_adjusted but it also always NULL
    if product_elt_c:
        elt.limitation = "C"
        elt.limitation_value = co_sharing_percent
    else:
        elt.limitation = "F"
        elt.limitation_value = fixed_limit
    elt.save()
    return []


def validate_assign_prod_to_claimitems_and_services(claim):
    errors = []
    for claimitem in claim.items.filter(validity_to__isnull=True) \
            .filter(rejection_reason=0).filter(rejection_reason__isnull=True):
        errors += validate_assign_prod_elt(
            claim, claimitem, claimitem.item,
            ProductItem.objects.filter(item_id=claimitem.item_id))

    for claimservice in claim.services.filter(validity_to__isnull=True) \
            .filter(rejection_reason=0).filter(rejection_reason__isnull=True):
        errors += validate_assign_prod_elt(
            claim,
            claimservice, claimservice.service,
            ProductService.objects.filter(service_id=claimservice_id))

    return errors


def _query_product_item_service_limit(target_date, family_id, elt_qs,
                                      limitation_field, limitation_type,
                                      limit_ordering):
    return elt_qs \
        .filter(product__policies__family_id=family_id) \
        .filter(product__policies__effective_date__lte=target_date) \
        .filter(product__policies__expiry_date__gte=target_date) \
        .filter(product__policies__validity_to__isnull=True) \
        .filter(validity_to__isnull=True) \
        .filter(product__policies__status__in=[Policy.STATUS_ACTIVE, Policy.STATUS_EXPIRED]) \
        .filter(product__validity_to__isnull=True) \
        .filter(**{limitation_field: limitation_type})\
        .order_by("-" + limit_ordering)\
        .first()

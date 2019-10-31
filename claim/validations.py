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
from medical_pricelist.models import ItemPricelistDetail, ServicePricelistDetail
from policy.models import Policy
from product.models import Product, ProductItem, ProductService
from .apps import ClaimConfig

REJECTION_REASON_INVALID_ITEM_OR_SERVICE = 1
REJECTION_REASON_NOT_IN_PRICE_LIST = 2
REJECTION_REASON_NO_PRODUCT_FOUND = 3
REJECTION_REASON_CATEGORY_LIMITATION = 4
# REJECTION_REASON_FREQUENCY_FAILURE = 5
# REJECTION_REASON_DUPLICATED = 6
REJECTION_REASON_FAMILY = 7
# REJECTION_REASON_ICD_NOT_IN_LIST = 8
REJECTION_REASON_TARGET_DATE = 9
REJECTION_REASON_ITEM_CARE_TYPE = 10
REJECTION_REASON_MAX_HOSPITAL_ADMISSIONS = 11
REJECTION_REASON_MAX_VISITS = 12
REJECTION_REASON_MAX_CONSULTATIONS = 13
REJECTION_REASON_MAX_SURGERIES = 14
REJECTION_REASON_MAX_DELIVERIES = 15
REJECTION_REASON_QTY_OVER_LIMIT = 16
REJECTION_REASON_WAITING_PERIOD_FAIL = 17
REJECTION_REASON_MAX_ANTENATAL = 19


def validate_claim(claim):
    """
    Based on the legacy validation, this method returns standard codes along with details
    :param claim: claim to be verified
    :return: (result_code, error_details)
    """
    if ClaimConfig.default_validations_disabled:
        return []
    errors = []
    errors += validate_family(claim, claim.insuree)

    if len(errors) == 0:
        errors += validate_target_date(claim)

    if len(errors) == 0:
        errors += validate_claimitems(claim)
        errors += validate_claimservices(claim)

    return errors


def validate_claimitems(claim):
    errors = []
    target_date = claim.date_from if claim.date_from else claim.date_to

    for claimitem in claim.items.filter(validity_to__isnull=True):
        claimitem.rejection_reason = None
        errors += validate_claimitem_validity(claimitem)
        errors += validate_claimitem_in_price_list(claim, claimitem)
        errors += validate_claimitem_care_type(claim, claimitem)
        errors += validate_claimitem_limitation_fail(claim, claimitem)
        errors += validate_item_product_family(
            claimitem=claimitem,
            target_date=target_date,
            item=claimitem.item,
            family_id=claim.insuree.family_id,
            insuree_id=claim.insuree_id,
            adult=claim.insuree.is_adult(target_date)
        )
        if claimitem.rejection_reason:
            claimitem.status = ClaimItem.STATUS_REJECTED
        else:
            claimitem.status = ClaimItem.STATUS_PASSED
        claimitem.save()
    return errors


def validate_claimitem_in_price_list(claim, claimitem):
    pricelist_detail = ItemPricelistDetail.objects\
        .filter(item_pricelist=claim.health_facility.item_pricelist)\
        .filter(item_id=claimitem.item_id)\
        .filter(validity_to__isnull=True)\
        .filter(item_pricelist__validity_to__isnull=True)\
        .first()
    if pricelist_detail:
        return []
    else:
        claimitem.rejection_reason = REJECTION_REASON_NOT_IN_PRICE_LIST
        return [{'code': REJECTION_REASON_NOT_IN_PRICE_LIST,
                 'message': _("claim.validation.pricelist.item") % {
                     'code': claim.code,
                     'claim_item': str(claimitem.item),
                     'health_facility': str(claim.health_facility)},
                 'detail': claim.uuid}]


def validate_claimservice_in_price_list(claim, claimservice):
    pricelist_detail = ServicePricelistDetail.objects\
        .filter(service_pricelist=claim.health_facility.service_pricelist)\
        .filter(service_id=claimservice.service_id)\
        .filter(validity_to__isnull=True)\
        .filter(service_pricelist__validity_to__isnull=True)\
        .first()
    if pricelist_detail:
        return []
    else:
        claimservice.rejection_reason = REJECTION_REASON_NOT_IN_PRICE_LIST
        return [{'code': REJECTION_REASON_NOT_IN_PRICE_LIST,
                 'message': _("claim.validation.pricelist.service") % {
                     'code': claim.code,
                     'claim_service': str(claimservice.service),
                     'health_facility': str(claim.health_facility)},
                 'detail': claim.uuid}]


def validate_claimservices(claim):
    errors = []
    target_date = claim.date_from if claim.date_from else claim.date_to
    base_category = get_claim_category(claim)

    for claimservice in claim.services.all():
        claimservice.rejection_reason = None
        errors += validate_claimservice_validity(claimservice)
        errors += validate_claimservice_in_price_list(claim, claimservice)
        errors += validate_claimservice_care_type(claim, claimservice)
        errors += validate_claimservice_limitation_fail(claim, claimservice)
        errors += validate_service_product_family(
            claimservice=claimservice,
            target_date=target_date,
            service=claimservice.service,
            family_id=claim.insuree.family_id,
            insuree_id=claim.insuree_id,
            adult=claim.insuree.is_adult(target_date),
            base_category=base_category,
        )
        if claimservice.rejection_reason:
            claimservice.status = ClaimItem.STATUS_REJECTED
        else:
            claimservice.status = ClaimItem.STATUS_PASSED
        claimservice.save()
    return errors


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
        return [{'code': REJECTION_REASON_INVALID_ITEM_OR_SERVICE,
                 'message': _("claim.validation.validity.item") % {
                     'code': claimitem.claim.code,
                     'item': str(claimitem.item)},
                 'detail': claimitem.claim.uuid}]
    return []


def validate_claimservice_validity(claimservice):
    # See note in validate_claimitem_validity
    if claimservice.validity_to is None and claimservice.service.validity_to is not None:
        claimservice.rejection_reason = REJECTION_REASON_INVALID_ITEM_OR_SERVICE
        return [{'code': REJECTION_REASON_INVALID_ITEM_OR_SERVICE,
                 'message': _("claim.validation.validity.service") % {
                     'code': claimservice.claim.code,
                     'service': str(claimservice.service)},
                 'detail': claimservice.claim.uuid}]
    return []


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
        claimservice.rejection_reason = REJECTION_REASON_ITEM_CARE_TYPE
        return [{'code': REJECTION_REASON_ITEM_CARE_TYPE,
                 'message': _("claim.validation.care_type.service") % {
                     'code': claim.code,
                     'care_type': care_type,
                     'hf_care_type': hf_care_type,
                     'target_date': target_date,
                     'claim_date_from': claim.date_from},
                 'detail': claim.uuid}]
    else:
        return []


def validate_target_date(claim):
    if claim.date_from is None and claim.date_to is None:
        claim.reject(REJECTION_REASON_TARGET_DATE)
        return [{'code': REJECTION_REASON_TARGET_DATE,
                 'message': _("claim.validation.target_date") % {
                     'code': claim.code},
                 'detail': claim.uuid}]
    return []


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
        claimitem.rejection_reason = REJECTION_REASON_ITEM_CARE_TYPE
        return [{'code': REJECTION_REASON_ITEM_CARE_TYPE,
                 'message': _("claim.validation.care_type.item") % {
                     'code': claim.code,
                     'care_type': care_type,
                     'hf_care_type': hf_care_type,
                     'target_date': target_date,
                     'claim_date_from': claim.date_from},
                 'detail': claim.uuid}]
    else:
        return []


def validate_claimitem_limitation_fail(claim, claimitem):
    target_date = claim.date_to if claim.date_to else claim.date_from
    patient_category_mask = utils.patient_category_mask(
        claim.insuree, target_date)

    if claimitem.item.patient_category & patient_category_mask != patient_category_mask:
        claimitem.rejection_reason = REJECTION_REASON_CATEGORY_LIMITATION
        return [{'code': REJECTION_REASON_CATEGORY_LIMITATION,
                 'message': _("claim.validation.limitation.item") % {
                     'code': claim.code,
                     'item': str(claimitem.item),
                     'patient_category': claimitem.item.patient_category,
                     'patient_category_mask': patient_category_mask},
                 'detail': claim.uuid}]
    else:
        return []


def validate_claimservice_limitation_fail(claim, claimservice):
    target_date = claim.date_to if claim.date_to else claim.date_from
    patient_category_mask = utils.patient_category_mask(
        claim.insuree, target_date)
    if claimservice.service.patient_category & patient_category_mask != patient_category_mask:
        claimservice.rejection_reason = REJECTION_REASON_CATEGORY_LIMITATION
        return [{'code': REJECTION_REASON_CATEGORY_LIMITATION,
                 'message': _("claim.validation.limitation.service") % {
                     'code': claim.code,
                     'service': str(claimservice.service),
                     'patient_category': claimservice.service.patient_category,
                     'patient_category_mask': patient_category_mask},
                 'detail': claim.uuid}]
    else:
        return []


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


def validate_item_product_family(claimitem, target_date, item, family_id, insuree_id, adult):
    errors = []
    found = False
    with get_products(target_date, item.id, family_id, insuree_id, adult, items=True) as cursor:
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
def validate_service_product_family(claimservice, target_date, service, family_id, insuree_id, adult, base_category):
    errors = []
    found = False
    with get_products(target_date, service.id, family_id, insuree_id, adult, items=False) as cursor:
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


def get_products(target_date, item_id, family_id, insuree_id, adult, items=True):
    cursor = connection.cursor()
    item_or_product = "Item" if items else "Service"
    waiting_period = "WaitingPeriodAdult" if adult else "WaitingPeriodChild"
    cursor.execute(f"""
                    SELECT  TblProduct.ProdID , tblProduct{item_or_product}s.Prod{item_or_product}ID ,
                        tblInsureePolicy.EffectiveDate,
                        tblPolicy.EffectiveDate, tblInsureePolicy.ExpiryDate, tblPolicy.PolicyStage
                        FROM tblFamilies
                         INNER JOIN tblPolicy ON tblFamilies.FamilyID = tblPolicy.FamilyID
                         INNER JOIN tblProduct ON tblPolicy.ProdID = tblProduct.ProdID
                         INNER JOIN tblProduct{item_or_product}s
                            ON tblProduct.ProdID = tblProduct{item_or_product}s.ProdID
                         INNER JOIN tblInsureePolicy ON tblPolicy.PolicyID = tblInsureePolicy.PolicyId
                        WHERE (tblPolicy.EffectiveDate <= %s)
                        AND (tblPolicy.ExpiryDate >= %s)
                        AND (tblPolicy.ValidityTo IS NULL)
                        AND (tblProduct{item_or_product}s.ValidityTo IS NULL)
                        AND (tblPolicy.PolicyStatus = {Policy.STATUS_ACTIVE}
                            OR tblPolicy.PolicyStatus = {Policy.STATUS_EXPIRED})
                        AND (tblProduct{item_or_product}s.{item_or_product}ID = %s)
                        AND (tblFamilies.FamilyID = %s)
                        AND (tblProduct.ValidityTo IS NULL)
                        AND (tblInsureePolicy.EffectiveDate <= %s)
                        AND (tblInsureePolicy.ExpiryDate >= %s)
                        AND (tblInsureePolicy.InsureeId = %s)
                        AND (tblInsureePolicy.ValidityTo IS NULL)
                        ORDER BY DATEADD(m,ISNULL(tblProduct{item_or_product}s.{waiting_period}, 0),
                         tblInsureePolicy.EffectiveDate)
                   """,
                   [target_date, target_date, item_id, family_id, target_date, target_date, insuree_id])
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


def validate_assign_prod_to_claimitems(claim):
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
    errors = []
    target_date = claim.date_to if claim.date_to else claim.date_from
    visit_type = claim.visit_type if claim.visit_type else "O"
    adult = claim.insuree.is_adult(target_date)
    (limitation_type_field, limit_adult,
     limit_child) = visit_type_field[visit_type]

    for claimitem in claim.items.filter(validity_to__isnull=True) \
            .filter(rejection_reason=0).filter(rejection_reason__isnull=True):
        if claimitem.price_asked \
                and claimitem.price_approved \
                and claimitem.price_asked > claimitem.price_approved:
            claim_price = claimitem.price_asked
        else:
            claim_price = claimitem.price_approved

        product_item_c = _query_product_item_service_limit(
            target_date, claim.insuree.family_id, claimitem.item, None, limitation_type_field,
            limit_adult if adult else limit_child, "C"
        )
        product_item_f = _query_product_item_service_limit(
            target_date, claim.insuree.family_id, claimitem.item, None, limitation_type_field,
            limit_adult if adult else limit_child, "F"
        )
        if not product_item_c and not product_item_f:
            claimitem.rejection_reason = REJECTION_REASON_NO_PRODUCT_FOUND
            errors.append({'code': REJECTION_REASON_NO_PRODUCT_FOUND,
                           'message': _("claim.validation.assign_prod.item.no_product_code") % {
                               'code': claim.code,
                               'item': str(claimitem.item)},
                           'detail': claim.uuid})
            continue

        if product_item_f:
            fixed_limit = getattr(
                product_item_f, limit_adult if adult else limit_child)
        else:
            fixed_limit = None
        if product_item_c:
            co_sharing_percent = getattr(
                product_item_c, limit_adult if adult else limit_child)
        else:
            co_sharing_percent = None

        # if both products exist, find the best one to use
        if product_item_c and product_item_f:
            if fixed_limit == 0 or fixed_limit > claim_price:
                product_item = product_item_f
                product_item_c = None  # used in condition below
            else:
                if 100 - co_sharing_percent > 0:
                    product_amount_own_f = claim_price - fixed_limit
                    product_amount_own_c = (
                        1 - co_sharing_percent/100) * claim_price
                    if product_amount_own_c > product_amount_own_f:
                        product_item = product_item_f
                        product_item_c = None  # used in condition below
                    else:
                        product_item = product_item_c
                else:
                    product_item = product_item_c
        else:
            if product_item_c:
                product_item = product_item_c
            else:
                product_item = product_item_f
                product_item_c = None

        claimitem.product_id = product_item.product_id
        claimitem.policy = product_item\
            .product\
            .policies\
            .filter(effective_date__lte=target_date)\
            .filter(expiry_date__gte=target_date)\
            .filter(validity_to__isnull=True)\
            .filter(status__in=[Policy.STATUS_ACTIVE, Policy.STATUS_EXPIRED])\
            .filter(family_id=claim.insuree.family_id)\
            .first()
        claimitem.price_origin = product_item.price_origin
        # The original code also sets claimitem.price_adjusted but it also always NULL
        if product_item_c:
            claimitem.limitation = "C"
            claimitem.limitation_value = co_sharing_percent
        else:
            claimitem.limitation = "F"
            claimitem.limitation_value = fixed_limit
        claimitem.save()

    # TODO: this code is duplicated. They will be merged after the behaviour has been verified in isolation. Most
    # of the code can be used indifferently with services rather than items.
    for claimservice in claim.services.filter(validity_to__isnull=True) \
            .filter(rejection_reason=0).filter(rejection_reason__isnull=True):
        claim_service.save_history()
        if claimservice.price_asked \
                and claimservice.price_approved \
                and claimservice.price_asked > claimservice.price_approved:
            claim_price = claimservice.price_asked
        else:
            claim_price = claimservice.price_approved

        product_service_c = _query_product_item_service_limit(
            target_date, claim.insuree.family_id, None, claimservice.service, limitation_type_field,
            limit_adult if adult else limit_child, "C"
        )
        product_service_f = _query_product_item_service_limit(
            target_date, claim.insuree.family_id, None, claimservice.service, limitation_type_field,
            limit_adult if adult else limit_child, "F"
        )

        if not product_service_c and not product_service_f:
            claimservice.rejection_reason = REJECTION_REASON_NO_PRODUCT_FOUND
            errors.append({'code': REJECTION_REASON_NO_PRODUCT_FOUND,
                           'message': _("claim.validation.assign_prod.service.no_product_code") % {
                               'code': claim.code,
                               'service': str(claimservice.service)},
                           'detail': claim.uuid})
            continue

        if product_service_f:
            fixed_limit = getattr(
                product_service_f, limit_adult if adult else limit_child)
        else:
            fixed_limit = None
        if product_service_c:
            co_sharing_percent = getattr(
                product_service_c, limit_adult if adult else limit_child)
        else:
            co_sharing_percent = None

        # if both products exist, find the best one to use
        if product_service_c and product_service_f:
            if fixed_limit == 0 or fixed_limit > claim_price:
                product_service = product_service_f
                product_service_c = None  # used in condition below
            else:
                if 100 - co_sharing_percent > 0:
                    product_amount_own_f = claim_price - fixed_limit
                    product_amount_own_c = (
                        1 - co_sharing_percent/100) * claim_price
                    if product_amount_own_c > product_amount_own_f:
                        product_service = product_service_f
                        product_service_c = None  # used in condition below
                    else:
                        product_service = product_service_c
                else:
                    product_service = product_service_c
        else:
            if product_service_c:
                product_service = product_service_c
            else:
                product_service = product_service_f
                product_service_c = None

        claimservice.product_id = product_service.product_id
        claimservice.policy = product_service\
            .product\
            .policies\
            .filter(effective_date__lte=target_date)\
            .filter(expiry_date__gte=target_date)\
            .filter(validity_to__isnull=True)\
            .filter(status__in=[Policy.STATUS_ACTIVE, Policy.STATUS_EXPIRED])\
            .filter(family_id=claim.insuree.family_id)\
            .first()
        claimservice.price_origin = product_service.price_origin
        # The original code also sets claimservice.price_adjusted but it also always NULL
        if product_service_c:
            claimservice.limitation = "C"
            claimservice.limitation_value = co_sharing_percent
        else:
            claimservice.limitation = "F"
            claimservice.limitation_value = fixed_limit
        claimservice.save()

    return errors


def _query_product_item_service_limit(target_date, family_id, item_id, service_id, limitation_field,
                                      limit_ordering, limitation_type):
    if item_id:
        qs = ProductItem.objects.filter(item_id=item_id)
    else:
        qs = ProductService.objects.filter(service_id=service_id)
    return qs \
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

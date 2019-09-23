from collections import OrderedDict
from typing import List

from claim.models import ClaimItem, Claim, ClaimService
from core import utils
from core.datetimes.shared import datetimedelta
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models import Sum, Q, Value
from django.db.models.functions import Coalesce
from medical_pricelist.models import ItemPricelistDetail, ServicePricelistDetail
from policy.models import Policy
from product.models import Product, ProductItem, ProductService
from medical.models import Item, Service

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


def validate_claim(claim) -> List[ValidationError]:
    """
    Based on the legacy validation, this method returns standard codes along with details
    :param claim: claim to be verified
    :return: (result_code, error_details)
    """
    errors = []
    errors += validate_family(claim, claim.insuree)

    if len(errors) == 0:
        errors += validate_target_date(claim)

    if len(errors) == 0:
        errors += validate_claimitems(claim)
        errors += validate_claimservices(claim)

    return errors


def validate_claimitems(claim) -> List[ValidationError]:
    errors = []
    target_date = claim.date_from if claim.date_from else claim.date_to

    for claimitem in claim.items.filter(validity_to__isnull=True):
        errors += validate_claimitem_validity(claimitem)
        errors += validate_claimitem_in_price_list(claim, claimitem)
        errors += validate_claimitem_care_type(claim, claimitem)
        errors += validate_claimitem_limitation_fail(claim, claimitem)
        errors += validate_item_product_family(
            claimitem=claimitem,
            target_date=target_date,
            item_id=claimitem.item_id,
            family_id=claim.insuree.family_id,
            insuree_id=claim.insuree_id,
            adult=claim.insuree.is_adult(target_date)
        )

    return errors


def validate_claimitem_in_price_list(claim, claimitem):
    pricelist_detail = ItemPricelistDetail.objects\
        .filter(item_pricelist__location_id=claim.health_facility_id)\
        .filter(item_id=claimitem.item_id)\
        .filter(validity_to__isnull=True)\
        .filter(item_pricelist__validity_to__isnull=True)\
        .first()
    if pricelist_detail:
        return []
    else:
        claimitem.rejection_reason = REJECTION_REASON_NOT_IN_PRICE_LIST
        claimitem.save()
        return [ValidationError("Couldn't find a valid item pricelist item for %s in location %s",
                                params=(claimitem.item_id, claim.health_facility_id),
                                code=REJECTION_REASON_NOT_IN_PRICE_LIST)]


def validate_claimservice_in_price_list(claim, claimservice):
    pricelist_detail = ServicePricelistDetail.objects\
        .filter(service_pricelist__location_id=claim.health_facility_id)\
        .filter(service_id=claimservice.service_id)\
        .filter(validity_to__isnull=True)\
        .filter(service_pricelist__validity_to__isnull=True)\
        .first()
    if pricelist_detail:
        return []
    else:
        claimservice.rejection_reason = REJECTION_REASON_NOT_IN_PRICE_LIST
        claimservice.save()
        return [ValidationError("Couldn't find a valid service pricelist item for %s in location %s",
                                params=(claimservice.service_id, claim.health_facility_id),
                                code=REJECTION_REASON_NOT_IN_PRICE_LIST)]


def validate_claimservices(claim):
    errors = []
    target_date = claim.date_from if claim.date_from else claim.date_to
    base_category = get_claim_category(claim)

    for claimservice in claim.services.all():
        errors += validate_claimservice_validity(claimservice)
        errors += validate_claimservice_in_price_list(claim, claimservice)
        errors += validate_claimservice_care_type(claim, claimservice)
        errors += validate_claimservice_limitation_fail(claim, claimservice)
        errors += validate_service_product_family(
            claimservice=claimservice,
            target_date=target_date,
            service_id=claimservice.service_id,
            family_id=claim.insuree.family_id,
            insuree_id=claim.insuree_id,
            adult=claim.insuree.is_adult(target_date),
            base_category=base_category,
        )
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
        claimitem.save()
        return [ValidationError("Claim Item %s is referencing item %s that is invalid",
                                params=(claimitem.id, claimitem.item_id),
                                code=REJECTION_REASON_INVALID_ITEM_OR_SERVICE)]
    return []


def validate_claimservice_validity(claimservice):
    # See note in validate_claimitem_validity
    if claimservice.validity_to is None and claimservice.service.validity_to is not None:
        claimservice.rejection_reason = REJECTION_REASON_INVALID_ITEM_OR_SERVICE
        claimservice.save()
        return [ValidationError("Claim Service %s is referencing service %s that is invalid",
                                params=(claimservice.id, claimservice.service_id),
                                code=REJECTION_REASON_INVALID_ITEM_OR_SERVICE)]
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
        claimservice.save()
        return [ValidationError("Care type %s and health facility care type %s with date %s vs %s",
                                params=[care_type, hf_care_type, target_date, claim.date_from],
                                code=REJECTION_REASON_ITEM_CARE_TYPE)]
    else:
        return []


def validate_target_date(claim):
    if claim.date_from is None and claim.date_to is None:
        claim.reject(REJECTION_REASON_TARGET_DATE)
        return ValidationError("Claim %s: neither date_from nor date_to is specified", params=claim.id,
                               code=REJECTION_REASON_TARGET_DATE)
    else:
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
        claimitem.save()
        return [ValidationError("Care type %s and health facility care type %s with date %s vs %s",
                                params=[care_type, hf_care_type, target_date, claim.date_from],
                                code=REJECTION_REASON_ITEM_CARE_TYPE)]
    else:
        return []


def validate_claimitem_limitation_fail(claim, claimitem):
    target_date = claim.date_to if claim.date_to else claim.date_from
    patient_category_mask = utils.patient_category_mask(claim.insuree, target_date)

    if claimitem.item.patient_category & patient_category_mask != patient_category_mask:
        claimitem.rejection_reason = REJECTION_REASON_CATEGORY_LIMITATION
        claimitem.save()
        return [ValidationError("ClaimItem %s referencing item %s has a patient category mask of %s but insuree has "
                                "a mask of %s",
                                params=(claimitem.id, claimitem.item_id, claimitem.item.patient_category,
                                        patient_category_mask),
                                code=REJECTION_REASON_CATEGORY_LIMITATION)]
    else:
        return []


def validate_claimservice_limitation_fail(claim, claimservice):
    target_date = claim.date_to if claim.date_to else claim.date_from
    patient_category_mask = utils.patient_category_mask(claim.insuree, target_date)

    if claimservice.service.patient_category & patient_category_mask != patient_category_mask:
        claimservice.rejection_reason = REJECTION_REASON_CATEGORY_LIMITATION
        claimservice.save()
        return [ValidationError("ClaimService %s referencing service %s has a patient category mask of %s but insuree "
                                "has a mask of %s",
                                params=(claimservice.id, claimservice.service_id, claimservice.service.patient_category,
                                        patient_category_mask),
                                code=REJECTION_REASON_CATEGORY_LIMITATION)]
    else:
        return []


def validate_family(claim, insuree) -> List[ValidationError]:
    errors = []
    if insuree.validity_to is not None:
        errors += [ValidationError("Insuree %s validity expired", params=insuree.id, code=REJECTION_REASON_FAMILY)]
    if insuree.family is None:
        errors += [ValidationError("Insuree %s should have a family, even if only one member", params=insuree.id,
                                   code=REJECTION_REASON_FAMILY)]
    else:
        if insuree.family.validity_to is not None:
            errors += [ValidationError("Insuree %s family validity expired", params=insuree.id,
                                       code=REJECTION_REASON_FAMILY)]

    if len(errors) > 0:
        claim.reject(REJECTION_REASON_FAMILY)
    return errors


def validate_item_product_family(claimitem, target_date, item_id, family_id, insuree_id, adult):
    errors = []
    found = False
    with get_products(target_date, item_id, family_id, insuree_id, adult, items=True) as cursor:
        for (product_id, product_item_id, insuree_policy_effective_date, policy_effective_date, expiry_date,
             policy_stage) in cursor.fetchall():
            found = True
            core = __import__("core")
            insuree_policy_effective_date = core.datetime.date.from_ad_date(insuree_policy_effective_date)
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
                claimitem.save()
                errors += [ValidationError("Item/service %s waiting period violation", params=item_id,
                                           code=REJECTION_REASON_WAITING_PERIOD_FAIL)]

            # **** START CHECK 16 --> Item/Service Maximum provision (16)*****
            if adult:
                limit_no = product_item.limit_no_adult
            else:
                limit_no = product_item.limit_no_child
            if limit_no is not None and limit_no >= 0:
                # count qty provided
                total_qty_provided = ClaimItem.objects\
                    .filter(claim__insuree_id=insuree_id)\
                    .filter(item_id=item_id)\
                    .annotate(target_date=Coalesce("claim__date_to", "claim__date_from"))\
                    .filter(target_date__gt=insuree_policy_effective_date).filter(target_date__lte=expiry_date)\
                    .filter(claim__status__gt=Policy.POLICY_STATUS_ACTIVE)\
                    .filter(claim__validity_to__isnull=True)\
                    .filter(validity_to__isnull=True)\
                    .filter(rejection_reason=0)\
                    .aggregate(Sum("qty_provided"))
                if total_qty_provided is None or total_qty_provided >= limit_no:
                    claimitem.rejection_reason = REJECTION_REASON_QTY_OVER_LIMIT
                    claimitem.save()
                    errors += [ValidationError("Item %s, provided %s over maximum number allowed %s",
                                               params=(item_id, total_qty_provided, limit_no),
                                               code=REJECTION_REASON_QTY_OVER_LIMIT)]
        if not found:
            claimitem.rejection_reason = REJECTION_REASON_NO_PRODUCT_FOUND
            claimitem.save()
            errors += [ValidationError("Not product item found for %s", params=item_id,
                                       code=REJECTION_REASON_NO_PRODUCT_FOUND)]

    return errors


# noinspection DuplicatedCode
def validate_service_product_family(claimservice, target_date, service_id, family_id, insuree_id, adult, base_category):
    errors = []
    found = False
    with get_products(target_date, service_id, family_id, insuree_id, adult, items=False) as cursor:
        for (product_id, product_service_id, insuree_policy_effective_date, policy_effective_date, expiry_date,
             policy_stage) in cursor.fetchall():
            found = True
            core = __import__("core")
            insuree_policy_effective_date = core.datetime.date.from_ad_date(insuree_policy_effective_date)
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
                claimservice.save()
                errors += [ValidationError("Item/service %s waiting period violation", params=service_id,
                                           code=REJECTION_REASON_WAITING_PERIOD_FAIL)]

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
                    .filter(claim__status__gt=Policy.POLICY_STATUS_ACTIVE)\
                    .filter(claim__validity_to__isnull=True)\
                    .filter(validity_to__isnull=True)\
                    .filter(rejection_reason=0)\
                    .aggregate(Sum("qty_provided"))
                if total_qty_provided is None or total_qty_provided >= limit_no:
                    claimservice.rejection_reason = REJECTION_REASON_QTY_OVER_LIMIT
                    claimservice.save()
                    errors += [ValidationError("Service %s, provided %s over maximum number allowed %s",
                                               params=(service_id, total_qty_provided, limit_no),
                                               code=REJECTION_REASON_QTY_OVER_LIMIT)]

            # The following checks (TODO: extract them from this method) use various limits from the product
            # Each violation is meant to interrupt the validation
            product = Product.objects.filter(pk=product_id).first()
            # **** START CHECK 13 --> Maximum consultations (13)*****
            if base_category == 'C':
                if product.max_no_consultations is not None and product.max_no_consultations >= 0:
                    count = get_claim_queryset_by_category(expiry_date, insuree_id, insuree_policy_effective_date, 'C')\
                        .count()
                    if count and count >= product.max_no_consultations:
                        errors += [ValidationError("%s is over maximum consultations %s",
                                                   params=(count, product.max_no_consultations),
                                                   code=REJECTION_REASON_MAX_CONSULTATIONS)]
                        break

            # **** START CHECK 14 --> Maximum Surgeries (14)*****
            if base_category == 'S':
                if product.max_no_surgery is not None and product.max_no_surgery >= 0:
                    count = get_claim_queryset_by_category(expiry_date, insuree_id, insuree_policy_effective_date, 'S')\
                        .count()
                    if count and count >= product.max_no_surgery:
                        errors += [ValidationError("%s is over maximum surgery %s",
                                                   params=(count, product.max_no_surgery),
                                                   code=REJECTION_REASON_MAX_SURGERIES)]
                        break

            # **** START CHECK 15 --> Maximum Deliveries (15)*****
            if base_category == 'D':
                if product.max_no_delivery is not None and product.max_no_delivery >= 0:
                    count = get_claim_queryset_by_category(expiry_date, insuree_id, insuree_policy_effective_date, 'D')\
                        .count()
                    if count and count >= product.max_no_delivery:
                        errors += [ValidationError("%s is over maximum deliveries %s",
                                                   params=(count, product.max_no_delivery),
                                                   code=REJECTION_REASON_MAX_DELIVERIES)]
                        break

            # **** START CHECK 19 --> Maximum Antenatal  (19)*****
            if base_category == 'A':
                if product.max_no_antenatal is not None and product.max_no_antenatal >= 0:
                    count = get_claim_queryset_by_category(expiry_date, insuree_id, insuree_policy_effective_date, 'A')\
                        .count()
                    if count and count >= product.max_no_antenatal:
                        errors += [ValidationError("%s is over maximum antenatal %s",
                                                   params=(count, product.max_no_antenatal),
                                                   code=REJECTION_REASON_MAX_ANTENATAL)]
                        break

            # **** START CHECK 11 --> Maximum Hospital admissions (11)*****
            if base_category == 'H':
                if product.max_no_hospitalization is not None and product.max_no_hospitalization >= 0:
                    count = get_claim_queryset_by_category(expiry_date, insuree_id, insuree_policy_effective_date, 'H')\
                        .count()
                    if count and count >= product.max_no_hospitalization:
                        errors += [ValidationError("%s is over maximum hospitalizations %s",
                                                   params=(count, product.max_no_hospitalization),
                                                   code=REJECTION_REASON_MAX_HOSPITAL_ADMISSIONS)]
                        break

            # **** START CHECK 12 --> Maximum Visits (OP) (12)*****
            if base_category == 'V':
                if product.max_no_visits is not None and product.max_no_visits >= 0:
                    count = get_claim_queryset_by_category(expiry_date, insuree_id, insuree_policy_effective_date, 'V')\
                        .count()
                    if count and count >= product.max_no_visits:
                        errors += [ValidationError("%s is over maximum visits %s",
                                                   params=(count, product.max_no_visits),
                                                   code=REJECTION_REASON_MAX_VISITS)]
                        break

        if not found:
            claimservice.rejection_reason = REJECTION_REASON_NO_PRODUCT_FOUND
            claimservice.save()
            errors += [ValidationError("No product service found for %s", params=service_id,
                                       code=REJECTION_REASON_NO_PRODUCT_FOUND)]

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
        queryset = queryset.filter(Q(category=category) | Q(category__isnull=True))
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
        claim_category = Service.CATEGORY_VISIT  # One might expect "O" here but the legacy code uses "V"

    return claim_category

import json

import graphene
from claim.validations import validate_claim, get_claim_category, validate_assign_prod_to_claimitems
from core import prefix_filterset, ExtendedConnection, filter_validity, Q
from core.schema import TinyInt, SmallInt, OpenIMISMutation, OrderedDjangoFilterConnectionField
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.db.models.functions import Coalesce
from graphene import InputObjectType
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField
from insuree.schema import InsureeGQLType
from location.schema import HealthFacilityGQLType
from medical.schema import DiagnosisGQLType
from location.schema import userDistricts

from .models import Claim, ClaimAdmin, ClaimOfficer, Feedback, ClaimItem, ClaimService


class ClaimAdminGQLType(DjangoObjectType):
    """
    Details about a Claim Administrator
    """

    class Meta:
        model = ClaimAdmin
        exclude_fields = ('row_id',)
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            "id": ["exact"],
            "code": ["exact", "icontains"],
            "last_name": ["exact", "icontains"],
            "other_names": ["exact", "icontains"],
        }
        connection_class = ExtendedConnection


class ClaimOfficerGQLType(DjangoObjectType):
    """
    Details about a Claim Officer
    """

    class Meta:
        model = ClaimOfficer
        exclude_fields = ('row_id',)
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            "id": ["exact"],
            "code": ["exact", "icontains"],
            "last_name": ["exact", "icontains"],
            "other_names": ["exact", "icontains"],
        }
        connection_class = ExtendedConnection


class ClaimGQLType(DjangoObjectType):
    """
    Main element for a Claim. It can contain items and/or services.
    The filters are possible on BatchRun, Insuree, HealthFacility, Admin and ICD in addition to the Claim fields
    themselves.
    """

    class Meta:
        model = Claim
        exclude_fields = ('row_id',)
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            "id": ["exact"],
            "code": ["exact", "istartswith", "icontains", "iexact"],
            "status": ["exact"],
            "date_claimed": ["exact", "lt", "lte", "gt", "gte"],
            "date_from": ["exact", "lt", "lte", "gt", "gte"],
            "date_to": ["exact", "lt", "lte", "gt", "gte"],
            "feedback_status": ["exact"],
            "review_status": ["exact"],
            "claimed": ["exact", "lt", "lte", "gt", "gte"],
            "approved": ["exact", "lt", "lte", "gt", "gte"],
            "visit_type": ["exact"],
            **prefix_filterset("icd__", DiagnosisGQLType._meta.filter_fields),
            **prefix_filterset("admin__", ClaimAdminGQLType._meta.filter_fields),
            **prefix_filterset("health_facility__", HealthFacilityGQLType._meta.filter_fields),
            **prefix_filterset("insuree__", InsureeGQLType._meta.filter_fields),
        }
        connection_class = ExtendedConnection

    @classmethod
    def get_queryset(cls, queryset, info):
        queryset = queryset.filter(*filter_validity())
        if settings.ROW_SECURITY & info.context.user.is_anonymous:
            return queryset.filter(id=-1)
        if settings.ROW_SECURITY:
            dist = userDistricts(info.context.user._u)
            return queryset.filter(
                health_facility__location__id__in=[l.location.id for l in dist]
            )
        return queryset


class FeedbackGQLType(DjangoObjectType):
    class Meta:
        model = Feedback
        exclude_fields = ('row_id',)


class ClaimItemGQLType(DjangoObjectType):
    """
    Contains the items within a specific Claim
    """

    class Meta:
        model = ClaimItem
        exclude_fields = ('row_id',)


class ClaimServiceGQLType(DjangoObjectType):
    """
    Contains the services within a specific Claim
    """

    class Meta:
        model = ClaimService
        exclude_fields = ('row_id',)


class Query(graphene.ObjectType):
    claims = OrderedDjangoFilterConnectionField(
        ClaimGQLType, orderBy=graphene.List(of_type=graphene.String))
    claim_admins = DjangoFilterConnectionField(ClaimAdminGQLType)
    claim_officers = DjangoFilterConnectionField(ClaimOfficerGQLType)


class ClaimItemInputType(InputObjectType):
    id = graphene.Int(required=False)
    item_id = graphene.Int(required=True)
    status = TinyInt(required=True)
    qty_provided = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    qty_approved = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    price_asked = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    price_adjusted = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    price_approved = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    price_valuated = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    explanation = graphene.String(required=False)
    justification = graphene.String(required=False)
    rejection_reason = SmallInt(required=False)

    validity_from_review = graphene.DateTime(required=False)
    validity_to_review = graphene.DateTime(required=False)
    limitation_value = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    limitation = graphene.String(required=False)
    # policy_id
    remunerated_amount = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    deductable_amount = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    exceed_ceiling_amount = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    price_origin = graphene.String(required=False)
    exceed_ceiling_amount_category = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)


class ClaimServiceInputType(InputObjectType):
    id = graphene.Int(required=False)
    legacy_id = graphene.Int(required=False)
    service_id = graphene.Int(required=True)
    status = TinyInt(required=True)
    qty_provided = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    qty_approved = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    price_asked = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    price_adjusted = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    price_approved = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    price_valuated = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    explanation = graphene.String(required=False)
    justification = graphene.String(required=False)
    rejection_reason = SmallInt(required=False)
    validity_to = graphene.DateTime(required=False)
    validity_from_review = graphene.DateTime(required=False)
    validity_to_review = graphene.DateTime(required=False)
    audit_user_id_review = graphene.Int(required=False)
    limitation_value = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    limitation = graphene.String(max_length=1, required=False)
    policy_id = graphene.Int(required=False)
    remunerated_amount = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    deductable_amount = graphene.Decimal(max_digits=18, decimal_places=2, required=False,
                                         description="deductable is spelled with a, not deductible")
    exceed_ceiling_amount = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    price_origin = graphene.String(max_length=1, required=False)
    exceed_ceiling_amount_category = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)


class FeedbackInputType(InputObjectType):
    id = graphene.Int(required=False, read_only=True)
    care_rendered = graphene.Boolean(required=False)
    payment_asked = graphene.Boolean(required=False)
    drug_prescribed = graphene.Boolean(required=False)
    drug_received = graphene.Boolean(required=False)
    asessment = SmallInt(
        required=False, description="Be careful, this field name has a typo")
    chf_officer_code = graphene.Int(required=False)
    feedback_date = graphene.DateTime(required=False)
    validity_from = graphene.DateTime(required=False)
    validity_to = graphene.DateTime(required=False)


class ClaimInputType(OpenIMISMutation.Input):
    id = graphene.Int(required=False, read_only=True)
    code = graphene.String(max_length=8, required=True)
    insuree_id = graphene.Int(required=True)
    date_from = graphene.Date(required=True)
    date_to = graphene.Date(required=False)
    icd_id = graphene.Int(required=True)
    icd_1_id = graphene.Int(required=False)
    icd_2_id = graphene.Int(required=False)
    icd_3_id = graphene.Int(required=False)
    icd_4_id = graphene.Int(required=False)
    review_status = TinyInt(required=False)
    status = TinyInt(required=True)
    date_claimed = graphene.Date(required=True)
    date_processed = graphene.Date(required=False)
    health_facility_id = graphene.Int(required=True)
    batch_run_id = graphene.Int(required=False)
    category = graphene.String(max_length=1, required=False)
    visit_type = graphene.String(max_length=1, required=False)
    admin_id = graphene.Int(required=False)

    feedback_available = graphene.Boolean(default=False)
    feedback_status = TinyInt(required=False)
    feedback = graphene.Field(FeedbackInputType, required=False)

    items = graphene.List(ClaimItemInputType, required=False)
    services = graphene.List(ClaimServiceInputType, required=False)


def update_or_create_claim(data):
    items = data.pop('items') if 'items' in data else []
    services = data.pop('services') if 'services' in data else []
    data.pop('client_mutation_id')
    data.pop('client_mutation_label')
    claim_id = data.pop('id') if 'id' in data else None
    try:
        claim, created = Claim.objects.update_or_create(
            id=claim_id,
            defaults=data)
    except Exception as exc:
        raise
    claimed = 0
    prev_items = [s.id for s in claim.items.all()]
    for item in items:
        claimed += item.qty_provided * item.price_asked
        item_id = item.pop('id') if 'id' in item else None
        # TODO: investigate the audit_user_id. For now, it seems to be forced to -1 in most cases
        # item['audit_user_id'] = user.id
        item['audit_user_id'] = -1
        if (item_id):
            prev_items.remove(item_id)
            claim.items.filter(id=item_id).update(**item)
        else:
            from datetime import date
            item['validity_from'] = date.today()
            # TODO: investigate 'availability' is mandatory, but not in UI > always true?
            item['availability'] = True
            ClaimItem.objects.create(claim=claim, **item)
    if prev_items:
        claim.items.filter(id__in=prev_items).delete()

    prev_services = [s.id for s in claim.services.all()]
    for service in services:
        claimed += service.qty_provided * service.price_asked
        service_id = service.pop('id') if 'id' in service else None
        # TODO: investigate the audit_user_id. For now, it seems to be forced to -1 in most cases
        # service['audit_user_id'] = user.id
        service['audit_user_id'] = -1
        if (service_id):
            prev_services.remove(service_id)
            claim.services.filter(id=service_id).update(**service)
        else:
            from datetime import date
            service['validity_from'] = date.today()
            ClaimService.objects.create(claim=claim, **service)
    if prev_services:
        claim.services.filter(id__in=prev_services).delete()

    claim.claimed = claimed
    claim.save()


class CreateClaimMutation(OpenIMISMutation):
    """
    Create a new claim. The claim items and services can all be entered with this call
    """
    _mutation_module = "claim"
    _mutation_class = "CreateClaimMutation"

    class Input(ClaimInputType):
        pass

    @classmethod
    def async_mutate(cls, root, info, **data):
        user = info.context.user
        # TODO move this verification to OIMutation
        if type(user) is AnonymousUser or not user.id:
            raise ValidationError(
                "User needs to be authenticated for this operation")
        # TODO: investigate the audit_user_id. For now, it seems to be forced to -1 in most cases
        # data['audit_user_id'] = user.id
        data['audit_user_id'] = -1
        from core import datetime
        data['validity_from'] = datetime.date.today()
        update_or_create_claim(data)


class UpdateClaimMutation(OpenIMISMutation):
    """
    Update a claim. The claim items and services can all be updated with this call
    """

    class Input(ClaimInputType):
        pass

    @classmethod
    def async_mutate(cls, root, info, **data):
        user = info.context.user
        # TODO move this verification to OIMutation
        if type(user) is AnonymousUser or not user.id:
            raise ValidationError(
                "User needs to be authenticated for this operation")
        # TODO: investigate the audit_user_id. For now, it seems to be forced to -1 in most cases
        # data['audit_user_id'] = user.id
        data['audit_user_id'] = -1
        update_or_create_claim(data)


class SubmitClaimsMutation(OpenIMISMutation):
    """
    Submit one or several claims.
    """

    class Input(OpenIMISMutation.Input):
        ids = graphene.List(graphene.Int)

    @classmethod
    def async_mutate(cls, root, info, **data):
        results = {}
        for claim_id in data["ids"]:
            claim = Claim.objects\
                .filter(pk=claim_id)\
                .prefetch_related("items")\
                .prefetch_related("services")\
                .first()
            if claim is None:
                results[claim_id] = {"error": f"id {claim_id} does not exist"}
                continue
            errors = validate_claim(claim)
            if len(errors) > 0:
                results[claim_id] = {
                    "error": errors[0].message, "error_code": errors[0].code}
            else:
                set_claim_submitted(claim, errors)
                results[claim_id] = {"success": True}

        # For now, the response should only contain errors, not successful updates
        errors = {k: v for k, v in results.items() if "success" not in v}
        if len(errors) > 0:
            return json.dumps(errors)
        else:
            return None


def set_claims_status(ids, field, status):
    affected_rows = Claim.objects.filter(id__in=ids).update(**{field: status})
    if affected_rows != len(ids):
        errors = ['Claims in error:']
        errors.extend(map(
            lambda c: c.code,
            Claim.objects.filter(Q(id__in=ids), ~Q(**{field: 4}))
        ))
        return json.dump(errors)
    return None


class SelectClaimsForFeedbackMutation(OpenIMISMutation):
    """
    Select one or several claims for feedback.
    """

    class Input(OpenIMISMutation.Input):
        ids = graphene.List(graphene.Int)

    @classmethod
    def async_mutate(cls, root, info, **data):
        return set_claims_status(data['ids'], 'feedback_status', 4)


class BypassClaimsFeedbackMutation(OpenIMISMutation):
    """
    Bypass feedback for one or several claims
    """

    class Input(OpenIMISMutation.Input):
        ids = graphene.List(graphene.Int)

    @classmethod
    def async_mutate(cls, root, info, **data):
        return set_claims_status(data['ids'], 'feedback_status', 16)


class SkipClaimsFeedbackMutation(OpenIMISMutation):
    """
    Skip feedback for one or several claims
    Skip indicates that the claim is not selected for feedback
    """

    class Input(OpenIMISMutation.Input):
        ids = graphene.List(graphene.Int)

    @classmethod
    def async_mutate(cls, root, info, **data):
        return set_claims_status(data['ids'], 'feedback_status', 2)


class DeliverClaimFeedbackMutation(OpenIMISMutation):
    """
    Deliver feedback of a claim
    """

    class Input(OpenIMISMutation.Input):
        claim_id = graphene.Int(required=False, read_only=True)
        feedback = graphene.Field(FeedbackInputType, required=True)

    @classmethod
    def async_mutate(cls, root, info, **data):
        claim = Claim.objects.get(id=data['claim_id'])
        feedback = data['feedback']
        from datetime import date
        feedback['validity_from'] = date.today()
        # TODO: investigate the audit_user_id. For now, it seems to be forced to -1 in most cases
        # service['audit_user_id'] = user.id
        feedback['audit_user_id'] = -1
        # The legacy model has a Foreign key on both sides of this one-to-one relationship
        f, created = Feedback.objects.update_or_create(
            claim=claim,
            defaults=feedback
        )
        claim.feedback = f
        claim.feedback_status = 8
        claim.feedback_available = True
        claim.save()
        return None


class SelectClaimsForReviewMutation(OpenIMISMutation):
    """
    Select one or several claims for review.
    """

    class Input(OpenIMISMutation.Input):
        ids = graphene.List(graphene.Int)

    @classmethod
    def async_mutate(cls, root, info, **data):
        return set_claims_status(data['ids'], 'review_status', 4)


class BypassClaimsReviewMutation(OpenIMISMutation):
    """
    Bypass review for one or several claims
    Bypass indicates that review of a previously selected claim won't be delivered
    """

    class Input(OpenIMISMutation.Input):
        ids = graphene.List(graphene.Int)

    @classmethod
    def async_mutate(cls, root, info, **data):
        return set_claims_status(data['ids'], 'review_status', 16)


class SkipClaimsReviewMutation(OpenIMISMutation):
    """
    Skip review for one or several claims
    Skip indicates that the claim is not selected for review
    """

    class Input(OpenIMISMutation.Input):
        ids = graphene.List(graphene.Int)

    @classmethod
    def async_mutate(cls, root, info, **data):
        return set_claims_status(data['ids'], 'review_status', 2)


class DeliverClaimReviewMutation(OpenIMISMutation):
    """
    Deliver review of a claim (items and services)
    """

    class Input(OpenIMISMutation.Input):
        claim_id = graphene.Int(required=False, read_only=True)
        items = graphene.List(ClaimItemInputType, required=False)
        services = graphene.List(ClaimServiceInputType, required=False)

    @classmethod
    def async_mutate(cls, root, info, **data):
        claim = Claim.objects.get(id=data['claim_id'])
        items = data.pop('items') if 'items' in data else []
        all_rejected = True
        for item in items:
            item_id = item.pop('id')
            claim.items.filter(id=item_id).update(**item)
            if item.status == 1:
                all_rejected = False
        services = data.pop('services') if 'services' in data else []
        for service in services:
            service_id = service.pop('id')
            claim.services.filter(id=service_id).update(**service)
            if service.status == 1:
                all_rejected = False
        claim.review_status = 8
        if all_rejected:
            claim.status = 1
        claim.save()
        return None


class ProcessClaimsMutation(OpenIMISMutation):
    """
    Process one or several claims.
    """

    class Input(OpenIMISMutation.Input):
        ids = graphene.List(graphene.Int)

    @classmethod
    def async_mutate(cls, root, info, **data):
        results = {}
        for claim_id in data["ids"]:
            claim = Claim.objects \
                .filter(pk=claim_id) \
                .prefetch_related("items") \
                .prefetch_related("services") \
                .first()
            if claim is None:
                results[claim_id] = {"error": f"id {claim_id} does not exist"}
                continue
            errors = validate_claim(claim)
            if len(errors) == 0:
                errors += validate_assign_prod_to_claimitems(claim)
            if len(errors) > 0:
                results[claim_id] = {
                    "error": errors[0].message, "error_code": errors[0].code}
            else:
                set_claim_processed(claim, errors)
                results[claim_id] = {"success": True}

        # For now, the response should only contain errors, not successful updates
        errors = {k: v for k, v in results.items() if "success" not in v}
        if len(errors) > 0:
            return json.dumps(errors)
        else:
            return None


def set_claim_submitted(claim, errors):
    # we went over the maximum for a category, all items and services in the claim are rejected
    over_category_errors = [
        x for x in errors if x.code in [11, 12, 13, 14, 15, 19]]
    if len(over_category_errors) > 0:
        claim.items.update(status=ClaimItem.STATUS_REJECTED, qty_approved=0,
                           rejection_reason=over_category_errors[0].code)
        claim.services.update(status=ClaimService.STATUS_REJECTED, qty_approved=0,
                              rejection_reason=over_category_errors[0].code)
    else:
        claim.items.exclude(rejection_reason=0)\
            .update(status=ClaimItem.STATUS_REJECTED, qty_approved=0)
        claim.services.exclude(rejection_reason=0)\
            .update(status=ClaimService.STATUS_REJECTED, qty_approved=0)

    rtn_items_passed = claim.items.filter(status=ClaimItem.STATUS_PASSED)\
        .filter(validity_to__isnull=True).count()
    rtn_services_passed = claim.services.filter(status=ClaimService.STATUS_PASSED)\
        .filter(validity_to__isnull=True).count()
    rtn_items_rejected = claim.items.filter(status=ClaimItem.STATUS_REJECTED)\
        .filter(validity_to__isnull=True).count()
    rtn_services_rejected = claim.services.filter(status=ClaimService.STATUS_REJECTED)\
        .filter(validity_to__isnull=True).count()

    if rtn_items_passed > 0 and rtn_services_passed > 0:  # update claim passed
        if rtn_items_rejected > 0 or rtn_services_rejected > 0:
            # Update claim approved value
            app_item_value = claim.items\
                .filter(validity_to__isnull=True)\
                .filter(status=ClaimItem.STATUS_PASSED)\
                .annotate(value=Coalesce("qty_provided", "qty_approved") * Coalesce("price_asked", "price_approved"))\
                .aggregate(Sum("value"))
            app_service_value = claim.services\
                .filter(validity_to__isnull=True)\
                .filter(status=ClaimService.STATUS_PASSED)\
                .annotate(value=Coalesce("qty_provided", "qty_approved") * Coalesce("price_asked", "price_approved"))\
                .aggregate(Sum("value"))
            claim.status = Claim.STATUS_CHECKED
            claim.approved = app_item_value if app_item_value else 0 + \
                app_service_value if app_service_value else 0
            # TODO set the right audit user id
            claim.audit_user_id_submit = -1
            from datetime import datetime
            claim.submit_stamp = datetime.now()
            claim.category = get_claim_category(claim)
            claim.save()
        else:  # no rejections
            claim.status = Claim.STATUS_CHECKED
            # TODO set the right audit user id
            claim.audit_user_id_submit = -1
            from datetime import datetime
            claim.submit_stamp = datetime.now()
            claim.category = get_claim_category(claim)
            claim.save()
    else:  # no item nor service passed, rejecting
        claim.status = Claim.STATUS_REJECTED
        # TODO set the right audit user id
        claim.audit_user_id_submit = -1
        from datetime import datetime
        claim.submit_stamp = datetime.now()
        claim.category = get_claim_category(claim)
        claim.save()


def set_claim_processed(claim, errors):
    rtn_items_passed = claim.items.filter(status=ClaimItem.STATUS_PASSED)\
        .filter(validity_to__isnull=True).count()
    rtn_services_passed = claim.services.filter(status=ClaimService.STATUS_PASSED)\
        .filter(validity_to__isnull=True).count()

    if rtn_items_passed > 0 or rtn_services_passed > 0:  # update claim passed
        claim.status = Claim.STATUS_PROCESSED
        # # TODO set the right audit user id
        claim.audit_user_id_process = -1
        from datetime import datetime
        claim.process_stamp = datetime.now()
        claim.save()


class Mutation(graphene.ObjectType):
    create_claim = CreateClaimMutation.Field()
    update_claim = UpdateClaimMutation.Field()
    submit_claims = SubmitClaimsMutation.Field()
    select_claims_for_feedback = SelectClaimsForFeedbackMutation.Field()
    deliver_claim_feedback = DeliverClaimFeedbackMutation.Field()
    bypass_claims_feedback = BypassClaimsFeedbackMutation.Field()
    skip_claims_feedback = SkipClaimsFeedbackMutation.Field()
    select_claims_for_review = SelectClaimsForReviewMutation.Field()
    deliver_claim_review = DeliverClaimReviewMutation.Field()
    bypass_claims_review = BypassClaimsReviewMutation.Field()
    skip_claims_review = SkipClaimsReviewMutation.Field()
    process_claims = ProcessClaimsMutation.Field()

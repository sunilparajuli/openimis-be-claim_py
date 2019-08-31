import graphene
from core import prefix_filterset, ExtendedConnection, filter_validity
from core.schema import TinyInt, SmallInt, OpenIMISMutation
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from graphene import InputObjectType
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField
from insuree.schema import InsureeGQLType
from location.schema import HealthFacilityGQLType, LocationGQLType
from medical.schema import DiagnosisGQLType
from claim_batch.schema import BatchRunGQLType

from .models import Claim, ClaimDiagnosisCode, ClaimAdmin, ClaimOfficer, Feedback, ClaimItem, ClaimService


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
            **prefix_filterset("batch_run__", BatchRunGQLType._meta.filter_fields)
        }
        connection_class = ExtendedConnection

    @classmethod
    def get_queryset(cls, queryset, info):
        queryset = queryset.filter(*filter_validity())
        if settings.ROW_SECURITY & info.context.user.is_anonymous:
            return queryset.filter(id=-1)
        return queryset


class ClaimDiagnosisCodeGQLType(DjangoObjectType):
    """
    This element should be replaced with a DiagnosisGQLType from the Medical module
    """

    class Meta:
        model = ClaimDiagnosisCode
        exclude_fields = ('row_id',)


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
    claims = DjangoFilterConnectionField(ClaimGQLType)
    claim_admins = DjangoFilterConnectionField(ClaimAdminGQLType)
    claim_officers = DjangoFilterConnectionField(ClaimOfficerGQLType)


class ClaimItemInputType(InputObjectType):
    id = graphene.Int(required=False)
    item_id = graphene.Int(required=True)
    status = TinyInt(required=True)
    qty_provided = graphene.Decimal(
        max_digits=18, decimal_places=2, required=True)
    qty_approved = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    price_asked = graphene.Decimal(
        max_digits=18, decimal_places=2, required=True)
    price_adjusted = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    price_approved = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    price_valuated = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    explanation = graphene.String(required=False)
    justification = graphene.String(required=False)
    rejection_reason = graphene.String(required=False)

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
    qty_provided = graphene.Decimal(max_digits=18, decimal_places=2)
    qty_approved = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    price_asked = graphene.Decimal(max_digits=18, decimal_places=2)
    price_adjusted = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    price_approved = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    price_valuated = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    explanation = graphene.String(required=False)
    justification = graphene.String(required=False)
    rejectionreason = SmallInt(
        required=False, description="rejectionreason is in one word for historical reasons")
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


class CreateClaimMutation(OpenIMISMutation):
    """
    Create a new claim. The claim items and services can all be submitted with this call
    """

    class Input(OpenIMISMutation.Input):
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

        feedback = data.pop('feedback') if 'feedback' in data else []
        items = data.pop('items') if 'items' in data else []
        services = data.pop('services') if 'services' in data else []
        data.pop('client_mutation_id')
        data.pop('client_mutation_label')
        try:
            claim = Claim.objects.create(**data)
        except Exception as exc:
            raise

        for item in items:
            # item['validity_from'] = datetime.date.today()
            from datetime import date
            item['validity_from'] = date.today()
            # TODO: investigate 'availability' is mandatory, but not in UI > alsways true?
            item['availability'] = True
            # TODO: investigate the audit_user_id. For now, it seems to be forced to -1 in most cases
            # item['audit_user_id'] = user.id
            item['audit_user_id'] = -1

            ClaimItem.objects.create(claim=claim, **item)

        for service in services:
            # service['validity_from'] = datetime.date.today()
            from datetime import date
            service['validity_from'] = date.today()
            # TODO: investigate the audit_user_id. For now, it seems to be forced to -1 in most cases
            # service['audit_user_id'] = user.id
            service['audit_user_id'] = -1

            ClaimService.objects.create(claim=claim, **service)

        if feedback:
            from datetime import date
            feedback['validity_from'] = date.today()
            # TODO: investigate the audit_user_id. For now, it seems to be forced to -1 in most cases
            # service['audit_user_id'] = user.id
            feedback['audit_user_id'] = -1
            # The legacy model has a Foreign key on both sides of this one-to-one relationship
            claim.feedback = Feedback.objects.create(claim=claim, **feedback)
            claim.save()

        claim.refresh_from_db()
        return claim


class Mutation(graphene.ObjectType):
    create_claim = CreateClaimMutation.Field()

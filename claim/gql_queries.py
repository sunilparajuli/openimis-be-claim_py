import graphene
from core import prefix_filterset, ExtendedConnection, filter_validity, Q, assert_string_length
from django.conf import settings
from graphene_django import DjangoObjectType
from insuree.schema import InsureeGQLType
from location.schema import HealthFacilityGQLType
from medical.schema import DiagnosisGQLType
from location.schema import userDistricts
from claim_batch.schema import BatchRunGQLType
from .models import Claim, ClaimAdmin, Feedback, ClaimItem, ClaimService, ClaimAttachment, ClaimMutation
from core.models import Officer


class ClaimAdminGQLType(DjangoObjectType):
    """
    Details about a Claim Administrator
    """

    class Meta:
        model = ClaimAdmin
        exclude_fields = ('row_id',)
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            "uuid": ["exact"],
            "code": ["exact", "icontains"],
            "last_name": ["exact", "icontains"],
            "other_names": ["exact", "icontains"],
        }
        connection_class = ExtendedConnection

    @classmethod
    def get_queryset(cls, queryset, info):
        queryset = queryset.filter(*filter_validity())
        return queryset


class ClaimOfficerGQLType(DjangoObjectType):
    """
    Details about a Claim Officer
    """

    class Meta:
        model = Officer
        exclude_fields = ('row_id',)
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            "uuid": ["exact"],
            "code": ["exact", "icontains"],
            "last_name": ["exact", "icontains"],
            "other_names": ["exact", "icontains"],
        }
        connection_class = ExtendedConnection

    @classmethod
    def get_queryset(cls, queryset, info):
        queryset = queryset.filter(*filter_validity())
        return queryset

class ClaimGQLType(DjangoObjectType):
    """
    Main element for a Claim. It can contain items and/or services.
    The filters are possible on BatchRun, Insuree, HealthFacility, Admin and ICD in addition to the Claim fields
    themselves.
    """
    attachments_count = graphene.Int()
    client_mutation_id = graphene.String()

    class Meta:
        model = Claim
        exclude_fields = ('row_id',)
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            "uuid": ["exact"],
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

    def resolve_attachments_count(self, info):
        return self.attachments.filter(validity_to__isnull=True).count()

    def resolve_items(self, info):
        return self.items.filter(validity_to__isnull=True)

    def resolve_services(self, info):
        return self.services.filter(validity_to__isnull=True)

    def resolve_client_mutation_id(self, info):
        claim_mutation = self.mutations.select_related(
            'mutation').filter(mutation__status=0).first()
        return claim_mutation.mutation.client_mutation_id if claim_mutation else None

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


class ClaimAttachmentGQLType(DjangoObjectType):
    doc = graphene.String()

    class Meta:
        model = ClaimAttachment
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            "id": ["exact"],
            "type": ["exact", "icontains"],
            "title": ["exact", "icontains"],
            "date": ["exact", "lt", "lte", "gt", "gte"],
            "filename": ["exact", "icontains"],
            "mime": ["exact", "icontains"],
            "url": ["exact", "icontains"],
            **prefix_filterset("claim__", ClaimGQLType._meta.filter_fields),
        }
        connection_class = ExtendedConnection

    @classmethod
    def get_queryset(cls, queryset, info):
        queryset = queryset.filter(*filter_validity())
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

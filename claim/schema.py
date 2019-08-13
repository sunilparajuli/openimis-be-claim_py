from django.conf import settings
import graphene
from core import prefix_filterset, ExtendedConnection
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField
from insuree.schema import InsureeGQLType
from location.schema import HealthFacilityGQLType, LocationGQLType
from medical.schema import DiagnosisGQLType

from .models import BatchRun, Claim, ClaimDiagnosisCode, ClaimAdmin, Feedback, ClaimItem, ClaimService


class BatchRunGQLType(DjangoObjectType):
    class Meta:
        model = BatchRun
        exclude_fields = ('row_id',)
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            "id": ["exact"],
            "run_date": ["exact", "lt", "lte", "gt", "gte"],
            **prefix_filterset("location__", LocationGQLType._meta.filter_fields),
        }
        connection_class = ExtendedConnection


class ClaimAdminGQLType(DjangoObjectType):
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


class ClaimGQLType(DjangoObjectType):

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
        if settings.ROW_SECURITY & info.context.user.is_anonymous:
            return queryset.filter(id=-1)
        return queryset

    # extra_field = graphene.String()
    # def resolve_extra_field(self, info):
    #     return 'sample extra!'


class ClaimDiagnosisCodeGQLType(DjangoObjectType):
    class Meta:
        model = ClaimDiagnosisCode
        exclude_fields = ('row_id',)


class FeedbackGQLType(DjangoObjectType):
    class Meta:
        model = Feedback
        exclude_fields = ('row_id',)


class ClaimItemGQLType(DjangoObjectType):
    class Meta:
        model = ClaimItem
        exclude_fields = ('row_id',)


class ClaimServiceGQLType(DjangoObjectType):
    class Meta:
        model = ClaimService
        exclude_fields = ('row_id',)


class Query(graphene.ObjectType):
    claims = DjangoFilterConnectionField(ClaimGQLType)
    claim_admins = DjangoFilterConnectionField(ClaimAdminGQLType)
    batch_runs = DjangoFilterConnectionField(BatchRunGQLType)

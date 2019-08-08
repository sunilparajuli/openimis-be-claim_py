import graphene
from core import prefix_filterset
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField
from insuree.schema import InsureeGQLType

from .models import Claim, ClaimDiagnosisCode, ClaimAdmin, Feedback, ClaimItem, ClaimService


class ClaimGQLType(DjangoObjectType):

    class Meta:
        model = Claim
        exclude_fields = ('row_id',)
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            "id": ["exact"],
            "status": ["exact"],
            **prefix_filterset("insuree__", InsureeGQLType._meta.filter_fields)
        }

    @classmethod
    def get_queryset(cls, queryset, info):
        if info.context.user.is_anonymous:
            return queryset.filter(id=1)
        return queryset

    # extra_field = graphene.String()
    # def resolve_extra_field(self, info):
    #     return 'sample extra!'


class ClaimAdminGQLType(DjangoObjectType):
    class Meta:
        model = ClaimAdmin
        exclude_fields = ('row_id',)


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
    claim = graphene.relay.node.Field(ClaimGQLType,
                                      id=graphene.Int(),
                                      name=graphene.String())
    all_claims = DjangoFilterConnectionField(ClaimGQLType)

    def resolve_all_claims(self, info, **kwargs):
        if info.context.user.is_authenticated:
            if info.context.user:
                return Claim.objects.filter(id__gte=0)  # TODO find how to filter
            else:
                return Claim.objects.all()
        else:
            return Claim.objects.all()

    def resolve_claim(self, info, **kwargs):
        id = kwargs.get('id')
        name = kwargs.get('name')

        if id is not None:
            return Claim.objects.get(pk=id)

        if name is not None:
            return Claim.objects.get(name=name)

        return Claim.objects.none()

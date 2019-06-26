import graphene
from graphene_django import DjangoObjectType

from .models import Claim, ClaimDiagnosisCode, ClaimAdmin, Feedback, ClaimItem, ClaimService


class ClaimType(DjangoObjectType):
    class Meta:
        model = Claim
        exclude_fields = ('row_id',)

    @classmethod
    def get_queryset(cls, queryset, info):
        if info.context.user.is_anonymous:
            return queryset.filter(id=1)
        return queryset

    # extra_field = graphene.String()
    # def resolve_extra_field(self, info):
    #     return 'sample extra!'


class ClaimAdminType(DjangoObjectType):
    class Meta:
        model = ClaimAdmin
        exclude_fields = ('row_id',)


class ClaimDiagnosisCodeType(DjangoObjectType):
    class Meta:
        model = ClaimDiagnosisCode
        exclude_fields = ('row_id',)


class FeedbackType(DjangoObjectType):
    class Meta:
        model = Feedback
        exclude_fields = ('row_id',)


class ClaimItemType(DjangoObjectType):
    class Meta:
        model = ClaimItem
        exclude_fields = ('row_id',)


class ClaimServiceType(DjangoObjectType):
    class Meta:
        model = ClaimService
        exclude_fields = ('row_id',)


class Query(graphene.ObjectType):
    claim = graphene.Field(ClaimType,
                           id=graphene.Int(),
                           name=graphene.String())
    all_claims = graphene.List(ClaimType)

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

from core.schema import signal_mutation_module_validate
import graphene
import graphene_django_optimizer as gql_optimizer
from core.schema import TinyInt, SmallInt, OpenIMISMutation, OrderedDjangoFilterConnectionField
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils.translation import gettext as _
from graphene_django.filter import DjangoFilterConnectionField

from .gql_queries import *
from .gql_mutations import *


class Query(graphene.ObjectType):
    claims = OrderedDjangoFilterConnectionField(
        ClaimGQLType,
        codeIsNot=graphene.String(),
        orderBy=graphene.List(of_type=graphene.String))
    claim_attachments = DjangoFilterConnectionField(ClaimAttachmentGQLType)
    claim_admins = DjangoFilterConnectionField(ClaimAdminGQLType)
    claim_officers = DjangoFilterConnectionField(ClaimOfficerGQLType)

    def resolve_claims(self, info, **kwargs):
        if not info.context.user.has_perms(ClaimConfig.gql_query_claims_perms):
            raise PermissionDenied(_("unauthorized"))
        query = Claim.objects
        code_is_not = kwargs.get('codeIsNot', None)
        if code_is_not:
            query = query.exclude(code=code_is_not)
        return gql_optimizer.query(query.all(), info)

    def resolve_claim_attachments(self, info, **kwargs):
        if not info.context.user.has_perms(ClaimConfig.gql_query_claims_perms):
            raise PermissionDenied(_("unauthorized"))
        pass

    def resolve_claim_admins(self, info, **kwargs):
        if not info.context.user.has_perms(ClaimConfig.gql_query_claim_admins_perms):
            raise PermissionDenied(_("unauthorized"))
        pass

    def resolve_claim_officers(self, info, **kwargs):
        if not info.context.user.has_perms(ClaimConfig.gql_query_claim_officers_perms):
            raise PermissionDenied(_("unauthorized"))
        pass


class Mutation(graphene.ObjectType):
    create_claim = CreateClaimMutation.Field()
    update_claim = UpdateClaimMutation.Field()
    create_claim_attachment = CreateClaimAttachmentMutation.Field()
    delete_claim_attachment = DeleteClaimAttachmentMutation.Field()
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
    delete_claims = DeleteClaimsMutation.Field()


def on_claim_mutation(sender, **kwargs):
    uuids = kwargs['data'].get('uuids', [])
    if not uuids:
        uuid = kwargs['data'].get('claim_uuid', None)
        uuids = [uuid] if uuid else []
    if not uuids:
        return []
    impacted_claims = Claim.objects.filter(uuid__in=uuids).all()
    for claim in impacted_claims:
        ClaimMutation.objects.create(
            claim=claim, mutation_id=kwargs['mutation_log_id'])
    return []


def bind_signals():
    signal_mutation_module_validate["claim"].connect(on_claim_mutation)

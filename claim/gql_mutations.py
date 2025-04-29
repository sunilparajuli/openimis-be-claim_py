import logging
import os
import urllib.parse
from uuid import uuid4, UUID
import pathlib
import base64
from urllib.parse import urlparse
from typing import Callable, Dict

import graphene
import importlib
import graphene_django_optimizer
from django.db.models import Count, Case, When, IntegerField, Q, Prefetch

from core.models import MutationLog, Officer
from .apps import ClaimConfig
from claim.validations import validate_claim, get_claim_category, validate_assign_prod_to_claimitems_and_services, \
    process_dedrem, approved_amount
from core import filter_validity, assert_string_length
from core.schema import TinyInt, SmallInt, OpenIMISMutation
from core.gql.gql_mutations import mutation_on_uuids_from_filter
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError, PermissionDenied, ObjectDoesNotExist
from django.utils.translation import gettext as _
from graphene import InputObjectType
from claim.gql_queries import ClaimGQLType
from claim.models import Claim, Feedback, FeedbackPrompt, ClaimDetail, ClaimItem, ClaimService, ClaimAttachment, \
    ClaimDedRem, GeneralClaimAttachmentType, ClaimAttachmentType, ClaimServiceService
from claim.attachment_strategies import *

from product.models import ProductItemOrService
from medical.models import Item, Service

from claim.utils import process_items_relations, process_services_relations
from claim.services import validate_claim_data as service_validate_claim_data, \
        update_or_create_claim as service_update_or_create_claim, check_unique_claim_code, ClaimSubmitService,\
            processing_claim as service_processing_claim,\
            create_feedback_prompt as service_create_feedback_prompt, update_claims_dedrems,\
                set_feedback_prompt_validity_to_to_current_date, set_claims_status
from claim.validations import REJECTION_REASON_INVALID_CLAIM
from django.db import transaction
import requests

logger = logging.getLogger(__name__)


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
    remunerated_amount = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    deductable_amount = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    exceed_ceiling_amount = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    price_origin = graphene.String(required=False)
    exceed_ceiling_amount_category = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)


class ClaimSubServiceInputType(InputObjectType):
    id = graphene.Int(required=False)
    sub_service_code = graphene.String(required=True)
    qty_provided = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    qty_asked = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    price_asked = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)


class ClaimSubItemInputType(InputObjectType):
    id = graphene.Int(required=False)
    sub_item_code = graphene.String(required=True)
    qty_provided = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    qty_asked = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    price_asked = graphene.Decimal(
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
    deductable_amount = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False,
        description="deductable is spelled with a, not deductible")
    exceed_ceiling_amount = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    price_origin = graphene.String(max_length=1, required=False)
    exceed_ceiling_amount_category = graphene.Decimal(
        max_digits=18, decimal_places=2, required=False)
    service_item_set = graphene.List(ClaimSubItemInputType, required=False)
    service_service_set = graphene.List(
        ClaimSubServiceInputType, required=False)


class FeedbackInputType(InputObjectType):
    id = graphene.Int(required=False, read_only=True)
    care_rendered = graphene.Boolean(required=False)
    payment_asked = graphene.Boolean(required=False)
    drug_prescribed = graphene.Boolean(required=False)
    drug_received = graphene.Boolean(required=False)
    asessment = SmallInt(
        required=False,
        description="Be careful, this field name has a typo")
    officer_id = graphene.Int(required=False)
    feedback_date = graphene.DateTime(required=False)
    validity_from = graphene.DateTime(required=False)
    validity_to = graphene.DateTime(required=False)


class ClaimCodeInputType(graphene.String):

    @staticmethod
    def coerce_string(value):
        assert_string_length(value, ClaimConfig.max_claim_length)
        return value

    serialize = coerce_string
    parse_value = coerce_string

    @staticmethod
    def parse_literal(ast):
        result = graphene.String.parse_literal(ast)
        assert_string_length(result, ClaimConfig.max_claim_length)
        return result


class ClaimGuaranteeIdInputType(graphene.String):

    @staticmethod
    def coerce_string(value):
        assert_string_length(value, 50)
        return value

    serialize = coerce_string
    parse_value = coerce_string

    @staticmethod
    def parse_literal(ast):
        result = graphene.String.parse_literal(ast)
        assert_string_length(result, 50)
        return result


class BaseAttachment:
    id = graphene.String(required=False, read_only=True)
    type = graphene.String(required=False)
    title = graphene.String(required=False)
    date = graphene.Date(required=False)
    filename = graphene.String(required=False)
    mime = graphene.String(required=False)
    general_type = graphene.String(required=False)
    predefined_type = graphene.String(required=False)
    url = graphene.String(required=False)


class BaseAttachmentInputType(BaseAttachment, OpenIMISMutation.Input):
    """
    Claim attachment (without the document), used on its own
    """
    claim_uuid = graphene.String(required=True)


class Attachment(BaseAttachment):
    document = graphene.String(required=False)


class ClaimAttachmentInputType(Attachment, InputObjectType):
    """
    Claim attachment, used nested in claim object
    """
    pass


class AttachmentInputType(Attachment, OpenIMISMutation.Input):
    """
    Claim attachment, used on its own
    """
    claim_uuid = graphene.String(required=True)


class ClaimInputType(OpenIMISMutation.Input):
    id = graphene.Int(required=False, read_only=True)
    uuid = graphene.String(required=False)
    code = ClaimCodeInputType(required=True)
    autogenerate = graphene.Boolean(required=False)
    insuree_id = graphene.Int(required=True)
    date_from = graphene.Date(required=True)
    date_to = graphene.Date(required=False)
    icd_id = graphene.Int(required=True)
    icd_1_id = graphene.Int(required=False)
    icd_2_id = graphene.Int(required=False)
    icd_3_id = graphene.Int(required=False)
    icd_4_id = graphene.Int(required=False)
    review_status = TinyInt(required=False)
    date_claimed = graphene.Date(required=True)
    date_processed = graphene.Date(required=False)
    health_facility_id = graphene.Int(required=True)
    refer_from_id = graphene.Int(required=False)
    refer_to_id = graphene.Int(required=False)
    batch_run_id = graphene.Int(required=False)
    category = graphene.String(max_length=1, required=False)
    visit_type = graphene.String(max_length=1, required=False)
    admin_id = graphene.Int(required=False)
    guarantee_id = ClaimGuaranteeIdInputType(required=False)
    explanation = graphene.String(required=False)
    adjustment = graphene.String(required=False)
    json_ext = graphene.types.json.JSONString(required=False)
    restore = graphene.UUID(required=False)
    feedback_available = graphene.Boolean(default=False)
    feedback_status = TinyInt(required=False)
    feedback = graphene.Field(FeedbackInputType, required=False)
    care_type = graphene.String(required=False)
    pre_authorization = graphene.Boolean(required=False)
    patient_condition = graphene.String(required=False)
    referral_code = graphene.String(required=False)

    items = graphene.List(ClaimItemInputType, required=False)
    services = graphene.List(ClaimServiceInputType, required=False)


class CreateClaimInputType(ClaimInputType):
    attachments = graphene.List(ClaimAttachmentInputType, required=False)


def create_file(date, claim_id, document):
    date_iso = date.isoformat()
    root = ClaimConfig.claim_attachments_root_path
    file_dir = '%s/%s/%s/%s' % (
        date_iso[0:4],
        date_iso[5:7],
        date_iso[8:10],
        claim_id
    )
    file_path = '%s/%s' % (file_dir, uuid4())
    pathlib.Path('%s/%s' % (root, file_dir)).mkdir(parents=True, exist_ok=True)
    f = open('%s/%s' % (root, file_path), "xb")
    f.write(base64.b64decode(document))
    f.close()
    return file_path


def create_attachment(claim_id, data):
    data["claim_id"] = claim_id
    from core import datetime
    now = datetime.datetime.now()
    general_type = data['general_type']
    data['module'] = 'claim'
    if general_type == GeneralClaimAttachmentType.URL:
        parsed_url = urlparse(data['url'])
        if (ClaimConfig.allowed_domains_attachments and
                not any(domain in parsed_url.path for domain in ClaimConfig.allowed_domains_attachments)):
            raise ValidationError(
                _("mutation.attachment_url_domain_not_allowed"))
        if data['predefined_type'] in attachment_strategies_dict:
            data['url'] = attachment_strategies_dict[data['predefined_type']].handler(
                data)
            data['document'] = data['url']
        data['predefined_type'] = ClaimAttachmentType.objects.get(validity_to__isnull=True, claim_general_type="URL",
                                                                  claim_attachment_type=data['predefined_type'])
    elif general_type == GeneralClaimAttachmentType.FILE:
        if ClaimConfig.claim_attachments_root_path:
            # don't use data date as it may be updated by user afterwards!
            data['url'] = create_file(now, claim_id, data.pop('document'))
        data['predefined_type'] = ClaimAttachmentType.objects.get(validity_to__isnull=True, claim_general_type="FILE",
                                                                  claim_attachment_type=data['predefined_type'])
    else:
        raise ValidationError(_("mutation.attachment_general_type_incorrect"))
    data['validity_from'] = now
    ClaimAttachment.objects.create(**data)


def create_attachments(claim_id, attachments):
    for attachment in attachments:
        create_attachment(claim_id, attachment)


def validate_claim_data(data, user):
    return service_validate_claim_data(data, user)


@transaction.atomic
def update_or_create_claim(data, user):
    if "client_mutation_id" in data:
        data.pop('client_mutation_id')
    if "client_mutation_label" in data:
        data.pop('client_mutation_label')
    return service_update_or_create_claim(data, user)


class CreateClaimMutation(OpenIMISMutation):
    """
    Create a new claim. The claim items and services can all be entered with this call
    """
    _mutation_module = "claim"
    _mutation_class = "CreateClaimMutation"

    class Input(CreateClaimInputType):
        pass

    @classmethod
    def async_mutate(cls, user, **data):
        try:
            # TODO move this verification to OIMutation
            if type(user) is AnonymousUser or not user.id:
                raise ValidationError(
                    _("mutation.authentication_required"))
            if not user.has_perms(ClaimConfig.gql_mutation_create_claims_perms):
                raise PermissionDenied(_("unauthorized"))
            is_claim_code_autogenerated = data.get("autogenerate", False)
            data['status'] = Claim.STATUS_ENTERED
            from core.utils import TimeUtils
            data['validity_from'] = TimeUtils.now()
            attachments = data.pop(
                'attachments') if 'attachments' in data else None
            claim = update_or_create_claim(data, user)
            if attachments:
                create_attachments(claim.id, attachments)
            if is_claim_code_autogenerated:
                return {"client_mutation_label": f"Create Claim - {claim.code}", "code": f"{claim.code}"}
            return None
        except Exception as exc:
            return [{
                'message': _("claim.mutation.failed_to_create_claim") % {'code': data['code']},
                'detail': str(exc)}]


class UpdateClaimMutation(OpenIMISMutation):
    """
    Update a claim. The claim items and services can all be updated with this call
    """
    _mutation_module = "claim"
    _mutation_class = "UpdateClaimMutation"

    class Input(ClaimInputType):
        pass

    @classmethod
    def async_mutate(cls, user, **data):
        try:
            # TODO move this verification to OIMutation
            if type(user) is AnonymousUser or not user.id:
                raise ValidationError(
                    _("mutation.authentication_required"))
            if not user.has_perms(ClaimConfig.gql_mutation_update_claims_perms):
                raise PermissionDenied(_("unauthorized"))
            data['audit_user_id'] = user.id_for_audit
            update_or_create_claim(data, user)
            return None
        except Exception as exc:
            return [{
                'message': _("claim.mutation.failed_to_update_claim") % {'code': data['code']},
                'detail': str(exc)}]


class CreateAttachmentMutation(OpenIMISMutation):
    _mutation_module = "claim"
    _mutation_class = "AddClaimAttachmentMutation"

    class Input(AttachmentInputType):
        pass

    @classmethod
    def async_mutate(cls, user, **data):
        claim = None
        try:
            if user.is_anonymous or not user.has_perms(ClaimConfig.gql_mutation_update_claims_perms):
                raise PermissionDenied(_("unauthorized"))
            if "client_mutation_id" in data:
                data.pop('client_mutation_id')
            if "client_mutation_label" in data:
                data.pop('client_mutation_label')
            claim_uuid = data.pop("claim_uuid")
            queryset = Claim.objects.filter(*filter_validity())
            if settings.ROW_SECURITY:
                from location.schema import LocationManager
                queryset = LocationManager().build_user_location_filter_query(
                    user._u, prefix='health_facility__location', queryset=queryset, loc_types=['D'])
            claim = queryset.filter(uuid=claim_uuid).first()
            if not claim:
                raise PermissionDenied(_("unauthorized"))
            create_attachment(claim.id, data)
            return None
        except Exception as exc:
            return [{
                'message': _("claim.mutation.failed_to_attach_document") % {'code': claim.code if claim else None},
                'detail': str(exc)}]


class UpdateAttachmentMutation(OpenIMISMutation):
    _mutation_module = "claim"
    _mutation_class = "UpdateAttachmentMutation"

    class Input(BaseAttachmentInputType):
        pass

    @classmethod
    def async_mutate(cls, user, **data):
        try:
            if not user.has_perms(ClaimConfig.gql_mutation_update_claims_perms):
                raise PermissionDenied(_("unauthorized"))
            queryset = ClaimAttachment.objects.filter(*filter_validity())
            if settings.ROW_SECURITY:
                from location.schema import LocationManager
                queryset = LocationManager().build_user_location_filter_query(user._u,
                                                                              prefix='claim__health_facility__location', queryset=queryset.select_related("claim"), loc_types=['D'])

            attachment = queryset \
                .filter(id=data['id']) \
                .first()
            if not attachment:
                raise PermissionDenied(_("unauthorized"))
            general_type = data['general_type']
            data['module'] = 'claim'
            from core import datetime
            now = datetime.datetime.now()
            if general_type == GeneralClaimAttachmentType.URL:
                parsed_url = urlparse(data['url'])
                if (ClaimConfig.allowed_domains_attachments and
                        not any(domain in parsed_url.path for domain in ClaimConfig.allowed_domains_attachments)):
                    raise ValidationError(
                        _("mutation.attachment_url_domain_not_allowed"))
                if data['predefined_type'] in attachment_strategies_dict:
                    data['url'] = attachment_strategies_dict[data['predefined_type']].handler(
                        data)
                    data['document'] = data['url']
                data['predefined_type'] = ClaimAttachmentType.objects.get(validity_to__isnull=True,
                                                                          claim_general_type="URL",
                                                                          claim_attachment_type=data['predefined_type'])
            elif general_type == GeneralClaimAttachmentType.FILE:
                if ClaimConfig.claim_attachments_root_path:
                    # don't use data date as it may be updated by user afterwards!
                    data['url'] = create_file(
                        now, claim_id, data.pop('document'))
                data['predefined_type'] = ClaimAttachmentType.objects.get(validity_to__isnull=True,
                                                                          claim_general_type="FILE",
                                                                          claim_attachment_type=data['predefined_type'])
            attachment.save_history()
            data['audit_user_id'] = user.id_for_audit
            [setattr(attachment, key, data[key]) for key in data]
            attachment.save()
            return None
        except Exception as exc:
            return [{
                'message': _("claim.mutation.failed_to_update_claim_attachment") % {
                    'code': attachment.claim.code,
                    'filename': attachment.filename
                },
                'detail': str(exc)}]


class DeleteAttachmentMutation(OpenIMISMutation):
    _mutation_module = "claim"
    _mutation_class = "DeleteClaimAttachmentMutation"

    class Input(OpenIMISMutation.Input):
        id = graphene.String()

    @classmethod
    def async_mutate(cls, user, **data):
        try:
            if not user.has_perms(ClaimConfig.gql_mutation_update_claims_perms):
                raise PermissionDenied(_("unauthorized"))
            queryset = ClaimAttachment.objects.filter(*filter_validity())
            if settings.ROW_SECURITY:
                from location.schema import LocationManager
                queryset = LocationManager().build_user_location_filter_query(
                    user._u, prefix='health_facility__location', queryset=queryset, loc_types=['D'])
            attachment = queryset \
                .filter(id=data['id']) \
                .first()
            if not attachment:
                raise PermissionDenied(_("unauthorized"))
            attachment.delete_history()
            return None
        except Exception as exc:
            return [{
                'message': _("claim.mutation.failed_to_delete_claim_attachment") % {
                    'code': attachment.claim.code,
                    'filename': attachment.filename
                },
                'detail': str(exc)}]


class ClaimSubmissionStatsMixin:
    @classmethod
    def _generate_claim_submission_stats(cls, uuids):
        claims_query = Claim.objects.filter(uuid__in=list(uuids))
        claim_item_query = ClaimItem.objects.filter(claim__in=claims_query)
        claim_service_query = ClaimService.objects.filter(
            claim__in=claims_query)
        claim_stats = claims_query.aggregate(
            submitted=Count('uuid', output_field=IntegerField()),
            checked=Count(Case(When(status=4, then=1),
                          output_field=IntegerField())),
            processed=Count(Case(When(status=8, then=1),
                            output_field=IntegerField())),
            valuated=Count(Case(When(status=16, then=1),
                           output_field=IntegerField())),
            rejected=Count(Case(When(status=1, then=1),
                           output_field=IntegerField())),
        )
        item_stats = claim_item_query.aggregate(
            items_passed=Count(Case(When(status=1, then=1),
                               output_field=IntegerField())),
            items_rejected=Count(
                Case(When(status=2, then=1), output_field=IntegerField())),
        )
        service_stats = claim_service_query.aggregate(
            services_passed=Count(
                Case(When(status=1, then=1), output_field=IntegerField())),
            services_rejected=Count(
                Case(When(status=2, then=1), output_field=IntegerField())),
        )

        return {**claim_stats, **item_stats, **service_stats}

    @classmethod
    def _parse_submission_stats(cls, claim_submission_stats):
        return claim_submission_stats

    @classmethod
    def add_submission_stats_to_mutation_log(cls, client_mutation_id, uuids):
        mutation_log = MutationLog.objects.filter(
            client_mutation_id=client_mutation_id).first()
        claim_submission_stats = cls._generate_claim_submission_stats(uuids)
        parsed_stats = cls._parse_submission_stats(claim_submission_stats)
        if isinstance(mutation_log.json_ext, dict):
            mutation_log.json_ext["claim_stats"] = parsed_stats
        else:
            mutation_log.json_ext = {"claim_stats": parsed_stats}
        mutation_log.save()


class SubmitClaimsMutation(OpenIMISMutation, ClaimSubmissionStatsMixin):
    """
    Submit one or several claims.
    """
    __filter_handlers = {
        'services': 'services__service__code__in',
        'items': 'items__item__code__in'
    }
    _mutation_module = "claim"
    _mutation_class = "SubmitClaimsMutation"

    class Input(OpenIMISMutation.Input):
        uuids = graphene.List(graphene.String)
        additional_filters = graphene.String()

    @classmethod
    def _parse_submission_stats(cls, claim_submission_stats):
        return {
            "submitted": claim_submission_stats["submitted"],
            "checked": claim_submission_stats["checked"],
            "rejected": claim_submission_stats["rejected"],
            "items_passed": claim_submission_stats["items_passed"],
            "items_rejected": claim_submission_stats["items_rejected"],
            "services_passed": claim_submission_stats["services_passed"],
            "services_rejected": claim_submission_stats["services_rejected"],
            "header": "Claims submitted",
            # failed
        }

    @classmethod
    @mutation_on_uuids_from_filter(Claim, ClaimGQLType, 'additional_filters', __filter_handlers)
    def async_mutate(cls, user, **data):
        if not user.has_perms(ClaimConfig.gql_mutation_submit_claims_perms):
            raise PermissionDenied(_("unauthorized"))
        errors = []
        uuids = data.get("uuids", [])
        client_mutation_id = data.get("client_mutation_id", None)
        service = ClaimSubmitService(user)
        c_errors = []

        claims = Claim.objects.filter(uuid__in=uuids,
            validity_to__isnull=True) \
            .prefetch_related(Prefetch('items', queryset=ClaimItem.objects.filter(
                *filter_validity(),
                Q(Q(rejection_reason=0) | Q(rejection_reason__isnull=True))))) \
            .prefetch_related(Prefetch('services', queryset=ClaimService.objects.filter(
                *filter_validity(),
                Q(Q(rejection_reason=0) | Q(rejection_reason__isnull=True)))))
        remaining_uuid = list(map(str.upper, uuids))

        for claim in claims:
            remaining_uuid.remove(claim.uuid.upper())
            subm_claim, error = service.submit_claim(claim, user)
            if error:
                c_errors += error
            if c_errors:
                errors.append({
                    'title': claim.code,
                    'list': c_errors
                })
        if len(remaining_uuid):
            c_errors.append({'code': REJECTION_REASON_INVALID_CLAIM,
                             'message': _("claim.validation.claim_uuid_not_found") + ','.join(remaining_uuid)})
        if len(errors) == 1:
            errors = errors[0]['list']
        cls.add_submission_stats_to_mutation_log(client_mutation_id, uuids)
        logger.debug(
            "SubmitClaimsMutation: claim done, errors: %s", len(errors))
        return errors


def create_feedback_prompt(claim_uuid, user):
    current_claim = Claim.objects.get(uuid=claim_uuid)
    return service_create_feedback_prompt(current_claim, user)


class SelectClaimsForFeedbackMutation(OpenIMISMutation):
    """
    Select one or several claims for feedback.
    """
    _mutation_module = "claim"
    _mutation_class = "SelectClaimsForFeedbackMutation"

    class Input(OpenIMISMutation.Input):
        uuids = graphene.List(graphene.String)

    @classmethod
    def async_mutate(cls, user, **data):
        if not user.has_perms(ClaimConfig.gql_mutation_select_claim_feedback_perms):
            raise PermissionDenied(_("unauthorized"))
        return set_claims_status(data['uuids'], 'feedback_status', Claim.FEEDBACK_SELECTED, user=user)


class BypassClaimsFeedbackMutation(OpenIMISMutation):
    """
    Bypass feedback for one or several claims
    """
    _mutation_module = "claim"
    _mutation_class = "BypassClaimsFeedbackMutation"

    class Input(OpenIMISMutation.Input):
        uuids = graphene.List(graphene.String)

    @classmethod
    def async_mutate(cls, user, **data):
        if not user.has_perms(ClaimConfig.gql_mutation_bypass_claim_feedback_perms):
            raise PermissionDenied(_("unauthorized"))
        return set_claims_status(data['uuids'], 'feedback_status', Claim.FEEDBACK_BYPASSED)


class SkipClaimsFeedbackMutation(OpenIMISMutation):
    """
    Skip feedback for one or several claims
    Skip indicates that the claim is not selected for feedback
    """
    _mutation_module = "claim"
    _mutation_class = "SkipClaimsFeedbackMutation"

    class Input(OpenIMISMutation.Input):
        uuids = graphene.List(graphene.String)

    @classmethod
    def async_mutate(cls, user, **data):
        if not user.has_perms(ClaimConfig.gql_mutation_skip_claim_feedback_perms):
            raise PermissionDenied(_("unauthorized"))
        return set_claims_status(data['uuids'], 'feedback_status', Claim.FEEDBACK_NOT_SELECTED)


class DeliverClaimFeedbackMutation(OpenIMISMutation):
    """
    Deliver feedback of a claim
    """
    _mutation_module = "claim"
    _mutation_class = "DeliverClaimFeedbackMutation"

    class Input(OpenIMISMutation.Input):
        claim_uuid = graphene.String(required=False, read_only=True)
        feedback = graphene.Field(FeedbackInputType, required=True)

    @classmethod
    def async_mutate(cls, user, **data):
        claim = None
        try:
            if not user.has_perms(ClaimConfig.gql_mutation_deliver_claim_feedback_perms):
                raise PermissionDenied(_("unauthorized"))
            claim = Claim.objects.select_related('feedback').get(
                uuid=data['claim_uuid'],
                validity_to__isnull=True)
            prev_feedback = claim.feedback
            prev_claim_id = claim.save_history()
            if prev_feedback:
                prev_feedback.claim_id = prev_claim_id
                prev_feedback.save()
            feedback = data['feedback']
            from core.utils import TimeUtils
            feedback['validity_from'] = TimeUtils.now()
            feedback['audit_user_id'] = user.id_for_audit
            # The legacy model has a Foreign key on both sides of this one-to-one relationship
            f, created = Feedback.objects.update_or_create(
                claim=claim,
                defaults=feedback
            )
            claim.feedback = f
            claim.feedback_status = Claim.FEEDBACK_DELIVERED
            claim.feedback_available = True
            claim.save()
            set_feedback_prompt_validity_to_to_current_date(claim.uuid)
            return None
        except Exception as exc:
            return [{
                'message': _("claim.mutation.failed_to_update_claim") % {'code': claim.code if claim else None},
                'detail': str(exc)}]


class SelectClaimsForReviewMutation(OpenIMISMutation):
    """
    Select one or several claims for review.
    """
    _mutation_module = "claim"
    _mutation_class = "SelectClaimsForReviewMutation"

    class Input(OpenIMISMutation.Input):
        uuids = graphene.List(graphene.String)

    @classmethod
    def async_mutate(cls, user, **data):
        if not user.has_perms(ClaimConfig.gql_mutation_select_claim_review_perms):
            raise PermissionDenied(_("unauthorized"))
        return set_claims_status(data['uuids'], 'review_status', Claim.REVIEW_SELECTED)


class BypassClaimsReviewMutation(OpenIMISMutation):
    """
    Bypass review for one or several claims
    Bypass indicates that review of a previously selected claim won't be delivered
    """
    _mutation_module = "claim"
    _mutation_class = "BypassClaimsReviewMutation"

    class Input(OpenIMISMutation.Input):
        uuids = graphene.List(graphene.String)

    @classmethod
    def async_mutate(cls, user, **data):
        if not user.has_perms(ClaimConfig.gql_mutation_bypass_claim_review_perms):
            raise PermissionDenied(_("unauthorized"))
        return set_claims_status(data['uuids'], 'review_status', Claim.REVIEW_BYPASSED)


class DeliverClaimsReviewMutation(OpenIMISMutation):
    """
    Mark claim review as delivered for one or several claims
    """
    _mutation_module = "claim"
    _mutation_class = "DeliverClaimsReviewMutation"

    class Input(OpenIMISMutation.Input):
        uuids = graphene.List(graphene.String)

    @classmethod
    def async_mutate(cls, user, **data):
        logger.error("SaveClaimReviewMutation")
        if not user.has_perms(ClaimConfig.gql_mutation_deliver_claim_review_perms):
            raise PermissionDenied(_("unauthorized"))
        errors = set_claims_status(data['uuids'], 'review_status', Claim.REVIEW_DELIVERED,
                                   {'audit_user_id_review': user.id_for_audit})
        # OMT-208 update the dedrem for the reviewed claims
        errors += update_claims_dedrems(data["uuids"], user)

        return errors


class SkipClaimsReviewMutation(OpenIMISMutation):
    """
    Skip review for one or several claims
    Skip indicates that the claim is not selected for review
    """
    _mutation_module = "claim"
    _mutation_class = "SkipClaimsReviewMutation"

    class Input(OpenIMISMutation.Input):
        uuids = graphene.List(graphene.String)

    @classmethod
    def async_mutate(cls, user, **data):
        if not user.has_perms(ClaimConfig.gql_mutation_skip_claim_review_perms):
            raise PermissionDenied(_("unauthorized"))
        return set_claims_status(data['uuids'], 'review_status', Claim.REVIEW_NOT_SELECTED)


class SaveClaimReviewMutation(OpenIMISMutation):
    """
    Save the review of a claim (items and services)
    """
    _mutation_module = "claim"
    _mutation_class = "SaveClaimReviewMutation"

    class Input(OpenIMISMutation.Input):
        claim_uuid = graphene.String(required=False, read_only=True)
        adjustment = graphene.String(required=False)
        items = graphene.List(ClaimItemInputType, required=False)
        services = graphene.List(ClaimServiceInputType, required=False)
        submit_review = graphene.Boolean(required=False)

    @classmethod
    def async_mutate(cls, user, **data):
        claim = None
        try:
            if not user.has_perms(ClaimConfig.gql_mutation_deliver_claim_review_perms):
                raise PermissionDenied(_("unauthorized"))
            claim = Claim.objects.get(uuid=UUID(str(data['claim_uuid'])),
                                      validity_to__isnull=True)
            if claim is None:
                return [{'message': _(
                    "claim.validation.id_does_not_exist") % {'id': data['claim_uuid']}}]
            claim.save_history()
            claim.adjustment = data.get('adjustment', None)
            items = data.pop('items') if 'items' in data else []
            all_rejected = True
            for item in items:
                item_id = item.pop('id')
                claim.items.filter(id=item_id).update(**item)
                if item['status'] == ClaimItem.STATUS_PASSED:
                    all_rejected = False
            services = data.pop('services') if 'services' in data else []
            claimed = 0
            update_claimed = False
            claim_service_elements = []
            for service in services:
                service_id = service.pop('id')
                service_item_set = service.pop('service_item_set', [])
                logger.debug(f"service_item_set {service_item_set}")
                service_service_set = service.pop('service_service_set', [])
                logger.debug(f"service_service_set {service_service_set} ")
                claim.services.filter(id=service_id).update(**service)
                for claim_service_service in service_service_set:
                    claim_service_code = claim_service_service.pop(
                        'sub_service_code')
                    claim_service = claim.services.filter(
                        id=service_id).first()
                    if claim_service:
                        service_element = Service.objects.filter(
                            *filter_validity(), code=claim_service_code).first()
                        if service_element:
                            claim_service_to_update = claim_service.services.filter(
                                service=service_element.id)
                            logger.debug(
                                f"claim_service_to_update {claim_service_to_update}")
                            if claim_service_to_update:
                                update_claimed = True
                                qty_asked = claim_service_service.pop(
                                    'qty_asked', 0)
                                price_asked = claim_service_service.pop(
                                    'price_asked', 0)
                                claim_service_service['qty_displayed'] = qty_asked
                                price = qty_asked * price_asked
                                service = Service.objects.get(
                                    id=service_id, validity_to__isnull=True)
                                if service.manualPrice:
                                    price = service.price
                                claimed += price
                                claim_service_to_update.update(
                                    **claim_service_service)
                        claim_service_elements.append(claim_service)
                for claim_service_item in service_item_set:
                    claim_item_code = claim_service_item.pop('sub_item_code')
                    claim_service = claim.services.filter(
                        id=service_id).first()
                    if claim_service:
                        item_element = Item.objects.filter(
                            *filter_validity(), code=claim_item_code).first()
                        if item_element:
                            claim_item_to_update = claim_service.items.filter(
                                item=item_element.id)
                            logger.debug(f"claim_item_to_update {claim_item_to_update}")
                            if claim_item_to_update:
                                update_claimed = True
                                qty_asked = claim_service_item.pop(
                                    'qty_asked', 0)
                                price_asked = claim_service_item.pop(
                                    'price_asked', 0)
                                claim_service_item['qty_displayed'] = qty_asked
                                price = qty_asked * price_asked
                                service = Service.objects.get(
                                    id=service_id, validity_to__isnull=True)
                                if service.manualPrice:
                                    price = service.price
                                claimed += price
                                claim_item_to_update.update(
                                    **claim_service_item)

                if service['status'] == ClaimService.STATUS_PASSED:
                    all_rejected = False
            claim.approved = approved_amount(claim)
            if update_claimed:
                claim.claimed = claimed
                for claimservice in claim_service_elements:
                    setattr(claimservice, 'price_adjusted', claimed)
            claim.audit_user_id_review = user.id_for_audit
            if all_rejected:
                claim.status = Claim.STATUS_REJECTED
            submit_review = data.get('submit_review', False)
            if submit_review:
                claim.review_status = Claim.REVIEW_DELIVERED
            claim.save()
            if submit_review:
                errors = update_claims_dedrems(None, user, [claim])
                if errors:
                    return errors

            return None
        except Exception as exc:
            return [{
                'message': _("claim.mutation.failed_to_update_claim") % {'code': claim.code if claim else None},
                'detail': str(exc)}]


class ProcessClaimsMutation(OpenIMISMutation, ClaimSubmissionStatsMixin):
    """
    Process one or several claims.
    """
    _mutation_module = "claim"
    _mutation_class = "ProcessClaimsMutation"

    class Input(OpenIMISMutation.Input):
        uuids = graphene.List(graphene.String)

    @classmethod
    def _parse_submission_stats(cls, claim_submission_stats):
        return {
            "submitted": claim_submission_stats["submitted"],
            "processed": claim_submission_stats["processed"],
            "valuated": claim_submission_stats["valuated"],
            "rejected": claim_submission_stats["rejected"],
            "header": "Submitted to process",
            # failed
        }

    @classmethod
    def async_mutate(cls, user, **data):
        if not user.has_perms(ClaimConfig.gql_mutation_process_claims_perms):
            raise PermissionDenied(_("unauthorized"))
        errors = []
        uuids = data.get("uuids", None)
        client_mutation_id = data.get("client_mutation_id", None)
        claims = Claim.objects \
            .filter(uuid__in=uuids) \
            .prefetch_related(Prefetch('items', queryset=ClaimItem.objects.filter(*filter_validity())))\
            .prefetch_related(Prefetch('services', queryset=ClaimService.objects.filter(*filter_validity())))
        remaining_uuid = list(map(str.upper, uuids))
        for claim in claims:
            remaining_uuid.remove(claim.uuid.upper())
            logger.debug(
              "ProcessClaimsMutation: processing %s", 
              claim.uuid
            )
            c_errors = []
            claim.save_history()
            claim.audit_user_id_process = user.id_for_audit
            logger.debug("ProcessClaimsMutation: validating claim %s", claim.uuid)
            c_errors += processing_claim(claim, user, True)
            logger.debug("ProcessClaimsMutation: claim %s set processed or valuated", claim.uuid)

            if c_errors:
                errors.append({
                    'title': claim.code,
                    'list': c_errors
                })
            claim.save()
        if len(remaining_uuid):
            errors += {
                'title': _('error'),
                'list': [{'message': _(
                    "claim.validation.id_does_not_exist") % {'id': ','.join(remaining_uuid)}}]
            }
        if len(errors) == 1:
            errors = errors[0]['list']
        cls.add_submission_stats_to_mutation_log(client_mutation_id, uuids)
        logger.debug("ProcessClaimsMutation: claims %s done, errors: %s",
                     data["uuids"], len(errors))
        return errors


class DeleteClaimsMutation(OpenIMISMutation):
    """
    Mark one or several claims as Deleted (validity_to)
    """

    class Input(OpenIMISMutation.Input):
        uuids = graphene.List(graphene.String)

    _mutation_module = "claim"
    _mutation_class = "DeleteClaimsMutation"

    @classmethod
    def async_mutate(cls, user, **data):
        if not user.has_perms(ClaimConfig.gql_mutation_delete_claims_perms):
            raise PermissionDenied(_("unauthorized"))
        errors = []
        for claim_uuid in data["uuids"]:
            claim = Claim.objects \
                .filter(uuid=claim_uuid) \
                .prefetch_related(Prefetch('items', queryset=ClaimItem.objects.filter(*filter_validity())))\
                .prefetch_related(Prefetch('services', queryset=ClaimService.objects.filter(*filter_validity())))\
                .first()
            if claim is None:
                errors += {
                    'title': claim_uuid,
                    'list': [{'message': _(
                        "claim.validation.id_does_not_exist") % {'id': claim_uuid}}]
                }
                continue
            errors += set_claim_deleted(claim)
        if len(errors) == 1:
            errors = errors[0]['list']
        return errors


def set_claim_deleted(claim):
    try:
        claim.delete_history()
        return []
    except Exception as exc:
        return {
            'title': claim.code,
            'list': [{
                'message': _("claim.mutation.failed_to_change_status_of_claim") % {'code': claim.code},
                'detail': claim.uuid}]
        }


def processing_claim(claim, user, is_process):
    return service_processing_claim(claim, user, is_process)


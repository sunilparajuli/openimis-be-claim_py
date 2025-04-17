import uuid

from claim_batch import models as claim_batch_models
from core import fields, TimeUtils
from core import models as core_models
from django import dispatch
from django.conf import settings
from django.db import models
from graphql import ResolveInfo
from insuree import models as insuree_models
from location import models as location_models
from location.models import LocationManager
from medical import models as medical_models
from policy import models as policy_models
from product import models as product_models
from django.apps import apps
from django.utils import timezone as django_tz

core_config = apps.get_app_config('core')
ClaimAdmin = core_models.ClaimAdmin

class Feedback(core_models.VersionedModel):
    id = models.AutoField(db_column='FeedbackID', primary_key=True)
    uuid = models.CharField(db_column='FeedbackUUID',
                            max_length=36, default=uuid.uuid4, unique=True)
    claim = models.OneToOneField(
        "Claim", models.DO_NOTHING, db_column='ClaimID', blank=True, null=True, related_name="+")
    care_rendered = models.BooleanField(
        db_column='CareRendered', blank=True, null=True)
    payment_asked = models.BooleanField(
        db_column='PaymentAsked', blank=True, null=True)
    drug_prescribed = models.BooleanField(
        db_column='DrugPrescribed', blank=True, null=True)
    drug_received = models.BooleanField(
        db_column='DrugReceived', blank=True, null=True)
    asessment = models.SmallIntegerField(
        db_column='Asessment', blank=True, null=True)
    # No FK in database (so value may not be an existing officer.id !)
    officer_id = models.IntegerField(
        db_column='CHFOfficerCode', blank=True, null=True)
    feedback_date = fields.DateTimeField(
        db_column='FeedbackDate', blank=True, null=True)
    audit_user_id = models.IntegerField(db_column='AuditUserID')

    class Meta:
        managed = True
        db_table = 'tblFeedback'

    @classmethod
    def get_queryset(cls, queryset, user):
        queryset = cls.filter_queryset(queryset)
        # GraphQL calls with an info object while Rest calls with the user itself
        if isinstance(user, ResolveInfo):
            user = user.context.user
        if settings.ROW_SECURITY and user.is_anonymous:
            return queryset.filter(id=-1)
        if settings.ROW_SECURITY:
            queryset = LocationManager().build_user_location_filter_query(
                user._u, prefix='health_facility__location', queryset=queryset, loc_types=['D'])
        return queryset


signal_claim_rejection = dispatch.Signal(["claim"])


class Claim(core_models.VersionedModel, core_models.ExtendableModel):
    id = models.AutoField(db_column='ClaimID', primary_key=True)
    uuid = models.CharField(db_column='ClaimUUID',
                            max_length=36, default=uuid.uuid4, unique=True)
    category = models.CharField(
        db_column='ClaimCategory', max_length=1, blank=True, null=True)
    insuree = models.ForeignKey(
        insuree_models.Insuree, models.DO_NOTHING, db_column='InsureeID')
    # do not change max_length value - use setting from apps.py
    code = models.CharField(db_column='ClaimCode', max_length=50)
    date_from = fields.DateField(db_column='DateFrom')
    date_to = fields.DateField(db_column='DateTo', blank=True, null=True)
    status = models.SmallIntegerField(db_column='ClaimStatus')
    restore = models.ForeignKey(
        'self', db_column='RestoredClaim', on_delete=models.DO_NOTHING, blank=True, null=True)
    adjuster = models.ForeignKey(
        core_models.InteractiveUser, models.DO_NOTHING,
        db_column='Adjuster', blank=True, null=True)
    adjustment = models.TextField(
        db_column='Adjustment', blank=True, null=True)
    claimed = models.DecimalField(
        db_column='Claimed',
        max_digits=18, decimal_places=2, blank=True, null=True)
    approved = models.DecimalField(
        db_column='Approved',
        max_digits=18, decimal_places=2, blank=True, null=True)
    reinsured = models.DecimalField(
        db_column='Reinsured',
        max_digits=18, decimal_places=2, blank=True, null=True)
    valuated = models.DecimalField(
        db_column='Valuated', max_digits=18, decimal_places=2, blank=True, null=True)
    date_claimed = fields.DateField(db_column='DateClaimed')
    date_processed = fields.DateField(
        db_column='DateProcessed', blank=True, null=True)
    # Django uses the feedback_id column to create the feedback column, which conflicts with the boolean field
    feedback_available = models.BooleanField(
        db_column='Feedback', default=False)
    feedback = models.OneToOneField(
        Feedback, models.DO_NOTHING,
        db_column='FeedbackID', blank=True, null=True, related_name="+")
    explanation = models.TextField(
        db_column='Explanation', blank=True, null=True)
    feedback_status = models.SmallIntegerField(
        db_column='FeedbackStatus', blank=True, null=True, default=1)
    review_status = models.SmallIntegerField(
        db_column='ReviewStatus', blank=True, null=True, default=1)
    approval_status = models.SmallIntegerField(
        db_column='ApprovalStatus', blank=True, null=True, default=1)
    rejection_reason = models.SmallIntegerField(
        db_column='RejectionReason', blank=True, null=True, default=0)

    batch_run = models.ForeignKey(claim_batch_models.BatchRun,
                                  models.DO_NOTHING, db_column='RunID', blank=True, null=True)
    audit_user_id = models.IntegerField(db_column='AuditUserID')
    validity_from_review = fields.DateTimeField(
        db_column='ValidityFromReview', blank=True, null=True)
    validity_to_review = fields.DateTimeField(
        db_column='ValidityToReview', blank=True, null=True)

    health_facility = models.ForeignKey(
        location_models.HealthFacility, models.DO_NOTHING, db_column='HFID')

    submit_stamp = fields.DateTimeField(
        db_column='SubmitStamp', blank=True, null=True)
    process_stamp = fields.DateTimeField(
        db_column='ProcessStamp', blank=True, null=True)
    remunerated = models.DecimalField(
        db_column='Remunerated', max_digits=18, decimal_places=2, blank=True, null=True)
    guarantee_id = models.CharField(
        db_column='GuaranteeId', max_length=50, blank=True, null=True)
    admin = models.ForeignKey(
        ClaimAdmin, models.DO_NOTHING, db_column='ClaimAdminId',
        blank=True, null=True)
    refer_from = models.ForeignKey(
        location_models.HealthFacility, models.DO_NOTHING, related_name='referFromHF',
        db_column='ReferFrom', blank=True, null=True)
    refer_to = models.ForeignKey(
        location_models.HealthFacility, models.DO_NOTHING, related_name='referToHF',
        db_column='ReferTo', blank=True, null=True)
    icd = models.ForeignKey(
        medical_models.Diagnosis, models.DO_NOTHING, db_column='ICDID',
        related_name="claim_icds")
    icd_1 = models.ForeignKey(
        medical_models.Diagnosis, models.DO_NOTHING, db_column='ICDID1',
        related_name="claim_icd1s",
        blank=True, null=True)
    icd_2 = models.ForeignKey(
        medical_models.Diagnosis, models.DO_NOTHING, db_column='ICDID2',
        related_name="claim_icd2s",
        blank=True, null=True)
    icd_3 = models.ForeignKey(
        medical_models.Diagnosis, models.DO_NOTHING, db_column='ICDID3',
        related_name="claim_icd3s",
        blank=True, null=True)
    icd_4 = models.ForeignKey(
        medical_models.Diagnosis, models.DO_NOTHING, db_column='ICDID4',
        related_name="claim_icd4s",
        blank=True, null=True)

    visit_type = models.CharField(
        db_column='VisitType', max_length=1, blank=True, null=True)
    audit_user_id_review = models.IntegerField(
        db_column='AuditUserIDReview', blank=True, null=True)
    audit_user_id_submit = models.IntegerField(
        db_column='AuditUserIDSubmit', blank=True, null=True)
    audit_user_id_process = models.IntegerField(
        db_column='AuditUserIDProcess', blank=True, null=True)
    care_type = models.CharField(
        db_column='CareType', max_length=4, blank=True, null=True)
    pre_authorization = models.BooleanField(
        default=False, blank=True, null=True)
    patient_condition = models.CharField(max_length=2, null=True, blank=True)
    referral_code = models.CharField(max_length=50, null=True, blank=True)

    # row_id = models.BinaryField(db_column='RowID', blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'tblClaim'

    STATUS_REJECTED = 1
    STATUS_ENTERED = 2
    STATUS_CHECKED = 4
    STATUS_PROCESSED = 8
    STATUS_VALUATED = 16

    FEEDBACK_IDLE = 1
    FEEDBACK_NOT_SELECTED = 2
    FEEDBACK_SELECTED = 4
    FEEDBACK_DELIVERED = 8
    FEEDBACK_BYPASSED = 16

    REVIEW_IDLE = 1
    REVIEW_NOT_SELECTED = 2
    REVIEW_SELECTED = 4
    REVIEW_DELIVERED = 8
    REVIEW_BYPASSED = 16

    def reject(self, rejection_code):
        updated_items = self.items.filter(validity_to__isnull=True).update(
            rejection_reason=rejection_code)
        updated_services = self.services.filter(
            validity_to__isnull=True).update(rejection_reason=rejection_code)
        signal_claim_rejection.send(sender=self.__class__, claim=self)
        return updated_items + updated_services

    def save_history(self, **kwargs):
        prev_id = super(Claim, self).save_history()
        if prev_id:
            prev_items = []
            for item in self.items.all():
                prev_items.append(item.save_history())
            ClaimItem.objects.filter(
                id__in=prev_items).update(claim_id=prev_id)
            prev_services = []
            for service in self.services.all():
                prev_services.append(service.save_history())
            ClaimService.objects.filter(
                id__in=prev_services).update(claim_id=prev_id)
        return prev_id

    @classmethod
    def get_queryset(cls, queryset, user):
        queryset = Claim.filter_queryset(queryset)
        # GraphQL calls with an info object while Rest calls with the user itself
        if isinstance(user, ResolveInfo):
            user = user.context.user
        if settings.ROW_SECURITY and user.is_anonymous:
            return queryset.filter(id=-1)
        if settings.ROW_SECURITY:
            # TechnicalUsers don't have health_facility_id attribute
            if hasattr(user._u, 'health_facility_id') and user._u.health_facility_id:
                queryset = queryset.filter(
                    health_facility_id=user._u.health_facility_id
                )
            else:
                if not isinstance(user._u, core_models.TechnicalUser):
                    queryset = LocationManager().build_user_location_filter_query(
                        user._u, prefix='health_facility__location', queryset=queryset, loc_types=['D'])
        return queryset


class FeedbackPrompt(core_models.VersionedModel):
    id = models.AutoField(db_column='FeedbackPromptID', primary_key=True)
    feedback_prompt_date = fields.DateField(
        db_column='FeedbackPromptDate', blank=True, null=True)
    claim = models.ForeignKey(
        Claim, models.DO_NOTHING, db_column='ClaimID', blank=True, null=True, related_name="+")
    officer = models.ForeignKey(
        core_models.Officer, models.DO_NOTHING, db_column="OfficerID", blank=True, null=True)
    phone_number = models.CharField(
        db_column='PhoneNumber', max_length=50, blank=True, null=True)
    sms_status = models.IntegerField(
        db_column='SMSStatus', blank=True, null=True)
    validity_from = fields.DateTimeField(
        db_column='ValidityFrom', blank=True, null=True)
    validity_to = fields.DateTimeField(
        db_column='ValidityTo', blank=True, null=True)
    legacy_id = models.IntegerField(
        db_column='LegacyID', blank=True, null=True)
    audit_user_id = models.IntegerField(
        db_column='AuditUserID', blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'tblFeedbackPrompt'

    @classmethod
    def get_queryset(cls, queryset, user):
        queryset = cls.filter_queryset(queryset)
        # GraphQL calls with an info object while Rest calls with the user itself
        if isinstance(user, ResolveInfo):
            user = user.context.user
        if settings.ROW_SECURITY and user.is_anonymous:
            return queryset.filter(id=-1)
        if settings.ROW_SECURITY:
            queryset = LocationManager().build_user_location_filter_query(
                user._u, prefix='health_facility__location', queryset=queryset, loc_types=['D'])

        return queryset


class ClaimAttachmentsCount(models.Model):
    claim = models.OneToOneField(
        Claim, primary_key=True, related_name='attachments_count', on_delete=models.DO_NOTHING)
    value = models.IntegerField(db_column='attachments_count')

    class Meta:
        managed = True
        db_table = 'claim_ClaimAttachmentsCountView'


class ClaimMutation(core_models.UUIDModel):
    claim = models.ForeignKey(Claim, models.DO_NOTHING,
                              related_name='mutations')
    mutation = models.ForeignKey(
        core_models.MutationLog, models.DO_NOTHING, related_name='claims')

    class Meta:
        managed = True
        db_table = "claim_ClaimMutation"


class ClaimDetailManager(core_models.CachedManager):

    def filter(self, *args, **kwargs):
        keys = [x for x in kwargs if "itemsvc" in x]
        for key in keys:
            new_key = key.replace("itemsvc", self.model.model_prefix)
            kwargs[new_key] = kwargs.pop(key)
        return super(ClaimDetailManager, self).filter(*args, **kwargs)


class ClaimDetail:
    STATUS_PASSED = 1
    STATUS_REJECTED = 2

    objects = ClaimDetailManager()

    
    @property
    def itemsvc(self):
        if hasattr(self, "item"):
            return self.item
        elif hasattr(self, "service"):
            return self.service
        else:
            raise Exception("ClaimDetail has neither item nor service")


    def get_value(self):
        if self.status != self.STATUS_REJECTED and not self.rejection_reason:
            qty = self.qty_approved or self.qty_provided or 0
            price = self.price_approved or self.price_adjusted or self.price_asked or 0
        return qty * price
    
    class Meta:
        abstract = True


class ClaimItem(core_models.VersionedModel, ClaimDetail, core_models.ExtendableModel):
    model_prefix = "item"
    id = models.AutoField(db_column='ClaimItemID', primary_key=True)
    claim = models.ForeignKey(Claim, models.DO_NOTHING,
                              db_column='ClaimID', related_name='items')
    item = models.ForeignKey(
        medical_models.Item, models.DO_NOTHING, db_column='ItemID')
    product = models.ForeignKey(product_models.Product,
                                models.DO_NOTHING, db_column='ProdID',
                                blank=True, null=True,
                                related_name="claim_items")
    status = models.SmallIntegerField(db_column='ClaimItemStatus')
    availability = models.BooleanField(db_column='Availability')
    qty_provided = models.DecimalField(
        db_column='QtyProvided', max_digits=18, decimal_places=2)
    qty_approved = models.DecimalField(
        db_column='QtyApproved', max_digits=18, decimal_places=2, blank=True, null=True)
    price_asked = models.DecimalField(
        db_column='PriceAsked', max_digits=18, decimal_places=2)
    price_adjusted = models.DecimalField(
        db_column='PriceAdjusted', max_digits=18, decimal_places=2, blank=True, null=True)
    price_approved = models.DecimalField(
        db_column='PriceApproved', max_digits=18, decimal_places=2, blank=True, null=True)
    price_valuated = models.DecimalField(
        db_column='PriceValuated', max_digits=18, decimal_places=2, blank=True, null=True)
    explanation = models.TextField(
        db_column='Explanation', blank=True, null=True)
    justification = models.TextField(
        db_column='Justification', blank=True, null=True)
    rejection_reason = models.SmallIntegerField(
        db_column='RejectionReason', blank=True, null=True)
    audit_user_id = models.IntegerField(db_column='AuditUserID')
    validity_from_review = fields.DateTimeField(
        db_column='ValidityFromReview', blank=True, null=True)
    validity_to_review = fields.DateTimeField(
        db_column='ValidityToReview', blank=True, null=True)
    audit_user_id_review = models.IntegerField(
        db_column='AuditUserIDReview', blank=True, null=True)
    limitation_value = models.DecimalField(
        db_column='LimitationValue', max_digits=18, decimal_places=2, blank=True, null=True)
    limitation = models.CharField(
        db_column='Limitation', max_length=1, blank=True, null=True)
    policy = models.ForeignKey(
        policy_models.Policy, models.DO_NOTHING, db_column='PolicyID', blank=True, null=True)
    remunerated_amount = models.DecimalField(
        db_column='RemuneratedAmount', max_digits=18, decimal_places=2, blank=True, null=True)
    deductable_amount = models.DecimalField(
        db_column='DeductableAmount', max_digits=18, decimal_places=2, blank=True, null=True)
    exceed_ceiling_amount = models.DecimalField(
        db_column='ExceedCeilingAmount', max_digits=18, decimal_places=2, blank=True, null=True)
    price_origin = models.CharField(
        db_column='PriceOrigin', max_length=1, blank=True, null=True)
    exceed_ceiling_amount_category = models.DecimalField(
        db_column='ExceedCeilingAmountCategory', max_digits=18, decimal_places=2, blank=True, null=True)
    objects = ClaimDetailManager()

    class Meta:
        managed = True
        db_table = 'tblClaimItems'


class GeneralClaimAttachmentType(models.TextChoices):
    URL = "URL"
    FILE = "FILE"


class ClaimAttachmentType(core_models.VersionedModel):
    id = models.SmallIntegerField(
        db_column='ClaimAttachmentTypeId', primary_key=True)
    claim_attachment_type = models.CharField(
        db_column='ClaimAttachmentType', max_length=50)
    is_autogenerated = models.BooleanField(default=False)
    claim_general_type = models.CharField(max_length=10, default=GeneralClaimAttachmentType.FILE,
                                          choices=GeneralClaimAttachmentType.choices)

    class Meta:
        managed = True
        db_table = 'claim_ClaimAttachment_ClaimAttachmentType'


class ClaimAttachment(core_models.UUIDModel, core_models.UUIDVersionedModel):
    claim = models.ForeignKey(
        Claim, models.DO_NOTHING, related_name='attachments')
    general_type = models.CharField(max_length=4, choices=GeneralClaimAttachmentType.choices,
                                    default=GeneralClaimAttachmentType.FILE)
    type = models.TextField(blank=True, null=True)
    predefined_type = models.ForeignKey(ClaimAttachmentType, models.DO_NOTHING, related_name='type_dropdown', null=True,
                                        blank=True)
    title = models.TextField(blank=True, null=True)
    date = fields.DateField(blank=True, default=TimeUtils.now)
    filename = models.TextField(blank=True, null=True)
    mime = models.TextField(blank=True, null=True)
    # this is not needed at the moment, but we want to move attachment to core
    # in that case module information is needed, and we want to avoid writing additional migration
    module = models.TextField(blank=False, null=True)
    # frontend contributions may lead to externalized (nas) storage for documents
    url = models.TextField(blank=True, null=True)
    # Support of BinaryField is database-related: prefer to stick to b64-encoded
    document = models.TextField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = "claim_ClaimAttachment"


class ClaimService(core_models.VersionedModel, ClaimDetail, core_models.ExtendableModel):
    model_prefix = "service"
    id = models.AutoField(db_column='ClaimServiceID', primary_key=True)
    claim = models.ForeignKey(
        Claim, models.DO_NOTHING, db_column='ClaimID', related_name='services')
    service = models.ForeignKey(
        medical_models.Service, models.DO_NOTHING, db_column='ServiceID')
    product = models.ForeignKey(product_models.Product,
                                models.DO_NOTHING, db_column='ProdID',
                                blank=True, null=True,
                                related_name="claim_services")
    status = models.SmallIntegerField(db_column='ClaimServiceStatus')
    qty_provided = models.DecimalField(
        db_column='QtyProvided', max_digits=18, decimal_places=2)
    qty_approved = models.DecimalField(
        db_column='QtyApproved', max_digits=18, decimal_places=2, blank=True, null=True)
    price_asked = models.DecimalField(
        db_column='PriceAsked', max_digits=18, decimal_places=2)
    price_adjusted = models.DecimalField(
        db_column='PriceAdjusted', max_digits=18, decimal_places=2, blank=True, null=True)
    price_approved = models.DecimalField(
        db_column='PriceApproved', max_digits=18, decimal_places=2, blank=True, null=True)
    price_valuated = models.DecimalField(
        db_column='PriceValuated', max_digits=18, decimal_places=2, blank=True, null=True)
    explanation = models.TextField(
        db_column='Explanation', blank=True, null=True)
    justification = models.TextField(
        db_column='Justification', blank=True, null=True)
    rejection_reason = models.SmallIntegerField(
        db_column='RejectionReason', blank=True, null=True)
    audit_user_id = models.IntegerField(db_column='AuditUserID')
    validity_from_review = fields.DateTimeField(
        db_column='ValidityFromReview', blank=True, null=True)
    validity_to_review = fields.DateTimeField(
        db_column='ValidityToReview', blank=True, null=True)
    audit_user_id_review = models.IntegerField(
        db_column='AuditUserIDReview', blank=True, null=True)
    limitation_value = models.DecimalField(
        db_column='LimitationValue', max_digits=18, decimal_places=2, blank=True, null=True)
    limitation = models.CharField(
        db_column='Limitation', max_length=1, blank=True, null=True)
    policy = models.ForeignKey(
        policy_models.Policy, models.DO_NOTHING, db_column='PolicyID', blank=True, null=True)
    remunerated_amount = models.DecimalField(
        db_column='RemuneratedAmount', max_digits=18, decimal_places=2, blank=True, null=True)
    deductable_amount = models.DecimalField(
        db_column='DeductableAmount', max_digits=18, decimal_places=2, blank=True, null=True)
    exceed_ceiling_amount = models.DecimalField(
        db_column='ExceedCeilingAmount', max_digits=18, decimal_places=2, blank=True, null=True)
    price_origin = models.CharField(
        db_column='PriceOrigin', max_length=1, blank=True, null=True)
    exceed_ceiling_amount_category = models.DecimalField(
        db_column='ExceedCeilingAmountCategory', max_digits=18, decimal_places=2, blank=True, null=True)
    objects = ClaimDetailManager()

    class Meta:
        managed = True
        db_table = 'tblClaimServices'


class ClaimServiceItem(models.Model):
    id = models.AutoField(primary_key=True, db_column='idCsi')
    item = models.ForeignKey(medical_models.Item, models.DO_NOTHING,
                             db_column='ItemID', related_name="service_items")
    claim_service = models.ForeignKey(ClaimService,
                                      models.DO_NOTHING, db_column="ClaimServiceID", related_name='items')
    qty_provided = models.IntegerField(db_column="qty_provided",
                                       blank=True, null=True)
    qty_displayed = models.IntegerField(db_column="qty_displayed",
                                        blank=True, null=True)
    created_date = models.DateTimeField(db_column="created_date", default=django_tz.now,
                                        blank=True, null=True)
    price_asked = models.DecimalField(db_column="price",
                                      max_digits=18, decimal_places=2, blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'tblClaimServicesItems'


class ClaimServiceService(models.Model):
    id = models.AutoField(primary_key=True, db_column='idCss')
    service = models.ForeignKey(medical_models.Service, models.DO_NOTHING,
                                db_column='ServiceId', related_name='service_services')
    claim_service = models.ForeignKey(ClaimService,
                                      models.DO_NOTHING, db_column="claimServiceID", related_name='services')
    qty_provided = models.IntegerField(db_column="qty_provided",
                                       blank=True, null=True)
    qty_displayed = models.IntegerField(db_column="qty_displayed",
                                        blank=True, null=True)
    created_date = models.DateTimeField(db_column="created_date", default=django_tz.now,
                                        blank=True, null=True)
    price_asked = models.DecimalField(db_column="price",
                                      max_digits=18, decimal_places=2, blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'tblClaimServicesService'


class ClaimDedRem(core_models.VersionedModel):
    id = models.AutoField(db_column='ExpenditureID', primary_key=True)

    policy = models.ForeignKey('policy.Policy', models.DO_NOTHING, db_column='PolicyID', blank=False, null=False,
                               related_name='claim_ded_rems')
    insuree = models.ForeignKey('insuree.Insuree', models.DO_NOTHING, db_column='InsureeID', blank=True, null=True,
                                related_name='claim_ded_rems')
    claim = models.ForeignKey(to=Claim, db_column='ClaimID', db_index=True, related_name="dedrems",
                              on_delete=models.DO_NOTHING)
    ded_g = models.DecimalField(
        db_column='DedG', max_digits=18, decimal_places=2, blank=True, null=True)
    ded_op = models.DecimalField(
        db_column='DedOP', max_digits=18, decimal_places=2, blank=True, null=True)
    ded_ip = models.DecimalField(
        db_column='DedIP', max_digits=18, decimal_places=2, blank=True, null=True)
    rem_g = models.DecimalField(
        db_column='RemG', max_digits=18, decimal_places=2, blank=True, null=True)
    rem_op = models.DecimalField(
        db_column='RemOP', max_digits=18, decimal_places=2, blank=True, null=True)
    rem_ip = models.DecimalField(
        db_column='RemIP', max_digits=18, decimal_places=2, blank=True, null=True)
    rem_consult = models.DecimalField(
        db_column='RemConsult', max_digits=18, decimal_places=2, blank=True, null=True)
    rem_surgery = models.DecimalField(
        db_column='RemSurgery', max_digits=18, decimal_places=2, blank=True, null=True)
    rem_delivery = models.DecimalField(
        db_column='RemDelivery', max_digits=18, decimal_places=2, blank=True, null=True)
    rem_hospitalization = models.DecimalField(db_column='RemHospitalization', max_digits=18, decimal_places=2,
                                              blank=True, null=True)
    rem_antenatal = models.DecimalField(db_column='RemAntenatal', max_digits=18, decimal_places=2,
                                        blank=True, null=True)

    audit_user_id = models.IntegerField(db_column='AuditUserID')

    class Meta:
        managed = True
        db_table = 'tblClaimDedRem'

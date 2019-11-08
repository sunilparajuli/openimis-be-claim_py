from core import fields
import uuid

from django import dispatch
from django.db import models
from core import models as core_models
from insuree import models as insuree_models
from location import models as location_models
from medical import models as medical_models
from policy import models as policy_models
from product import models as product_models
from claim_batch import models as claim_batch_models


class ClaimAdmin(core_models.VersionedModel):
    id = models.AutoField(db_column='ClaimAdminId', primary_key=True)
    uuid = models.CharField(db_column='ClaimAdminUUID',
                            max_length=36, default=uuid.uuid4, unique=True)
    code = models.CharField(db_column='ClaimAdminCode',
                            max_length=8, blank=True, null=True)
    last_name = models.CharField(
        db_column='LastName', max_length=100, blank=True, null=True)
    other_names = models.CharField(
        db_column='OtherNames', max_length=100, blank=True, null=True)
    dob = models.DateField(db_column='DOB', blank=True, null=True)
    email_id = models.CharField(
        db_column='EmailId', max_length=200, blank=True, null=True)
    phone = models.CharField(
        db_column='Phone', max_length=50, blank=True, null=True)
    health_facility = models.ForeignKey(
        location_models.HealthFacility, models.DO_NOTHING, db_column='HFId', blank=True, null=True)
    has_login = models.BooleanField(
        db_column='HasLogin', blank=True, null=True)

    audit_user_id = models.IntegerField(
        db_column='AuditUserId', blank=True, null=True)
    # row_id = models.BinaryField(db_column='RowId', blank=True, null=True)

    def __str__(self):
        return self.code + " " + self.last_name + " " + self.other_names

    class Meta:
        managed = False
        db_table = 'tblClaimAdmin'


class Feedback(core_models.VersionedModel):
    id = models.AutoField(db_column='FeedbackID', primary_key=True)
    uuid = models.CharField(db_column='FeedbackUUID',
                            max_length=36, default=uuid.uuid4, unique=True)
    claim = models.OneToOneField(
        "Claim", models.DO_NOTHING,
        db_column='ClaimID', blank=True, null=True, related_name="+")
    care_rendered = models.NullBooleanField(
        db_column='CareRendered', blank=True, null=True)
    payment_asked = models.NullBooleanField(
        db_column='PaymentAsked', blank=True, null=True)
    drug_prescribed = models.NullBooleanField(
        db_column='DrugPrescribed', blank=True, null=True)
    drug_received = models.NullBooleanField(
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
        managed = False
        db_table = 'tblFeedback'


signal_claim_rejection = dispatch.Signal(providing_args=["claim"])


class Claim(core_models.VersionedModel):
    id = models.AutoField(db_column='ClaimID', primary_key=True)
    uuid = models.CharField(db_column='ClaimUUID',
                            max_length=36, default=uuid.uuid4, unique=True)
    category = models.CharField(
        db_column='ClaimCategory', max_length=1, blank=True, null=True)
    insuree = models.ForeignKey(
        insuree_models.Insuree, models.DO_NOTHING, db_column='InsureeID')
    code = models.CharField(db_column='ClaimCode', max_length=8)
    date_from = fields.DateField(db_column='DateFrom')
    date_to = fields.DateField(db_column='DateTo', blank=True, null=True)
    status = models.SmallIntegerField(db_column='ClaimStatus')
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
        db_column='FeedbackStatus', blank=True, null=True)
    review_status = models.SmallIntegerField(
        db_column='ReviewStatus', blank=True, null=True)
    approval_status = models.SmallIntegerField(
        db_column='ApprovalStatus', blank=True, null=True)
    rejection_reason = models.SmallIntegerField(
        db_column='RejectionReason', blank=True, null=True)

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
    # row_id = models.BinaryField(db_column='RowID', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tblClaim'

    STATUS_REJECTED = 1
    STATUS_ENTERED = 2
    STATUS_CHECKED = 4
    STATUS_PROCESSED = 8
    STATUS_VALUATED = 16

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


class ClaimMutation(core_models.UUIDModel):
    claim = models.ForeignKey(Claim, models.DO_NOTHING,
                              related_name='mutations')
    mutation = models.ForeignKey(
        core_models.MutationLog, models.DO_NOTHING, related_name='claims')

    class Meta:
        managed = True
        db_table = "claim_ClaimMutation"


class ClaimItem(core_models.VersionedModel):
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
    validity_from = fields.DateTimeField(db_column='ValidityFrom')
    validity_to = fields.DateTimeField(
        db_column='ValidityTo', blank=True, null=True)
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

    class Meta:
        managed = False
        db_table = 'tblClaimItems'

    STATUS_PASSED = 1
    STATUS_REJECTED = 2


class ClaimAttachment(core_models.UUIDModel, core_models.VersionedModel):
    claim = models.ForeignKey(
        Claim, models.DO_NOTHING, related_name='attachments')
    type = models.TextField(blank=True, null=True)
    title = models.TextField(blank=True, null=True)
    date = fields.DateField(blank=True, null=True)
    filename = models.TextField(blank=True, null=True)
    mime = models.TextField(blank=True, null=True)
    # Support of BinaryField is database-related: prefer to stick to b64-encoded
    document = models.TextField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = "claim_ClaimAttachment"


class ClaimService(core_models.VersionedModel):
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
    validity_from = fields.DateTimeField(db_column='ValidityFrom')
    validity_to = fields.DateTimeField(
        db_column='ValidityTo', blank=True, null=True)
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

    class Meta:
        managed = False
        db_table = 'tblClaimServices'

    STATUS_PASSED = 1
    STATUS_REJECTED = 2

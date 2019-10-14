from core import fields
import uuid
from core import models as core_models
from core.models import VersionedModel
from django.db import models
from insuree import models as insuree_models
from location import models as location_models
from medical import models as medical_models
from policy import models as policy_models
from claim_batch import models as claim_batch_models


class ClaimAdmin(VersionedModel):
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


class Feedback(VersionedModel):
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
    chf_officer_code = models.IntegerField(
        db_column='CHFOfficerCode', blank=True, null=True)
    feedback_date = fields.DateTimeField(
        db_column='FeedbackDate', blank=True, null=True)
    audit_user_id = models.IntegerField(db_column='AuditUserID')

    class Meta:
        managed = False
        db_table = 'tblFeedback'


class Claim(VersionedModel):
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
        return updated_items + updated_services


class ClaimItem(VersionedModel):
    id = models.AutoField(db_column='ClaimItemID', primary_key=True)
    claim = models.ForeignKey(Claim, models.DO_NOTHING,
                              db_column='ClaimID', related_name='items')
    item = models.ForeignKey(
        medical_models.Item, models.DO_NOTHING, db_column='ItemID')
    product = models.ForeignKey('product.Product', models.DO_NOTHING, db_column='ProdID', blank=True, null=True,
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

    class Meta:
        managed = False
        db_table = 'tblClaimItems'

    STATUS_PASSED = 1
    STATUS_REJECTED = 2


class ClaimService(VersionedModel):
    id = models.AutoField(db_column='ClaimServiceID', primary_key=True)
    claim = models.ForeignKey(
        Claim, models.DO_NOTHING, db_column='ClaimID', related_name='services')
    service = models.ForeignKey(
        medical_models.Service, models.DO_NOTHING, db_column='ServiceID')
    # prod = models.ForeignKey('Tblproduct', models.DO_NOTHING, db_column='ProdID', blank=True, null=True)
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

    class Meta:
        managed = False
        db_table = 'tblClaimServices'

    STATUS_PASSED = 1
    STATUS_REJECTED = 2


class ClaimOfficer(VersionedModel):
    id = models.AutoField(db_column='OfficerID', primary_key=True)
    uuid = models.CharField(db_column='OfficerUUID',
                            max_length=36, default=uuid.uuid4, unique=True)
    code = models.CharField(db_column='Code', max_length=8)
    last_name = models.CharField(db_column='LastName', max_length=100)
    other_names = models.CharField(db_column='OtherNames', max_length=100)
    # dob = models.DateField(db_column='DOB', blank=True, null=True)
    # phone = models.CharField(db_column='Phone', max_length=50, blank=True, null=True)
    # location = models.ForeignKey(Tbllocations, models.DO_NOTHING, db_column='LocationId', blank=True, null=True)
    # officeridsubst = models.ForeignKey('self', models.DO_NOTHING, db_column='OfficerIDSubst', blank=True, null=True)
    # worksto = models.DateTimeField(db_column='WorksTo', blank=True, null=True)
    # veocode = models.CharField(db_column='VEOCode', max_length=8, blank=True, null=True)
    # veolastname = models.CharField(db_column='VEOLastName', max_length=100, blank=True, null=True)
    # veoothernames = models.CharField(db_column='VEOOtherNames', max_length=100, blank=True, null=True)
    # veodob = models.DateField(db_column='VEODOB', blank=True, null=True)
    # veophone = models.CharField(db_column='VEOPhone', max_length=25, blank=True, null=True)
    # audituserid = models.IntegerField(db_column='AuditUserID')
    # rowid = models.TextField(db_column='RowID', blank=True, null=True)   This field type is a guess.
    # emailid = models.CharField(db_column='EmailId', max_length=200, blank=True, null=True)
    # phonecommunication = models.BooleanField(db_column='PhoneCommunication', blank=True, null=True)
    # permanentaddress = models.CharField(max_length=100, blank=True, null=True)
    # haslogin = models.BooleanField(db_column='HasLogin', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tblOfficer'

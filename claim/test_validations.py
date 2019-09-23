from claim.models import Claim, ClaimService, ClaimItem
from claim.validations import get_claim_category, validate_claim
from django.test import TestCase
from insuree.models import Family, Insuree, InsureePolicy, Gender
from location.models import HealthFacility
from medical.models import Service, Item
from product.models import Product, ProductService
from policy.models import Policy
from medical_pricelist.models import ServicePricelistDetail


# default arguments should not pass a list or a dict because they're mutable but we don't risk mutating them here:
# noinspection PyDefaultArgument,DuplicatedCode
class ValidationTest(TestCase):
    service_H = None
    service_O = None
    service_D = None
    service_A = None
    service_A_invalid = None

    @staticmethod
    def _get_service_of_category(category, valid=True):
        return Service.objects.filter(category=category).filter(validity_to__isnull=valid).first()

    @staticmethod
    def _get_item_of_type(item_type, valid=True):
        return Item.objects.filter(type=item_type).filter(validity_to__isnull=valid).first()

    @staticmethod
    def _create_test_claim(custom_props={}):
        return Claim.objects.create(
            **{
                "health_facility_id": 18,
                "icd_id": 116,
                "date_from": "2019-06-01",
                "date_claimed": "2019-06-01",
                "date_to": "2019-06-01",
                "audit_user_id": 1,
                "insuree_id": 136,
                "status": 1,
                "validity_from": "2019-06-01",
                **custom_props
            }
        )

    @staticmethod
    def _create_test_claimitem(claim, item_type, valid=True, custom_props={}):
        return ClaimItem.objects.create(
            **{
                "claim": claim,
                "qty_provided": 7,
                "price_asked": 11,
                "item_id": ValidationTest._get_item_of_type(item_type).id if item_type else 23,  # Atropine
                "status": 1,
                "availability": True,
                "validity_from": "2019-06-01",
                "validity_to": None if valid else "2019-06-01",
                "audit_user_id": -1,
                **custom_props
               }
        )

    @staticmethod
    def _create_test_claimservice(claim, category=None, valid=True, custom_props={}):
        return ClaimService.objects.create(
            **{
                "claim": claim,
                "qty_provided": 7,
                "price_asked": 11,
                "service_id": ValidationTest._get_service_of_category(category).id if category else 23,  # Skin graft, no cat
                "status": 1,
                "validity_from": "2019-06-01",
                "validity_to": None if valid else "2019-06-01",
                "audit_user_id": -1,
                **custom_props
            }
        )

    @staticmethod
    def _create_test_service(category, valid=True, custom_props={}):
        return Service.objects.create(
            **{
                "code": "TST-" + category,
                "category": category,
                "name": "Test service " + category,
                "type": Service.TYPE_CURATIVE,
                "level": 1,
                "price": 100,
                "patient_category": 15,
                "care_type": Service.CARE_TYPE_OUT_PATIENT,
                "validity_from": "2019-06-01",
                "validity_to": None if valid else "2019-06-01",
                "audit_user_id": -1,
                **custom_props
            }
        )

    @staticmethod
    def _add_service_to_hf_pricelist(service, hf_id=18, custom_props={}):
        hf = HealthFacility.objects.get(pk=hf_id)
        return ServicePricelistDetail.objects.create(
            **{
                "service_pricelist": hf.service_pricelist,
                "service": service,
                "validity_from": "2019-01-01",
                "audit_user_id": -1,
                **custom_props
            }
        )

    @staticmethod
    def _create_test_item(item_type, valid=True, custom_props=None):
        return Item.objects.create(
            **{
                "code": "XXX",
                "type": item_type,
                "name": "Test item",
                "price": 100,
                "patient_category": 1,
                "care_type": 1,
                "validity_from": "2019-06-01",
                "validity_to": None if valid else "2019-06-01",
                "audit_user_id": -1,
                **(custom_props if custom_props else {})
            }
        )

    @staticmethod
    def _create_test_product(code, valid=True, custom_props=None):
        return Product.objects.create(
            **{
                "code": code,
                "name": "Test product " + code,
                "lump_sum": 123.45,
                "member_count": 1,
                "grace_period": 1,
                "date_from": "2019-06-01",
                "date_to": "2049-06-01",
                "validity_from": "2019-06-01",
                "validity_to": None if valid else "2019-06-01",
                "audit_user_id": -1,
                **(custom_props if custom_props else {})
            }
        )

    @staticmethod
    def _create_test_product_service(product, service, valid=True, custom_props=None):
        return ProductService.objects.create(
            **{
                "product": product,
                "service": service,
                "limitation_type": ProductService.LIMIT_CO_INSURANCE,
                "price_origin": ProductService.ORIGIN_PRICELIST,
                "validity_from": "2019-06-01",
                "validity_to": None if valid else "2019-06-01",
                "audit_user_id": -1,
                **(custom_props if custom_props else {})
            }
        )

    @staticmethod
    def _create_test_policy(product, insuree, link=True, valid=True, custom_props=None):
        policy = Policy.objects.create(
            **{
                "family": insuree.family,
                "product": product,
                "status": Policy.STATUS_ACTIVE,
                "stage": Policy.STAGE_NEW,
                "enroll_date": "2019-06-01",
                "start_date": "2019-06-02",
                "validity_from": "2019-06-01",
                "effective_date": "2019-06-01",
                "expiry_date": "2039-06-01",
                "validity_to": None if valid else "2019-06-01",
                "audit_user_id": -1,
                **(custom_props if custom_props else {})
            }
        )
        if link:
            insuree_policy = InsureePolicy.objects.create(
                insuree=insuree,
                policy=policy,
                audit_user_id=-1,
                effective_date="2019-06-01",
                expiry_date="2039-06-01",
                validity_from="2019-06-01",
                validity_to=None if valid else "2019-06-01",
            )
        return policy

    @staticmethod
    def _create_test_insuree(valid=True, with_family=True, custom_props=None):
        # insuree has a mandatory reference to family and family has a mandatory reference to insuree
        # So we first insert the family with a dummy id and then update it
        if with_family:
            family = Family.objects.create(
                validity_from="2019-01-01",
                head_insuree_id=1,  # dummy
                audit_user_id=-1,
            )
        else:
            family = None

        insuree = Insuree.objects.create(
            **{
                "last_name": "Test Last",
                "other_names": "First Second",
                "family": family,
                "gender": Gender.objects.get(code='M'),
                "dob": "1970-01-01",
                "head": True,
                "card_issued": True,
                "validity_from": "2019-01-01",
                "audit_user_id": -1,
                **(custom_props if custom_props else {})
            }
        )
        if with_family:
            family.head_insuree_id = insuree.id
            family.save()

        return insuree

    def setUp(self) -> None:
        self.service_H = self._create_test_service("H")
        self.service_O = self._create_test_service("O")
        self.service_D = self._create_test_service("D")
        self.service_A = self._create_test_service("A")
        self.service_A_invalid = self._create_test_service("A", False)

        self.item_1 = self._create_test_item("D")

    def tearDown(self) -> None:
        self.service_H.delete()
        self.service_O.delete()
        self.service_D.delete()
        self.service_A.delete()
        self.service_A_invalid.delete()

        self.item_1.delete()

    def test_get_claim_category_S(self):
        # Given
        claim = self._create_test_claim()
        service1 = self._create_test_claimservice(claim, "S")

        # when
        category = get_claim_category(claim)

        # then
        self.assertIsNotNone(category)
        self.assertEquals(category, "S")

        # tearDown
        service1.delete()
        claim.delete()

    def test_get_claim_category_D(self):
        # Given
        claim = self._create_test_claim()
        service1 = self._create_test_claimservice(claim, "D")

        # when
        category = get_claim_category(claim)

        # then
        self.assertIsNotNone(category)
        self.assertEquals(category, "D")

        # tearDown
        service1.delete()
        claim.delete()

    def test_get_claim_category_mix(self):
        # Given
        claim = self._create_test_claim()
        services = [
            self._create_test_claimservice(claim, "H"),
            self._create_test_claimservice(claim, "O"),
            self._create_test_claimservice(claim, None),
            self._create_test_claimservice(claim, "A"),
            self._create_test_claimservice(claim, "S"),
        ]

        # when
        category = get_claim_category(claim)

        # then
        self.assertIsNotNone(category)
        self.assertEquals(category, "S")

        # tearDown
        for service in services:
            service.delete()
        claim.delete()

    def test_get_claim_category_some_invalid(self):
        # Given
        claim = self._create_test_claim()
        services = [
            self._create_test_claimservice(claim, "H", False),
            self._create_test_claimservice(claim, "A", False),
            self._create_test_claimservice(claim, "S"),
        ]

        # when
        category = get_claim_category(claim)

        # then
        self.assertIsNotNone(category)
        self.assertEquals(category, "S")

        # tearDown
        for service in services:
            service.delete()
        claim.delete()

    def test_get_claim_category_null(self):
        # Given
        claim = self._create_test_claim()
        service1 = self._create_test_claimservice(claim, None)

        # when
        category = get_claim_category(claim)

        # then
        self.assertIsNotNone(category)
        self.assertEquals(category, "V")

        # tearDown
        service1.delete()
        claim.delete()

    def test_validate_claim_valid(self):
        # Given
        claim = self._create_test_claim()
        service1 = self._create_test_claimservice(claim, "S")
        service2 = self._create_test_claimservice(claim, "S")
        item1 = self._create_test_claimitem(claim, "D")
        item2 = self._create_test_claimitem(claim, "D")

        # When
        errors = validate_claim(claim)

        # Then
        self.assertEquals(len(errors), 0, "The claim should be fully valid")

        # tearDown
        service1.delete()
        service2.delete()
        item1.delete()
        item2.delete()
        claim.delete()

    # This test cannot be performed because the database constraints don't allow a null date_from.
    # def test_validate_claim_target_date(self):
    #     # Given
    #     claim = self._create_test_claim(custom_props={"date_from": None, "date_to": None})
    #     service1 = self._create_test_claimservice(claim, "S")
    #
    #     # When
    #     errors = validate_claim(claim)
    #
    #     # Then
    #     self.assertEquals(len(errors), 1, "The claim should fail the target date validation")
    #     self.assertEquals(errors[0].code, 9, "The claim should fail the target date validation with code 9")
    #     self.assertTrue("date" in errors[0].message.lower())
    #
    #     # tearDown
    #     service1.delete()
    #     claim.delete()

    def test_validate_pricelist_hf1(self):
        # When the claimitem points to a pricelist that doesn't correspond to the claim HF
        hf_without_pricelist = HealthFacility.objects.filter(item_pricelist__id__isnull=True).first()
        self.assertIsNotNone(hf_without_pricelist, "This test requires a health facility without a price list item")
        # Given
        claim = self._create_test_claim({"health_facility_id": hf_without_pricelist.id})
        service1 = self._create_test_claimservice(claim, "S")
        item1 = self._create_test_claimitem(claim, "D")

        # When
        errors = validate_claim(claim)

        # Then
        claim.refresh_from_db()
        service1.refresh_from_db()
        item1.refresh_from_db()
        self.assertGreaterEqual(len(errors), 1, "Should raise at least one error")
        error2 = [e for e in errors if e.code == 2]
        self.assertGreaterEqual(len(error2), 1, "There should be an error code 2")
        self.assertEquals(item1.rejection_reason, 2, "Database was updated with rejection reason")

        # tearDown
        service1.delete()
        item1.delete()
        claim.delete()

    def test_validate_family(self):
        # When the insuree family is invalid
        # Given
        invalid_insuree = Insuree.objects.filter(family__in=Family.objects.filter(validity_to__isnull=False)).first()
        self.assertIsNotNone(invalid_insuree)
        claim = self._create_test_claim({"insuree_id": invalid_insuree.id})
        service1 = self._create_test_claimservice(claim, "S")
        item1 = self._create_test_claimitem(claim, "D")

        # When
        errors = validate_claim(claim)

        # Then
        claim.refresh_from_db()
        item1.refresh_from_db()
        self.assertGreaterEqual(len(errors), 1, "Should raise at least one error")
        error7 = [e for e in errors if e.code == 7]
        self.assertGreaterEqual(len(error7), 2, "There should be 2 error code 7: invalid insuree, invalid family")
        self.assertEquals(item1.rejection_reason, 7, "Database was updated with rejection reason")

        # tearDown
        service1.delete()
        item1.delete()
        claim.delete()

    def test_validate_max_visits(self):
        # When the insuree already reaches his limit of visits
        # Given
        insuree = self._create_test_insuree()
        self.assertIsNotNone(insuree)
        product = self._create_test_product("VISIT", custom_props={"max_no_visits": 1})
        policy = self._create_test_policy(product, insuree, link=True)
        service = self._create_test_service("V")
        product_service = self._create_test_product_service(product, service)
        pricelist_detail = self._add_service_to_hf_pricelist(service)

        # A first claim for a visit should be accepted
        claim1 = self._create_test_claim({"insuree_id": insuree.id})
        service1 = self._create_test_claimservice(claim1, custom_props={"service_id": service.id})
        errors = validate_claim(claim1)
        self.assertEquals(len(errors), 0, "The first visit should be accepted")

        # a second visit should be denied
        claim2 = self._create_test_claim({"insuree_id": insuree.id})
        service2 = self._create_test_claimservice(claim2, "V")
        errors = validate_claim(claim2)
        # TODO Temporarily disabled
        # self.assertGreater(len(errors), 0, "The second visit should be refused")

        # Then
        claim1.refresh_from_db()
        claim2.refresh_from_db()

        # tearDown
        service2.delete()
        claim2.delete()
        service1.delete()
        claim1.delete()
        policy.insureepolicy_set.first().delete()
        policy.delete()
        product_service.delete()
        pricelist_detail.delete()
        service.delete()
        product.delete()

    def test_validate_patient_category(self):
        # When the insuree already reaches his limit of visits
        # Given
        insuree = self._create_test_insuree()
        self.assertIsNotNone(insuree)
        product = self._create_test_product("VISIT", custom_props={"max_no_visits": 1})
        policy = self._create_test_policy(product, insuree, link=True)
        service = self._create_test_service("V", custom_props={"patient_category": 1})
        product_service = self._create_test_product_service(product, service)
        pricelist_detail = self._add_service_to_hf_pricelist(service)

        # The insuree has a patient_category of 6, not matching the service category
        claim1 = self._create_test_claim({"insuree_id": insuree.id})
        service1 = self._create_test_claimservice(claim1, custom_props={"service_id": service.id})
        errors = validate_claim(claim1)

        # Then
        claim1.refresh_from_db()
        self.assertEquals(len(errors), 1)
        self.assertEquals(errors[0].code, 4)

        # tearDown
        service1.delete()
        claim1.delete()
        policy.insureepolicy_set.first().delete()
        policy.delete()
        product_service.delete()
        pricelist_detail.delete()
        service.delete()
        product.delete()

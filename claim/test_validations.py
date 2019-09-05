from claim.models import Claim, ClaimService
from claim.validations import get_claim_category
from django.test import TestCase
from medical.models import Service


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
    def _create_test_claim():
        return Claim.objects.create(
            health_facility_id=12,
            icd_id=116,
            date_from="2019-06-01",
            date_claimed="2019-06-01",
            date_to="2019-06-01",
            audit_user_id=1,
            insuree_id=136,
            status=1,
            validity_from="2019-06-01",
        )

    @staticmethod
    def _create_test_claimservice(claim, category, valid=True):
        return ClaimService.objects.create(
            claim=claim,
            qty_provided=7,
            price_asked=11,
            service_id=ValidationTest._get_service_of_category(category).id if category else 23,  # Skin graft, no cat
            status=1,
            validity_from="2019-06-01",
            validity_to=None if valid else "2019-06-01",
            audit_user_id=-1,
        )

    @staticmethod
    def _create_test_service(category, valid=True):
        return Service.objects.create(
            code="XXX",
            category=category,
            name="Test service H",
            type="H",
            level=1,
            price=100,
            pat_cat=1,
            validity_from="2019-06-01",
            validity_to=None if valid else "2019-06-01",
            audit_user_id=-1
        )

    def setUp(self) -> None:
        self.service_H = self._create_test_service("H")
        self.service_O = self._create_test_service("O")
        self.service_D = self._create_test_service("D")
        self.service_A = self._create_test_service("A")
        self.service_A_invalid = self._create_test_service("A", False)

    def tearDown(self) -> None:
        self.service_H.delete()
        self.service_O.delete()
        self.service_D.delete()
        self.service_A.delete()
        self.service_A_invalid.delete()

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

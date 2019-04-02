from django.test import TestCase
from unittest import mock
import xml.etree.ElementTree as ET
from .services import *
import core


class SubmitClaimsTestCase(TestCase):

    def test_minimal_item_claim_submit_xml(self):
        items = [
            ClaimItemSubmit(code='aa', quantity=2),
        ]
        item = "<Item><ItemCode>aa</ItemCode><ItemQuantity>2</ItemQuantity></Item>"

        claim = ClaimSubmit(
            date=core.datetime.date(2076, 9, 24),
            code="code_ABVC",
            icd_code="ICD_CODE_WWQ",
            total=334,
            start_date=core.datetime.date(2076, 9, 28),
            claim_admin_code='ADM_CODE_ADKJ',
            insuree_chf_id='CHFID_UUZIS',
            health_facility_code="HFCode_JQL",
            item_submits=items,
        )
        details = "<Details>"
        details = details + "<ClaimDate>09/01/2020</ClaimDate>"
        details = details + "<HFCode>HFCode_JQL</HFCode>"
        details = details + "<ClaimAdmin>ADM_CODE_ADKJ</ClaimAdmin>"
        details = details + "<ClaimCode>code_ABVC</ClaimCode>"
        details = details + "<CHFID>CHFID_UUZIS</CHFID>"
        details = details + "<StartDate>13/01/2020</StartDate>"
        details = details + "<ICDCode>ICD_CODE_WWQ</ICDCode>"
        details = details + "<Total>334</Total>"
        details = details + "</Details>"
        expected = "<Claim>%s<Items>%s</Items></Claim>" % (details, item)
        self.assertEquals(expected, claim.to_xml())

    def test_minimal_service_claim_submit_xml(self):
        services = [
            ClaimServiceSubmit(code='aa', quantity=2),
        ]
        service = "<Service><ServiceCode>aa</ServiceCode><ServiceQuantity>2</ServiceQuantity></Service>"

        claim = ClaimSubmit(
            date=core.datetime.date(2076, 9, 24),
            code="code_ABVC",
            icd_code="ICD_CODE_WWQ",
            total=334,
            start_date=core.datetime.date(2076, 9, 28),
            claim_admin_code='ADM_CODE_ADKJ',
            insuree_chf_id='CHFID_UUZIS',
            health_facility_code="HFCode_JQL",
            service_submits=services,
        )
        details = "<Details>"
        details = details + "<ClaimDate>09/01/2020</ClaimDate>"
        details = details + "<HFCode>HFCode_JQL</HFCode>"
        details = details + "<ClaimAdmin>ADM_CODE_ADKJ</ClaimAdmin>"
        details = details + "<ClaimCode>code_ABVC</ClaimCode>"
        details = details + "<CHFID>CHFID_UUZIS</CHFID>"
        details = details + "<StartDate>13/01/2020</StartDate>"
        details = details + "<ICDCode>ICD_CODE_WWQ</ICDCode>"
        details = details + "<Total>334</Total>"
        details = details + "</Details>"
        expected = "<Claim>%s<Services>%s</Services></Claim>" % (
            details, service)
        self.assertEquals(expected, claim.to_xml())

    def test_extended_claim_submit_xml(self):
        items = [
            ClaimItemSubmit(code='aa', quantity=2),
            ClaimItemSubmit(code='bb', quantity=1, price=12.3),
        ]
        item_a = "<Item><ItemCode>aa</ItemCode><ItemQuantity>2</ItemQuantity></Item>"
        item_b = "<Item><ItemCode>bb</ItemCode><ItemPrice>12.3</ItemPrice><ItemQuantity>1</ItemQuantity></Item>"

        services = [
            ClaimServiceSubmit(code='aa-serv', quantity=2),
            ClaimServiceSubmit(code='a<a\'-serv', quantity=1, price=35),
        ]
        service_a = "<Service><ServiceCode>aa-serv</ServiceCode><ServiceQuantity>2</ServiceQuantity></Service>"
        service_b = "<Service><ServiceCode>a&lt;a\'-serv</ServiceCode><ServicePrice>35</ServicePrice><ServiceQuantity>1</ServiceQuantity></Service>"

        claim = ClaimSubmit(
            date=core.datetime.date(2076, 9, 24),
            code="code_ABVC",
            icd_code="ICD_CODE_WWQ",
            total=334,
            start_date=core.datetime.date(2076, 9, 28),
            claim_admin_code='ADM_CODE_ADKJ',
            insuree_chf_id='CHFID_UUZIS',
            health_facility_code="HFCode_JQL",
            item_submits=items,
            service_submits=services
        )
        details = "<Details>"
        details = details + "<ClaimDate>09/01/2020</ClaimDate>"
        details = details + "<HFCode>HFCode_JQL</HFCode>"
        details = details + "<ClaimAdmin>ADM_CODE_ADKJ</ClaimAdmin>"
        details = details + "<ClaimCode>code_ABVC</ClaimCode>"
        details = details + "<CHFID>CHFID_UUZIS</CHFID>"
        details = details + "<StartDate>13/01/2020</StartDate>"
        details = details + "<ICDCode>ICD_CODE_WWQ</ICDCode>"
        details = details + "<Total>334</Total>"
        details = details + "</Details>"
        expected = "<Claim>%s" % details
        expected = expected + "<Items>%s%s</Items>" % (item_a, item_b)
        expected = expected + \
            "<Services>%s%s</Services>" % (service_a, service_b)
        expected = expected + "</Claim>"
        self.assertEquals(expected, claim.to_xml())


    mock_cursor = mock.MagicMock()    

    @mock.patch("django.db.backends.utils.CursorWrapper")
    def test_claim_submit_error(self, mock_cursor):
        mock_cursor.return_value.__enter__.return_value.fetchone.return_value = [2]

        claim = ClaimSubmit(
            date=core.datetime.date(2076, 9, 24),
            code="code_ABVC",
            icd_code="ICD_CODE_WWQ",
            total=334,
            start_date=core.datetime.date(2076, 9, 28),
            claim_admin_code='ADM_CODE_ADKJ',
            insuree_chf_id='CHFID_UUZIS',
            health_facility_code="HFCode_JQL"            
        )
        with self.assertRaises(ClaimSubmitError) as cm:
            submit_claim(claim)
        self.assertEquals(cm.exception.code, 2)

    mock_cursor = mock.MagicMock()    

    @mock.patch("django.db.backends.utils.CursorWrapper")
    def test_claim_submit_allgood(self, mock_cursor):
        mock_cursor.return_value.__enter__.return_value.description = None

        claim = ClaimSubmit(
            date=core.datetime.date(2076, 9, 24),
            code="code_ABVC",
            icd_code="ICD_CODE_WWQ",
            total=334,
            start_date=core.datetime.date(2076, 9, 28),
            claim_admin_code='ADM_CODE_ADKJ',
            insuree_chf_id='CHFID_UUZIS',
            health_facility_code="HFCode_JQL"            
        )
        submit_claim(claim)

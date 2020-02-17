from claim.models import Claim, ClaimService, ClaimItem
from medical.test_helpers import get_item_of_type, get_service_of_category


def create_test_claim(custom_props={}):
    return Claim.objects.create(
        **{
            "health_facility_id": 18,
            "icd_id": 116,
            "date_from": "2019-06-01",
            "date_claimed": "2019-06-01",
            "date_to": "2019-06-01",
            "audit_user_id": 1,
            "insuree_id": 2,
            "status": 2,
            "validity_from": "2019-06-01",
            **custom_props
        }
    )

def create_test_claimitem(claim, item_type, valid=True, custom_props={}):
    return ClaimItem.objects.create(
        **{
            "claim": claim,
            "qty_provided": 7,
            "price_asked": 11,
            "item_id": get_item_of_type(item_type).id if item_type else 23,  # Atropine
            "status": 1,
            "availability": True,
            "validity_from": "2019-06-01",
            "validity_to": None if valid else "2019-06-01",
            "audit_user_id": -1,
            **custom_props
           }
    )

def create_test_claimservice(claim, category=None, valid=True, custom_props={}):
    return ClaimService.objects.create(
        **{
            "claim": claim,
            "qty_provided": 7,
            "price_asked": 11,
            "service_id": get_service_of_category(category).id if category else 23,  # Skin graft, no cat
            "status": 1,
            "validity_from": "2019-06-01",
            "validity_to": None if valid else "2019-06-01",
            "audit_user_id": -1,
            **custom_props
        }
    )

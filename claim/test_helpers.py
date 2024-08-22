from claim.models import Claim, ClaimService, ClaimItem, ClaimDedRem, ClaimAdmin
from claim.validations import get_claim_category, approved_amount
from claim.services import claim_create, update_sum_claims
from medical.test_helpers import get_item_of_type, get_service_of_category
from uuid import uuid4
from product.models import ProductItem, ProductService, ProductItemOrService
from product.test_helpers import create_test_product_service, create_test_product_item
from medical_pricelist.test_helpers import add_service_to_hf_pricelist, add_item_to_hf_pricelist
from insuree.test_helpers import create_test_insuree
from policy.test_helpers import create_test_policy2
from insuree.models import Insuree

class DummyUser:
    def __init__(self):
      self.id_for_audit = 1  

def create_test_claim(custom_props={}, user = DummyUser(), product=None):
    from datetime import datetime, timedelta
    insuree = None
    if 'insuree' in custom_props:
        insuree = custom_props['insuree']
    if 'insuree_id' in custom_props:
        insuree = Insuree.objects.filter(id=custom_props['insuree_id']).first()
    else:
        insuree = create_test_insuree()
        custom_props["insuree"]= insuree
        
    _to = datetime.now() - timedelta(days=1)
    if product:
        create_test_policy2(product, insuree)
    
    return claim_create(
        {
            "health_facility_id": 18,
            "icd_id": 116,
            "date_from": datetime.now() - timedelta(days=2),
            "date_claimed": _to,
            "date_to": _to,
            "status": 2,
            "validity_from": _to,
            "code": str(uuid4()),
            **custom_props
        }, user
    )


def create_test_claimitem(claim, item_type, valid=True, custom_props={}, product=None):
    item = ClaimItem.objects.create(
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
    update_sum_claims(claim)
    if product:
        product_item = create_test_product_item(
            product,
            item.item,
            custom_props={"price_origin": ProductItemOrService.ORIGIN_RELATIVE},
        )
        pricelist_detail = add_item_to_hf_pricelist(
            item.item,
            hf_id=claim.health_facility.id
        )

    
    return item



def create_test_claimservice(claim, category=None, valid=True, custom_props={}, product=None):
    service =  ClaimService.objects.create(
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
    update_sum_claims(claim)
    if product:
        create_test_product_service(
            product,
            service.service,
            custom_props={"price_origin": ProductItemOrService.ORIGIN_RELATIVE},
        )
        add_service_to_hf_pricelist(
            service.service,
            hf_id=claim.health_facility.id
        )

    
    return service



def mark_test_claim_as_processed(claim, status=Claim.STATUS_CHECKED, audit_user_id=-1):
    claim.approved = approved_amount(claim)
    claim.status = status
    claim.audit_user_id_submit = audit_user_id
    from core.utils import TimeUtils
    claim.submit_stamp = TimeUtils.now()
    claim.category = get_claim_category(claim)
    claim.save()


def delete_claim_with_itemsvc_dedrem_and_history(claim):
    # first delete old versions of the claim
    ClaimDedRem.objects.filter(claim=claim).delete()
    old_claims = Claim.objects.filter(legacy_id=claim.id)
    ClaimItem.objects.filter(claim__in=old_claims).delete()
    ClaimService.objects.filter(claim__in=old_claims).delete()
    old_claims.delete()
    claim.items.all().delete()
    claim.services.all().delete()
    claim.delete()


def create_test_claim_admin(custom_props={}):
    from core import datetime
    code = custom_props.pop('code','TST-CA')
    uuid = custom_props.pop('uuid',None)
    ca = None
    qs_ca = ClaimAdmin.objects
    data = {
        "code": code,
        "uuid": uuid,
        "last_name": "LastAdmin",
        "other_names": "JoeAdmin",
        "email_id": "joeadmin@lastadmin.com",
        "phone": "+12027621401",
        "health_facility_id": 1,
        "has_login": False,
        "audit_user_id": 1,
        "validity_from": datetime.datetime(2019, 6, 1),
        **custom_props
    }
    if code:
        qs_ca = qs_ca.filter(code=code)
    if uuid:
        qs_ca = qs_ca.filter(uuid=uuid)
        
    if code or uuid:
        ca = qs_ca.first()
    if ca:
        data['uuid']=ca.uuid
        ca.update(data)
        return ca
    else:
        data['uuid']=uuid4()
        return ClaimAdmin.objects.create( **data)

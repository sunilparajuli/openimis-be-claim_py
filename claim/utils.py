from claim.models import Claim, ClaimItem, ClaimService, ClaimDetail
from .apps import ClaimConfig


def process_child_relation(user, data_children, claim_id, children, create_hook):
    claimed = 0
    from core.utils import TimeUtils
    for data_elt in data_children:
        claimed += data_elt['qty_provided'] * data_elt['price_asked']
        elt_id = data_elt.pop('id') if 'id' in data_elt else None
        if elt_id:
            # elt has been historized along with claim historization
            elt = children.get(id=elt_id)
            [setattr(elt, k, v) for k, v in data_elt.items()]
            elt.validity_from = TimeUtils.now()
            elt.audit_user_id = user.id_for_audit
            elt.claim_id = claim_id
            elt.validity_to = None
            elt.save()
        else:
            data_elt['validity_from'] = TimeUtils.now()
            data_elt['audit_user_id'] = user.id_for_audit
            # Ensure claim id from func argument will be assigned
            data_elt.pop('claim_id', None)
            # Should entered claim items/services have status passed assigned?
            # Status is mandatory field, and it doesn't have default value in model
            data_elt['status'] = ClaimDetail.STATUS_PASSED
            create_hook(claim_id, data_elt)

    return claimed


def item_create_hook(claim_id, item):
    # TODO: investigate 'availability' is mandatory,
    # but not in UI > always true?
    item['availability'] = True
    ClaimItem.objects.create(claim_id=claim_id, **item)


def service_create_hook(claim_id, service):
    ClaimService.objects.create(claim_id=claim_id, **service)


def process_items_relations(user, claim, items):
    return process_child_relation(user, items, claim.id, claim.items, item_create_hook)


def process_services_relations(user, claim, services):
    return process_child_relation(user, services, claim.id, claim.services, service_create_hook)


def __autogenerate_nepali_claim_code():
    code_length = ClaimConfig.claim_autogenerate_code_length
    prefix = __get_current_nepali_fiscal_year_code()
    last_claim = Claim.objects.filter(validity_to__isnull=True, code__icontains=prefix)
    code = 0
    if last_claim:
        code = int(last_claim.latest('code').code[-code_length:])
    return prefix + str(code+1).zfill(code_length)


def __get_current_nepali_fiscal_year_code():
    import nepali_datetime
    current_date = nepali_datetime.date.today()

    if current_date.month < 4:
        current_year = nepali_datetime.date.today().year - 1
    else:
        current_year = nepali_datetime.date.today().year

    year_code = str(current_year) + "-" + str(current_year+1)[-3:] + "-"
    return year_code

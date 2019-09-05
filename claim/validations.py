from collections import OrderedDict

CLAIM_VAL_ERR_FAMILY = 7
CLAIM_VAL_ERR_TARGET_DATE = 9


def validate_claim(claim):
    """
    Based on the legacy validation, this method returns standard codes along with details
    :param claim: claim to be verified
    :return: (result_code, error_details)
    """
    family_valid, family_valid_message = validate_family(claim.insuree)
    if not family_valid:
        return 7, family_valid_message
    category = get_claim_category(claim)
    return None, None

def validate_family(insuree):
    if insuree.validity_to is not None:
        return False, "Insuree validity expired"
    if insuree.family is None:
        return False, "Insuree has no family"  # TODO This message does seem strange
    if insuree.family.validity_to is not None:
        return False, "Insuree family validity expired"
    return True, None


def get_claim_category(claim):
    """
    Determine the claim category based on its services:
    S = Surgery
    D = Delivery
    A = Antenatal care
    H = Hospitalization
    C = Consultation
    O = Other
    V = Visit
    :param claim: claim for which category should be determined
    :return: category if a service is defined, None if not service at all
    """

    service_categories = OrderedDict([
        ("S", "Surgery"),
        ("D", "Delivery"),
        ("A", "Antenatal care"),
        ("H", "Hospitalization"),
        ("C", "Consultation"),
        ("O", "Other"),
        ("V", "Visit"),
    ])
    claim_service_categories = [
        item["service__category"]
        for item in claim.services
        .filter(validity_to__isnull=True)
        .filter(service__validity_to__isnull=True)
        .values("service__category").distinct()
    ]
    for category in service_categories:
        if category in claim_service_categories:
            claim_category = category
            break
    else:
        claim_category = "V"  # One might expect "O" here but the legacy code uses "V"

    return claim_category

# openIMIS Backend Claim reference module
This repository holds the files of the openIMIS Backend Claim reference module.
It is dedicated to be deployed as a module of [openimis-be_py](https://github.com/openimis/openimis-be_py).

## Code climat (develop branch)

[![Maintainability](https://img.shields.io/codeclimate/maintainability/openimis/openimis-be-claim_py.svg)](https://codeclimate.com/github/openimis/openimis-be-claim_py/maintainability)
[![Test Coverage](https://img.shields.io/codeclimate/coverage/openimis/openimis-be-claim_py.svg)](https://codeclimate.com/github/openimis/openimis-be-claim_py/maintainability)

## Content

Current version provides the following ORM mapping:
* tblClaimAdmin > ClaimAdmin
* tblICDCodes > ClaimDiagnosisCode
* tblFeedback > Feedback
* tblClaim  > Claim (without fk to tblBatchrun)
* tblClaimItems > ClaimItem (without fk to tblProduct)
* tblClaimServices > ClaimService (without fk to tblProduct)

It also provides the following services
* ClaimSubmitService.submit (requires claim.can_add permission)
* EligibilityService.request (requires claim.can_view permission)

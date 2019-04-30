# openIMIS Backend Claim reference module
This repository holds the files of the openIMIS Backend Claim reference module.
It is dedicated to be deployed as a module of [openimis-be_py](https://github.com/openimis/openimis-be_py).

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

## Code climat (develop branch)

[![Maintainability](https://img.shields.io/codeclimate/maintainability/openimis/openimis-be-claim_py.svg)](https://codeclimate.com/github/openimis/openimis-be-claim_py/maintainability)
[![Test Coverage](https://img.shields.io/codeclimate/coverage/openimis/openimis-be-claim_py.svg)](https://codeclimate.com/github/openimis/openimis-be-claim_py)

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

## Dependencies

This module depends on the following modules and entities:
* core.InteractiveUser
* location.HealthFacility
* insuree.Insuree
* medical.Item
* medical.Service
* policy.Policy
# openIMIS Backend Claim reference module
This repository holds the files of the openIMIS Backend Claim reference module.
It is dedicated to be deployed as a module of [openimis-be_py](https://github.com/openimis/openimis-be_py).

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

## Code climat (develop branch)

[![Maintainability](https://img.shields.io/codeclimate/maintainability/openimis/openimis-be-claim_py.svg)](https://codeclimate.com/github/openimis/openimis-be-claim_py/maintainability)
[![Test Coverage](https://img.shields.io/codeclimate/coverage/openimis/openimis-be-claim_py.svg)](https://codeclimate.com/github/openimis/openimis-be-claim_py)

## ORM mapping:
* tblClaimAdmin > ClaimAdmin
* tblFeedback > Feedback
* tblClaim  > Claim
* tblClaimItems > ClaimItem
* tblClaimServices > ClaimService
* tblOfficer > ClaimOfficer (partially mapped)

## Listened Django Signals
None

## Services
* *DEPRECATED* ClaimSubmitService.submit, mapped to uspUpdateClaimFromPhone Stored Proc (used by api_fhir reference implementation: needs replacement, with signals)
* ClaimReportService, loading the necessary data for the Claim printing

## Reports (template can be overloaded via report.ReportDefinition)
* claim_claims (Claim printing)

## GraphQL Queries
* claims
* claim_admins
* claim_officers

## GraphQL Mutations - each mutation emits default signals and return standard error lists (cfr. openimis-be-core_py)
* create_claim
* update_claim
* submit_claims
* select_claims_for_feedback
* deliver_claim_feedback
* bypass_claims_feedback
* skip_claims_feedback
* select_claims_for_review
* deliver_claim_review
* bypass_claims_review
* skip_claims_review
* process_claims
* delete_claims

## Configuration options (can be changed via core.ModuleConfiguration)
* default_validations_disabled: bypass (defaul) claim validations in Submit and Process mutations (default: False)
* gql_query_claims_perms: required rights to use claims GraphQL Query (default: ["111001"])
* gql_query_claim_admins_perms: required rights to use claim_admins GraphQL Query (default: [])
* gql_query_claim_officers_perms: required rights to use claim_officers GraphQL Query (default: [])
* gql_mutation_create_claims_perms: required rights to use create_claim GraphQL Mutation (default: ["111002"])
* gql_mutation_update_claims_perms: required rights to use update_claim GraphQL Mutation (default: ["111010"])
* gql_mutation_submit_claims_perms: required rights to use submit_claim GraphQL Mutation (default: ["111007"])
* gql_mutation_select_claim_feedback_perms: required rights to use select_claim_feedback GraphQL Mutation (default: ["111010"])
* gql_mutation_bypass_claim_feedback_perms: required rights to use bypass_claim_feedback GraphQL Mutation (default: ["111010"])
* gql_mutation_skip_claim_feedback_perms: required rights to use skip_claim_feedback GraphQL Mutation (default: ["111010"])
* gql_mutation_deliver_claim_feedback_perms: required rights to use deliver_claim_feedback GraphQL Mutation (default: ["111009"])
* gql_mutation_select_claim_review_perms: required rights to use select_claim_review GraphQL Mutation (default: ["111010"])
* gql_mutation_bypass_claim_review_perms: required rights to use bypass_claim_review GraphQL Mutation (default: ["111010"])
* gql_mutation_skip_claim_review_perms: required rights to use skip_claim_review GraphQL Mutation (default: ["111010"])
* gql_mutation_deliver_claim_review_perms: required rights to use deliver_claim_review GraphQL Mutation (default: ["111010"])
* gql_mutation_process_claims_perms: required rights to use process_claims GraphQL Mutation (default: ["111011"])
* gql_mutation_delete_claims_perms: required rights to use delete_claims GraphQL Mutation (default: ["111004"])
* claim_print_perms: required rights to call print endpoint (default: ["111006"])

## openIMIS Modules Dependencies
* core.models.VersionedModel
* core.models.InteractiveUser
* insuree.models.Insuree
* location.models.HealthFacility
* medical.models.Diagnosis
* medical.models.Item
* medical.models.Service
* policy.models.Policy
* report.services.ReportService
import base64
import json
from dataclasses import dataclass
from core.models import User
from core.test_helpers import create_test_interactive_user
from django.conf import settings
from graphene_django.utils.testing import GraphQLTestCase
from graphql_jwt.shortcuts import get_token
#credits https://docs.graphene-python.org/projects/django/en/latest/testing/
from claim import schema as claim_schema
from graphene.test import Client
from graphene import Schema

from claim.models import Claim
@dataclass
class DummyContext:
    """ Just because we need a context to generate. """
    user: User

class ClaimGraphQLTestCase(GraphQLTestCase):
    GRAPHQL_URL = f'/{settings.SITE_ROOT()}graphql'
    # This is required by some version of graphene but is never used. It should be set to the schema but the import
    # is shown as an error in the IDE, so leaving it as True.
    GRAPHQL_SCHEMA = True
    admin_user = None
    graph_client = None
    schema = None        
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin_user = create_test_interactive_user(username="testLocationAdmin")
        cls.admin_token = get_token(cls.admin_user, DummyContext(user=cls.admin_user))
        cls.schema = Schema(
            query=claim_schema.Query,
            mutation=claim_schema.Mutation
        )
        cls.graph_client = Client(cls.schema)

    def test_claims_query(self):
        
        response = self.query(
            '''
            query {
                claims
                {
                    totalCount
                    pageInfo { hasNextPage, hasPreviousPage, startCursor, endCursor}
                    edges
                    {
                        node
                        {
                            uuid,code,jsonExt,dateClaimed,dateProcessed,feedbackStatus,reviewStatus,claimed,approved,status,restore {id},healthFacility { id uuid name code },insuree{id, uuid, chfId, lastName, otherNames, dob},attachmentsCount
                        }
                    }
                }
            }
            ''',
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.admin_token}"},
        )

        content = json.loads(response.content)

        # This validates the status code and if you get errors
        self.assertResponseNoErrors(response)

        # Add some more asserts if you like
        ...

    def test_query_with_variables(self):
        response = self.query(
            '''
            query claims($status: Int!, $first:  Int! ) {
                claims(status: $status,orderBy: ["-dateClaimed"],first: $first)
                {
                    totalCount
                    pageInfo { hasNextPage, hasPreviousPage, startCursor, endCursor}
                    edges
                    {
                        node
                        {
                            uuid,code,jsonExt,dateClaimed,dateProcessed,feedbackStatus,reviewStatus,claimed,approved,status,restore {id},healthFacility { id uuid name code },insuree{id, uuid, chfId, lastName, otherNames, dob},attachmentsCount
                        }
                    }
                }
            }
            ''',
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.admin_token}"},
            variables={'status': 2, 'first':10}
        )

        content = json.loads(response.content)

        # This validates the status code and if you get errors
        self.assertResponseNoErrors(response)
        
    def execute_mutation(self, mutation):
        mutation_result = self.graph_client.execute(mutation, context=DummyContext(user=self.admin_user))
        return mutation_result
        
    def test_mutation_create_claim(self):   
        response = self.query(
            '''
            mutation {
                createClaim(
                    input: {
                    clientMutationId: "3a90436a-d5ea-48e7-bde4-0bcff0240260"
                    clientMutationLabel: "Create Claim - m-c-claim" 
                    code: "m-c-claim"
                autogenerate: false
                insureeId: 1
                adminId: 15
                dateFrom: "2023-12-06"  
                icdId: 2 
                jsonExt: "{}"
                feedbackStatus: 1
                reviewStatus: 1
                dateClaimed: "2023-12-06"
                healthFacilityId: 4
                visitType: "O"
                services: [
                {
                
                serviceId: 90
                priceAsked: "10.00"
                qtyProvided: "1.00"
                status: 1
            }
                ]
                items: [
                {
                
                itemId: 7
                priceAsked: "160.00"
                qtyProvided: "1.00"
                status: 1
            }
                ]
                    }
                ) {
                    clientMutationId
                    internalId
                }
            }
                ''',
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.admin_token}"})
        
        claim = Claim.objects.filter(code = 'm-c-claim').first()
        self.assertIsNotNone(claim)
        self.assertEqual(claim.status, Claim.STATUS_ENTERED)
            
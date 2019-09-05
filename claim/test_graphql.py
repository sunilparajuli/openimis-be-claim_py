import graphene
from core import schema as core_schema
from claim import schema as claim_schema
from core.models import User, TechnicalUser
from django.test import TestCase
from graphene.test import Client
from openIMIS.schema import schema


class TestContext:
    user = None


class TestGraphQL(TestCase):
    user = None
    context = TestContext()

    def setUp(self) -> None:
        self.user = TechnicalUser.objects.create(username="graphql", password="graphql", is_staff=True)
        self.context.user = self.user

    def test_claims_nofilter(self):
        client = Client(schema=schema)
        executed = client.execute('''{ claims { edges {node {id}} } }''',
                                  context_value=self.context)
        self.assertFalse(hasattr(executed, "errors"))
        self.assertGreaterEqual(len(executed["data"]["claims"]["edges"]), 1)
        # This can also be used, but in this case in not predictable enough:
        # assert executed == {
        #     'data': {
        #         'claims': {
        #             'edges': [
        #                 {
        #                     'node': {
        #                         'id': '...'
        #                     }
        #                 },
        #             ]
        #         }
        #     }
        # }

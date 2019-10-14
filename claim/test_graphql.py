from core.models import InteractiveUser, Language, User
from django.test import TestCase
from graphene.test import Client
from openIMIS.schema import schema


class TestContext:
    user = None


class TestGraphQL(TestCase):
    user = None
    context = TestContext()

    def setUp(self) -> None:
        int_user = InteractiveUser.objects.get(login_name="Admin")
        self.user = User.objects.get_or_create(us)
        self.context.user = self.user

    def test_claims_nofilter(self):
        client = Client(schema=schema)
        # executed = client.execute('''{ claims { edges {node {id}} } }''',
        #                           context_value=self.context)
        # self.assertFalse(hasattr(executed, "errors"))
        # self.assertGreaterEqual(len(executed["data"]["claims"]["edges"]), 1)
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

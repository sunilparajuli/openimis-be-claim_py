import random

from claim.test_helpers import create_test_claim, create_test_claimservice, create_test_claimitem
from django.core.management.base import BaseCommand
from insuree.models import Insuree
from medical.models import Service


class Command(BaseCommand):
    help = "This command will generate test Claims with some optional parameters. It is intended to simulate larger" \
           "databases for performance testing"
    insurees = None
    services = None
    items = None

    def add_arguments(self, parser):
        parser.add_argument("nb_claims", nargs=1, type=int)
        parser.add_argument("nb_services", nargs=1, type=int, help="number of services per claim, with 10% randomness")
        parser.add_argument("nb_items", nargs=1, type=int, help="number of items per claim, with 10% randomness")
        parser.add_argument(
            '--verbose',
            action='store_true',
            dest='verbose',
            help='Be verbose about what it is doing',
        )

    def handle(self, *args, **options):
        nb_claims = options["nb_claims"][0]
        nb_services = options["nb_services"][0]
        nb_items = options["nb_items"][0]
        verbose = options["verbose"]
        for claim_num in range(1, nb_claims + 1):
            insuree = self.get_random_insuree()
            claim = create_test_claim({"insuree_id": insuree})
            if verbose:
                print(claim_num, "created claim", claim, "for insuree", insuree)
            for svc_num in range(1, nb_services + 1):
                service = self.get_random_service()
                claim_service = create_test_claimservice(claim, custom_props={"service_id": service})
                if verbose:
                    print(claim_num, svc_num, "Created claim service", claim_service, "for service", service)
            for item_num in range(1, nb_items + 1):
                item = self.get_random_service()
                claim_item = create_test_claimitem(claim, "D", custom_props={"item_id": item})
                if verbose:
                    print(claim_num, item_num, "Created claim service", claim_item, "for service", item)

    def get_random_insuree(self):
        if not self.insurees:
            self.insurees = Insuree.objects.filter(validity_to__isnull=True).values_list("pk", flat=True)
        return random.choice(self.insurees)

    def get_random_service(self):
        if not self.services:
            self.services = Service.objects.filter(validity_to__isnull=True).values_list("pk", flat=True)
        return random.choice(self.services)
